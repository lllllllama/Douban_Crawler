from __future__ import annotations

import random
import re

import scrapy
from bs4 import BeautifulSoup

from douban_crawler.config import settings
from douban_crawler.selenium.cookie_bootstrap import DoubanCookieBootstrapper
from douban_crawler.utils.http import RequestOptions, RotatingSession
from douban_crawler.utils.text import clean_text
from scrapy_douban.items import CommentItem, MovieItem


class Top250Spider(scrapy.Spider):
    name = "top250"
    allowed_domains = ["movie.douban.com"]

    def __init__(self, list_page_count: int | str | None = None, movie_limit: int | str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.list_page_count = int(list_page_count or settings.list_page_count)
        self.movie_limit = int(movie_limit or 0)
        self.dispatched_movies = 0
        self.cookie_bootstrapper = DoubanCookieBootstrapper()
        self.comment_session = RotatingSession()
        self.comment_cookies: dict[str, str] = {}

    def start_requests(self):
        for page_index in range(self.list_page_count):
            yield scrapy.Request(
                url=f"{settings.base_url}?start={page_index * 25}&filter=",
                callback=self.parse,
            )

    def parse(self, response):
        for node in response.css("ol.grid_view > li"):
            if self.movie_limit and self.dispatched_movies >= self.movie_limit:
                return

            detail_url = node.css(".hd a::attr(href)").get()
            if not detail_url:
                continue

            title_nodes = node.css(".hd .title::text").getall()
            other_title = node.css(".hd .other::text").get()
            quote = node.css(".quote span::text").get() or ""
            people_info = " ".join(
                clean_text(text)
                for text in node.css(".bd > p:not(.quote) *::text, .bd > p:not(.quote)::text").getall()
                if clean_text(text)
            )
            vote_source = " ".join(node.css(".bd *::text").getall())
            vote_match = re.search(r"(\d+)人评价", vote_source)
            movie_id_match = re.search(r"/subject/(\d+)/", detail_url)

            payload = {
                "movie_id": movie_id_match.group(1) if movie_id_match else "",
                "rank": int(node.css(".pic em::text").get()),
                "title_cn": clean_text(title_nodes[0]) if title_nodes else "",
                "title_foreign": clean_text(title_nodes[1]) if len(title_nodes) > 1 else clean_text(other_title or ""),
                "score": float(node.css(".rating_num::text").get() or 0),
                "votes": int(vote_match.group(1)) if vote_match else 0,
                "people_info": clean_text(people_info),
                "quote": clean_text(quote),
                "detail_url": detail_url,
            }
            self.dispatched_movies += 1
            yield response.follow(detail_url, callback=self.parse_detail, cb_kwargs={"payload": payload})

    def parse_detail(self, response, payload: dict):
        info_node = response.css("#info")
        imdb_href = next(
            (
                href
                for href in info_node.css("a::attr(href)").getall()
                if "imdb.com/title/" in href
            ),
            "",
        )
        imdb_match = re.search(r"title/(tt\d+)", imdb_href)

        payload.update(
            {
                "_item_type": "movie",
                "year": self._extract_year(response.css("#content span.year::text").get()),
                "runtime": clean_text(response.css('span[property="v:runtime"]::text').get() or ""),
                "genres": [clean_text(text) for text in response.css('span[property="v:genre"]::text').getall()],
                "imdb_url": imdb_href,
                "imdb_id": imdb_match.group(1) if imdb_match else "",
                "imdb_rating": None,
                "summary": clean_text(
                    " ".join(response.css('span[property="v:summary"] *::text, span[property="v:summary"]::text').getall())
                ),
                "directors": [clean_text(text) for text in response.css("a[rel='v:directedBy']::text").getall()],
                "writers": self._extract_info_links(response.text, "编剧"),
                "actors": [clean_text(text) for text in response.css("a[rel='v:starring']::text").getall()[:5]],
                "country": self._extract_info_text(response.text, "制片国家/地区"),
                "language": self._extract_info_text(response.text, "语言"),
                "poster_url": response.css("#mainpic img::attr(src)").get() or "",
                "poster_path": "",
            }
        )
        yield MovieItem(payload)

        comment_url = f"{payload['detail_url']}comments?status=P"
        for item in self.fetch_comments(payload["movie_id"], comment_url):
            yield item

    def fetch_comments(self, movie_id: str, comment_url: str):
        if not self.comment_cookies:
            self.comment_cookies = self.cookie_bootstrapper.fetch(comment_url)

        response = self.comment_session.get(
            comment_url,
            cookies=self.comment_cookies,
            options=RequestOptions(),
        )
        html = response.text
        if "<form name=\"sec\"" in html or "载入中 ..." in html:
            self.comment_cookies = self.cookie_bootstrapper.fetch(comment_url)
            html = self.comment_session.get(
                comment_url,
                cookies=self.comment_cookies,
                options=RequestOptions(),
            ).text

        soup = BeautifulSoup(html, "lxml")
        for node in soup.select(".comment-item")[: settings.comment_target_count]:
            rating_node = node.select_one(".comment-info .rating")
            time_node = node.select_one(".comment-time")
            yield CommentItem(
                {
                    "_item_type": "comment",
                    "movie_id": movie_id,
                    "user_name": clean_text(
                        (node.select_one(".comment-info a").get_text(strip=True) if node.select_one(".comment-info a") else "")
                    ),
                    "rating_text": clean_text(rating_node.get("title", "未评分")) if rating_node else "未评分",
                    "comment_time": clean_text(
                        (time_node.get("title") or time_node.get_text(strip=True)) if time_node else ""
                    ),
                    "content": clean_text(
                        node.select_one(".short").get_text(" ", strip=True) if node.select_one(".short") else ""
                    ),
                }
            )

    def pick_user_agent(self) -> str:
        return random.choice(settings.headers_pool)

    def pick_proxy(self) -> str | None:
        return random.choice(settings.proxies) if settings.proxies else None

    @staticmethod
    def _extract_year(text: str | None) -> int | None:
        if not text:
            return None
        match = re.search(r"(\d{4})", text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_info_text(html: str, label: str) -> str:
        match = re.search(rf"{re.escape(label)}:</span>\s*([^<]+)", html)
        return clean_text(match.group(1)) if match else ""

    @staticmethod
    def _extract_info_links(html: str, label: str) -> list[str]:
        match = re.search(rf"{re.escape(label)}</span>:\s*(.*?)(?:<br/>|\n)", html, re.DOTALL)
        if not match:
            return []
        return [clean_text(text) for text in re.findall(r"<a[^>]*>([^<]+)</a>", match.group(1))]
