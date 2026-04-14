from __future__ import annotations

import json
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from douban_crawler.config import COOKIE_FILE, settings
from douban_crawler.utils.logging_utils import configure_logger


class DoubanCookieBootstrapper:
    def __init__(self, cookie_file: Path | None = None) -> None:
        self.cookie_file = cookie_file or COOKIE_FILE
        self.logger = configure_logger()

    def load_or_fetch(self, target_url: str) -> dict[str, str]:
        if self.cookie_file.exists():
            try:
                data = json.loads(self.cookie_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data:
                    return {str(k): str(v) for k, v in data.items()}
            except json.JSONDecodeError:
                self.logger.warning("Cookie file is invalid, regenerating: %s", self.cookie_file)

        cookies = self.fetch(target_url)
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        self.cookie_file.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return cookies

    def fetch(self, target_url: str) -> dict[str, str]:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1600,1200")

        driver = webdriver.Chrome(options=options)
        try:
            driver.get(target_url)
            time.sleep(settings.cookie_wait_seconds)
            cookies = {item["name"]: item["value"] for item in driver.get_cookies()}
            if not cookies:
                raise RuntimeError("failed to obtain douban cookies via selenium")
            self.logger.info("Bootstrapped %s cookies from Selenium", len(cookies))
            return cookies
        finally:
            driver.quit()
