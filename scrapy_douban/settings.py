from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

BOT_NAME = "scrapy_douban"

SPIDER_MODULES = ["scrapy_douban.spiders"]
NEWSPIDER_MODULE = "scrapy_douban.spiders"

ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 1.5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 4
RETRY_TIMES = 4

DOWNLOADER_MIDDLEWARES = {
    "scrapy_douban.middlewares.DoubanHeaderMiddleware": 543,
    "scrapy_douban.middlewares.DoubanCookieMiddleware": 544,
}

ITEM_PIPELINES = {
    "scrapy_douban.pipelines.SQLiteExportPipeline": 300,
}

LOG_LEVEL = "INFO"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
