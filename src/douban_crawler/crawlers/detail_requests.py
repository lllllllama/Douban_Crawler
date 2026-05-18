from __future__ import annotations

import brotli
import re
import time
import random
from typing import Any

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from douban_crawler.config import settings
from douban_crawler.models import MovieRecord
from douban_crawler.utils.logging_utils import configure_logger
from douban_crawler.utils.posters import download_poster
from douban_crawler.utils.text import clean_text


class DetailRequestsCrawler:
    def __init__(self) -> None:
        settings.ensure_directories()
        self.logger = configure_logger()
        self.cookies: dict[str, str] = {}

        # 使用标准 requests.Session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def enrich(self, movies: list[MovieRecord]) -> None:
        for movie in tqdm(movies, desc="detail-pages"):
            try:
                # 随机延迟，降低频率
                time.sleep(random.uniform(4, 8))

                # 1. 获取详情页
                detail_html = self._get_html(movie.detail_url)
                self._parse_detail(detail_html, movie)
                if movie.poster_url:
                    try:
                        movie.poster_path = download_poster(
                            movie.poster_url,
                            title=movie.title_cn,
                            rank=movie.rank,
                            session=self.session,
                        )
                    except Exception as e:
                        self.logger.warning("海报下载失败 %s: %s", movie.title_cn, e)

                # 2. 获取短评页
                comments_url = f"{movie.detail_url}comments?status=P"
                comments_html = self._get_html(comments_url)
                self._parse_comments(comments_html, movie)

            except Exception as e:
                self.logger.warning(f"跳过电影 {movie.title_cn} (ID: {movie.movie_id})，原因: {e}")
                continue

    def _get_html(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, settings.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    cookies=self.cookies,
                    headers={
                        "Referer": "https://movie.douban.com/",
                        "User-Agent": random.choice(settings.headers_pool),
                    },
                    timeout=settings.timeout,
                )
                if response.status_code in {403, 429, 500, 502, 503, 504}:
                    raise RuntimeError(f"status {response.status_code}")
                response.raise_for_status()
                if response.headers.get("Content-Encoding") == "br":
                    try:
                        return brotli.decompress(response.content).decode("utf-8")
                    except Exception:
                        return response.text
                return response.text
            except Exception as exc:
                last_error = exc
                self.logger.warning("详情请求失败 %s/%s: %s", attempt, settings.max_retries, exc)
                if settings.enable_exponential_backoff:
                    time.sleep(min(2 ** attempt, 20))
        raise RuntimeError(f"请求失败：{url}") from last_error

    def _parse_detail(self, html: str, movie: MovieRecord) -> None:
        soup = BeautifulSoup(html, "lxml")
        info_node = soup.select_one("#info")
        if not info_node:
            return

        info_text = info_node.get_text(" ", strip=True)

        # 提取年份
        year_source = " ".join(
            [
                info_text,
                soup.select_one("#content span.year").get_text(" ", strip=True)
                if soup.select_one("#content span.year")
                else "",
            ]
        )
        year_match = re.search(r"(\d{4})", year_source)
        if year_match:
            movie.year = int(year_match.group(1))

        # 提取导演
        director_nodes = info_node.select("a[rel='v:directedBy']")
        if director_nodes:
            movie.directors = [clean_text(d.get_text(strip=True)) for d in director_nodes]

        # 提取编剧
        writer_match = re.search(r"编剧</span>:\s*(.*?)(?:\s*<br/>|\s*</span>|\n)", html, re.DOTALL)
        if writer_match:
            writers_text = writer_match.group(1)
            writers = re.findall(r'<a[^>]*>([^<]+)</a>', writers_text)
            movie.writers = [clean_text(w) for w in writers]

        # 提取主演
        actor_nodes = soup.select("a[rel='v:starring']")
        if actor_nodes:
            movie.actors = [clean_text(a.get_text(strip=True)) for a in actor_nodes[:5]]

        # 提取类型
        genre_nodes = soup.select("span[property='v:genre']")
        if genre_nodes:
            movie.genres = [clean_text(g.get_text(strip=True)) for g in genre_nodes]

        # 提取制片国家/地区
        country_match = re.search(r"制片国家/地区:</span>\s*([^<]+)", html)
        if country_match:
            movie.country = clean_text(country_match.group(1))

        # 提取语言
        lang_match = re.search(r"语言:</span>\s*([^<]+)", html)
        if lang_match:
            movie.language = clean_text(lang_match.group(1))

        # 提取片长
        runtime_match = re.search(r"片长:</span>\s*([^<]+)", html)
        if runtime_match:
            runtime_text = runtime_match.group(1)
            minute_match = re.search(r"(\d+)", runtime_text)
            if minute_match:
                movie.runtime = int(minute_match.group(1))

        # 提取IMDb链接
        imdb_node = info_node.select_one("a[href*='imdb.com']")
        if imdb_node:
            movie.imdb_url = imdb_node["href"]
            imdb_match = re.search(r"title/(tt\d+)", movie.imdb_url)
            if imdb_match:
                movie.imdb_id = imdb_match.group(1)

        # 提取剧情简介
        summary_node = soup.select_one("span[property='v:summary']")
        if summary_node:
            movie.summary = clean_text(summary_node.get_text(" ", strip=True))

        poster_node = soup.select_one("#mainpic img")
        if poster_node and poster_node.get("src"):
            movie.poster_url = str(poster_node["src"])

    def _parse_comments(self, html: str, movie: MovieRecord) -> None:
        soup = BeautifulSoup(html, "lxml")
        comments: list[dict[str, Any]] = []
        for node in soup.select(".comment-item"):
            user_node = node.select_one(".comment-info a")
            vote_node = node.select_one(".comment-info .rating")
            time_node = node.select_one(".comment-time")
            content_node = node.select_one(".comment-content") or node.select_one(".short")

            user = clean_text(user_node.get_text(strip=True)) if user_node else ""
            rating = 0
            if vote_node:
                rating_match = re.search(r"allstar(\d+)", " ".join(vote_node.get("class", [])))
                if rating_match:
                    rating = int(rating_match.group(1)) // 10
            time_str = clean_text(
                (time_node.get("title") or time_node.get_text(strip=True)) if time_node else ""
            )
            content = clean_text(content_node.get_text(" ", strip=True)) if content_node else ""

            comments.append({
                "user": user,
                "rating": rating,
                "time": time_str,
                "content": content
            })
        movie.comments = comments
