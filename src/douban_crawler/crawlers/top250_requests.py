from __future__ import annotations

import brotli
import re
import time
import random
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from douban_crawler.config import RAW_DATA_DIR, settings
from douban_crawler.models import MovieRecord
from douban_crawler.utils.exporters import export_csv, export_json
from douban_crawler.utils.list_metadata import parse_list_people_info
from douban_crawler.utils.logging_utils import configure_logger
from douban_crawler.utils.robots import build_robot_parser, is_allowed
from douban_crawler.utils.text import clean_text


class Top250RequestsCrawler:
    def __init__(self) -> None:
        settings.ensure_directories()
        self.logger = configure_logger()
        self.robot_parser = build_robot_parser(settings.base_url)

        # 使用标准 requests.Session 替代 RotatingSession
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def crawl(self) -> list[MovieRecord]:
        records: list[MovieRecord] = []
        for page_index in tqdm(range(settings.list_page_count), desc="list-pages"):
            url = settings.base_url
            params = {"start": page_index * 25, "filter": ""}
            if not is_allowed(self.robot_parser, f"{url}?start={page_index * 25}", "Mozilla/5.0"):
                self.logger.warning("Skip disallowed URL: %s", url)
                continue

            html = self._get_list_html(url, params=params)

            page_records = self._parse_list_page(html)
            records.extend(page_records)
            if settings.movie_limit:
                records = records[: settings.movie_limit]
            self.logger.info("Parsed %s items from page %s", len(page_records), page_index + 1)
            if settings.movie_limit and len(records) >= settings.movie_limit:
                break

        self._export(records)
        return records

    def _get_list_html(self, url: str, *, params: dict[str, str]) -> str:
        last_error: Exception | None = None
        for attempt in range(1, settings.max_retries + 1):
            time.sleep(random.uniform(1, 4))
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers={
                        "Referer": "https://movie.douban.com/",
                        "User-Agent": random.choice(settings.headers_pool),
                    },
                    timeout=settings.timeout,
                )
                if response.status_code in {403, 429, 500, 502, 503, 504}:
                    raise RuntimeError(f"status {response.status_code}")
                response.raise_for_status()
                return self._decode_response(response)
            except Exception as exc:
                last_error = exc
                self.logger.warning("List request failed attempt %s/%s: %s", attempt, settings.max_retries, exc)
                if settings.enable_exponential_backoff:
                    time.sleep(min(2 ** attempt, 20))
        raise RuntimeError(f"request failed for {url}") from last_error

    @staticmethod
    def _decode_response(response: requests.Response) -> str:
        if response.headers.get("Content-Encoding") == "br":
            try:
                return brotli.decompress(response.content).decode("utf-8")
            except Exception:
                return response.text
        return response.text

    def _parse_list_page(self, html: str) -> list[MovieRecord]:
        soup = BeautifulSoup(html, "lxml")
        parsed: list[MovieRecord] = []
        for node in soup.select("ol.grid_view > li"):
            title_nodes = node.select(".hd .title")
            other_title = node.select_one(".hd .other")
            score_node = node.select_one(".star .rating_num")
            if score_node is None:
                score_node = node.select_one(".rating_num")
            bd_node = node.select_one(".bd")
            if bd_node is None:
                continue
            vote_text = bd_node.get_text(" ", strip=True)
            detail_url = node.select_one(".hd a")["href"]
            poster_node = node.select_one(".pic img")
            people_node = bd_node.select_one("p:not(.quote)")
            people_info = (
                re.sub(r"\s+", " ", people_node.get_text(" ", strip=True))
                if people_node
                else ""
            )
            list_metadata = parse_list_people_info(people_info)
            quote_node = node.select_one(".inq") or node.select_one(".quote span")
            movie_id_match = re.search(r"/subject/(\d+)/", detail_url)
            votes_match = re.search(r"(\d+)人评价", vote_text)

            title_cn = title_nodes[0].get_text(strip=True) if title_nodes else ""
            title_foreign = ""
            if len(title_nodes) > 1:
                title_foreign = clean_text(title_nodes[1].get_text(strip=True))
            elif other_title:
                title_foreign = clean_text(other_title.get_text(" ", strip=True))

            parsed.append(
                MovieRecord(
                    movie_id=movie_id_match.group(1) if movie_id_match else "",
                    rank=int(node.select_one(".pic em").get_text(strip=True)),
                    title_cn=clean_text(title_cn),
                    title_foreign=title_foreign,
                    score=float(score_node.get_text(strip=True)) if score_node else 0.0,
                    votes=int(votes_match.group(1)) if votes_match else 0,
                    people_info=clean_text(people_info),
                    quote=clean_text(quote_node.get_text(" ", strip=True)) if quote_node else "",
                    detail_url=detail_url,
                    year=list_metadata["year"],
                    genres=list_metadata["genres"],
                    directors=list_metadata["directors"],
                    actors=list_metadata["actors"],
                    country=list_metadata["country"],
                    poster_url=str(poster_node.get("src", "")) if poster_node else "",
                )
            )
        return parsed

    def _export(self, records: list[MovieRecord]) -> None:
        rows = [record.to_dict() for record in records]
        export_json(rows, RAW_DATA_DIR / "top250_list.json")
        export_csv(rows, RAW_DATA_DIR / "top250_list.csv")
        self.logger.info("Exported %s rows to %s", len(rows), Path(RAW_DATA_DIR))
