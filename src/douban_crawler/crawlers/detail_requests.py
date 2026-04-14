from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from douban_crawler.config import POSTER_DIR, settings
from douban_crawler.models import CommentRecord, MovieRecord
from douban_crawler.selenium.cookie_bootstrap import DoubanCookieBootstrapper
from douban_crawler.utils.http import RequestOptions, RotatingSession
from douban_crawler.utils.logging_utils import configure_logger
from douban_crawler.utils.storage import SQLiteStore
from douban_crawler.utils.text import clean_text, slugify


class DetailRequestsCrawler:
    def __init__(self) -> None:
        settings.ensure_directories()
        self.logger = configure_logger()
        self.session = RotatingSession()
        self.cookie_bootstrapper = DoubanCookieBootstrapper()
        self.store = SQLiteStore()
        self.cookies: dict[str, str] = {}

    def enrich(self, movies: list[MovieRecord]) -> tuple[list[MovieRecord], list[CommentRecord]]:
        if not movies:
            return movies, []

        self.cookies = self.cookie_bootstrapper.load_or_fetch(movies[0].detail_url)
        if settings.movie_limit > 0:
            movies = movies[: settings.movie_limit]

        all_comments: list[CommentRecord] = []
        for movie in tqdm(movies, desc="detail-pages"):
            detail_html = self._get_html(movie.detail_url)
            self._parse_detail_page(movie, detail_html)

            comments_html = self._get_html(f"{movie.detail_url}comments?status=P")
            comments = self._parse_comments(movie.movie_id, comments_html)
            all_comments.extend(comments[: settings.comment_target_count])

            if movie.poster_url:
                movie.poster_path = self._download_poster(movie.poster_url, movie.rank, movie.title_cn)

        self.store.save_movies(movies)
        self.store.save_comments(all_comments)
        return movies, all_comments

    def _get_html(self, url: str) -> str:
        response = self.session.get(
            url,
            cookies=self.cookies,
            options=RequestOptions(),
        )
        text = response.text
        if "<form name=\"sec\"" in text or "载入中 ..." in text:
            self.logger.warning("Cookie expired when requesting %s, refreshing", url)
            self.cookies = self.cookie_bootstrapper.fetch(url)
            text = self.session.get(
                url,
                cookies=self.cookies,
                options=RequestOptions(),
            ).text
        return text

    def _parse_detail_page(self, movie: MovieRecord, html: str) -> None:
        soup = BeautifulSoup(html, "lxml")
        year_node = soup.select_one("#content span.year")
        runtime_node = soup.select_one('span[property="v:runtime"]')
        summary_node = soup.select_one('span[property="v:summary"]')
        poster_node = soup.select_one("#mainpic img")
        info_node = soup.select_one("#info")

        movie.year = self._extract_year(year_node.get_text(strip=True)) if year_node else None
        movie.runtime = clean_text(runtime_node.get_text(strip=True)) if runtime_node else ""
        movie.genres = [clean_text(node.get_text(strip=True)) for node in soup.select('span[property="v:genre"]')]
        movie.summary = clean_text(summary_node.get_text(" ", strip=True)) if summary_node else ""
        movie.poster_url = poster_node["src"] if poster_node else ""
        movie.imdb_id = self._extract_imdb_id(info_node) if info_node else ""
        movie.imdb_rating = self._fetch_imdb_rating(movie.imdb_id) if movie.imdb_id else None

    def _parse_comments(self, movie_id: str, html: str) -> list[CommentRecord]:
        soup = BeautifulSoup(html, "lxml")
        comments: list[CommentRecord] = []
        for node in soup.select(".comment-item"):
            user_node = node.select_one(".comment-info a")
            rating_node = node.select_one(".comment-info .rating")
            time_node = node.select_one(".comment-time")
            content_node = node.select_one(".short")
            if not user_node or not content_node:
                continue

            comments.append(
                CommentRecord(
                    movie_id=movie_id,
                    user_name=clean_text(user_node.get_text(strip=True)),
                    rating_text=clean_text(rating_node.get("title", "未评分")) if rating_node else "未评分",
                    comment_time=clean_text(
                        time_node.get("title") or time_node.get_text(strip=True)
                    )
                    if time_node
                    else "",
                    content=clean_text(content_node.get_text(" ", strip=True)),
                )
            )
            if len(comments) >= settings.comment_target_count:
                break
        return comments

    def _download_poster(self, poster_url: str, rank: int, title_cn: str) -> str:
        filename = f"{rank:03d}_{slugify(title_cn)}{Path(poster_url).suffix or '.jpg'}"
        output_path = POSTER_DIR / filename
        if output_path.exists():
            return str(output_path)

        response = self.session.session.get(
            poster_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://movie.douban.com/",
            },
            timeout=settings.timeout,
        )
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return str(output_path)

    @staticmethod
    def _extract_year(text: str) -> int | None:
        match = re.search(r"(\d{4})", text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_imdb_id(info_node: BeautifulSoup) -> str:
        for link in info_node.select("a[href*='imdb.com/title/']"):
            match = re.search(r"title/(tt\d+)", link.get("href", ""))
            if match:
                return match.group(1)
        return ""

    def _fetch_imdb_rating(self, imdb_id: str) -> float | None:
        try:
            response = requests.get(
                f"https://www.imdb.com/title/{imdb_id}/",
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=settings.timeout,
            )
            if response.status_code != 200:
                self.logger.warning(
                    "IMDb rating unavailable for %s, status=%s",
                    imdb_id,
                    response.status_code,
                )
                return None
            match = re.search(r'"ratingValue":\s*"?(?P<rating>\d+\.\d+)', response.text)
            return float(match.group("rating")) if match else None
        except requests.RequestException as exc:
            self.logger.warning("IMDb rating request failed for %s: %s", imdb_id, exc)
            return None
