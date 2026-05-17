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

            # 随机延迟，避免请求过快
            time.sleep(random.uniform(3, 6))

            response = self.session.get(
                url,
                params=params,
                headers={'Referer': 'https://movie.douban.com/'}
            )

            # 第一页时保存调试信息
            if page_index == 0:
                # 保存原始二进制响应
                with open("debug_page1_raw.bin", "wb") as f:
                    f.write(response.content)
                # 保存响应头信息
                with open("debug_headers.txt", "w", encoding="utf-8") as f:
                    f.write(f"Status: {response.status_code}\n")
                    for k, v in response.headers.items():
                        f.write(f"{k}: {v}\n")
                self.logger.info("Saved raw response to debug_page1_raw.bin and headers to debug_headers.txt")

            if response.status_code != 200:
                self.logger.error(f"请求失败，状态码：{response.status_code}")
                continue

            # 处理 Brotli 压缩（关键修复）
            # 安全处理 Brotli 压缩
            if response.headers.get('Content-Encoding') == 'br':
                try:
                    html = brotli.decompress(response.content).decode('utf-8')
                except Exception:
                    # 如果解压失败，说明 content 可能已被 requests 自动解压，直接使用 text
                    html = response.text
            else:
                html = response.text

            # 第一页时保存解压后的HTML用于调试
            if page_index == 0:
                with open("debug_page1.html", "w", encoding="utf-8") as f:
                    f.write(html)
                self.logger.info("Saved decompressed HTML to debug_page1.html")
                # 打印前500字符预览
                print("Response preview:", html[:500])

            page_records = self._parse_list_page(html)
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
                )
            )
        return parsed

    def _export(self, records: list[MovieRecord]) -> None:
        rows = [record.to_dict() for record in records]
        export_json(rows, RAW_DATA_DIR / "top250_list.json")
        export_csv(rows, RAW_DATA_DIR / "top250_list.csv")
        self.logger.info("Exported %s rows to %s", len(rows), Path(RAW_DATA_DIR))
