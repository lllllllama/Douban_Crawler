from __future__ import annotations

from douban_crawler.config import settings
from douban_crawler.utils.logging_utils import configure_logger


def main() -> None:
    settings.ensure_directories()
    logger = configure_logger()
    logger.info("Project bootstrap complete. Implement crawl steps via scripts/*.py.")


if __name__ == "__main__":
    main()
