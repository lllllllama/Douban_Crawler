from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
LOG_DIR = ROOT_DIR / "logs"
POSTER_DIR = ROOT_DIR / "posters"
OUTPUT_DIR = ROOT_DIR / "output"
COOKIE_FILE = ROOT_DIR / "tmp" / "douban_cookies.json"
DB_FILE = ROOT_DIR / "data" / "douban_movies.sqlite3"


@dataclass(slots=True)
class Settings:
    base_url: str = "https://movie.douban.com/top250"
    detail_delay_range: tuple[float, float] = (1.0, 4.0)
    max_retries: int = 4
    timeout: int = 20
    max_workers: int = 4
    comment_target_count: int = 15
    list_page_count: int = 10
    headers_pool: list[str] = field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        ]
    )
    proxies: list[str] = field(
        default_factory=lambda: [
            item.strip()
            for item in os.getenv("DOUBAN_PROXY_POOL", "").split(",")
            if item.strip()
        ]
    )

    def ensure_directories(self) -> None:
        for path in (
            DATA_DIR,
            RAW_DATA_DIR,
            PROCESSED_DATA_DIR,
            LOG_DIR,
            POSTER_DIR,
            OUTPUT_DIR,
            COOKIE_FILE.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
