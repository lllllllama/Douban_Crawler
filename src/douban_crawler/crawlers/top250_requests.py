from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from tqdm import tqdm

from douban_crawler.config import RAW_DATA_DIR, settings
from douban_crawler.models import MovieRecord
from douban_crawler.utils.exporters import export_csv, export_json
from douban_crawler.utils.http import RequestOptions, RotatingSession
from douban_crawler.utils.logging_utils import configure_logger
from douban_crawler.utils.robots import build_robot_parser, is_allowed


class Top250RequestsCrawler:
    def __init__(self) -> None:
        settings.ensure_directories()
        self.logger = configure_logger()
        self.session = RotatingSession()
        self.robot_parser = build_robot_parser(settings.base_url)

    def crawl(self) -> list[MovieRecord]:
        records: list[MovieRecord] = []
        for page_index in tqdm(range(settings.list_page_count), desc="list-pages"):
            url = settings.base_url
            params = {"start": page_index * 25, "filter": ""}
            if not is_allowed(self.robot_parser, f"{url}?start={page_index * 25}", "Mozilla/5.0"):
                self.logger.warning("Skip disallowed URL: %s", url)
                continue

            response = self.session.get(url, params=params, options=RequestOptions())
            page_records = self._parse_list_page(response.text)
            records.extend(page_records)
            self.logger.info("Parsed %s items from page %s", len(page_records), page_index + 1)

        self._export(records)
        return records

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
            people_node = bd_node.select_one("p:not(.quote)")
            people_info = (
                re.sub(r"\s+", " ", people_node.get_text(" ", strip=True))
                if people_node
                else ""
            )
            quote_node = node.select_one(".inq") or node.select_one(".quote span")
            movie_id_match = re.search(r"/subject/(\d+)/", detail_url)
            votes_match = re.search(r"(\d+)人评价", vote_text)

            title_cn = title_nodes[0].get_text(strip=True) if title_nodes else ""
            title_foreign = ""
            if len(title_nodes) > 1:
                title_foreign = self._clean_text(title_nodes[1].get_text(strip=True))
            elif other_title:
                title_foreign = self._clean_text(other_title.get_text(" ", strip=True))

            parsed.append(
                MovieRecord(
                    movie_id=movie_id_match.group(1) if movie_id_match else "",
                    rank=int(node.select_one(".pic em").get_text(strip=True)),
                    title_cn=self._clean_text(title_cn),
                    title_foreign=title_foreign,
                    score=float(score_node.get_text(strip=True)) if score_node else 0.0,
                    votes=int(votes_match.group(1)) if votes_match else 0,
                    people_info=self._clean_text(people_info),
                    quote=self._clean_text(quote_node.get_text(" ", strip=True)) if quote_node else "",
                    detail_url=detail_url,
                )
            )
        return parsed

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip(" /")

    def _export(self, records: list[MovieRecord]) -> None:
        rows = [record.to_dict() for record in records]
        export_json(rows, RAW_DATA_DIR / "top250_list.json")
        export_csv(rows, RAW_DATA_DIR / "top250_list.csv")
        self.logger.info("Exported %s rows to %s", len(rows), Path(RAW_DATA_DIR))
