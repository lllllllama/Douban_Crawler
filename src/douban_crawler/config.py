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
    detail_delay_range: tuple[float, float] = (1.0, 3.0)
    timeout: tuple[float, float] = (5.0, 20.0)
    max_retries: int = 3
    max_workers: int = int(os.getenv("DOUBAN_MAX_WORKERS", "4"))
    comment_target_count: int = 12
    list_page_count: int = int(os.getenv("DOUBAN_LIST_PAGE_COUNT", "10"))
    movie_limit: int = int(os.getenv("DOUBAN_MOVIE_LIMIT", "0"))
    cookie_wait_seconds: int = 8
    enable_exponential_backoff: bool = True
    headers_pool: list[str] = field(
        default_factory=lambda: [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
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
        for path in (DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, LOG_DIR, POSTER_DIR, OUTPUT_DIR, COOKIE_FILE.parent):
            path.mkdir(parents=True, exist_ok=True)

settings = Settings()
