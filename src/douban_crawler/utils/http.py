from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any
import requests
from requests.adapters import HTTPAdapter

from douban_crawler.config import settings
from douban_crawler.utils.logging_utils import configure_logger

@dataclass(slots=True)
class RequestOptions:
    use_delay: bool = True
    allow_retry_statuses: tuple[int, ...] = (403, 429, 500, 502, 503, 504)

class RotatingSession:
    def __init__(self) -> None:
        self.logger = configure_logger()
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(pool_connections=10, pool_maxsize=20))
        self.session.mount("http://", HTTPAdapter(pool_connections=10, pool_maxsize=20))
        self.blacklisted_proxies = set()

    def _build_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(settings.headers_pool),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://movie.douban.com/",
        }

    def _pick_proxy(self) -> dict[str, str] | None:
        if not settings.proxies:
            return None
        available = [p for p in settings.proxies if p not in self.blacklisted_proxies]
        if not available:
            return None
        proxy = random.choice(available)
        return {"http": proxy, "https": proxy}

    def get(self, url: str, *, params: dict[str, Any] | None = None, cookies: dict[str, str] | None = None, options: RequestOptions | None = None) -> requests.Response:
        options = options or RequestOptions()
        last_error = None

        for attempt in range(1, settings.max_retries + 1):
            if options.use_delay:
                delay = random.uniform(*settings.detail_delay_range)
                time.sleep(delay)

            try:
                proxy = self._pick_proxy()
                resp = self.session.get(
                    url,
                    params=params,
                    headers=self._build_headers(),
                    timeout=settings.timeout,
                    proxies=proxy,
                    cookies=cookies
                )
                if resp.status_code in options.allow_retry_statuses:
                    last_error = RuntimeError(f"status {resp.status_code}")
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                last_error = e
                proxy = self._pick_proxy()
                if proxy:
                    self.blacklisted_proxies.add(next(iter(proxy.values())))

        raise RuntimeError(f"request failed for {url}") from last_error
