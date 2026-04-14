from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

import requests

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

    def _build_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(settings.headers_pool),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://movie.douban.com/",
        }

    def _pick_proxy(self) -> dict[str, str] | None:
        if not settings.proxies:
            return None
        proxy = random.choice(settings.proxies)
        return {"http": proxy, "https": proxy}

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        cookies: dict[str, str] | None = None,
        options: RequestOptions | None = None,
    ) -> requests.Response:
        options = options or RequestOptions()
        last_error: Exception | None = None

        for attempt in range(1, settings.max_retries + 1):
            if options.use_delay:
                delay = random.uniform(*settings.detail_delay_range)
                self.logger.info("Sleep %.2fs before requesting %s", delay, url)
                time.sleep(delay)

            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=self._build_headers(),
                    timeout=settings.timeout,
                    proxies=self._pick_proxy(),
                    cookies=cookies,
                )
                if response.status_code in options.allow_retry_statuses:
                    self.logger.warning(
                        "Retry %s/%s for %s due to status=%s",
                        attempt,
                        settings.max_retries,
                        url,
                        response.status_code,
                    )
                    last_error = RuntimeError(f"unexpected status {response.status_code}")
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                self.logger.warning(
                    "Retry %s/%s for %s due to %s",
                    attempt,
                    settings.max_retries,
                    url,
                    exc,
                )

        raise RuntimeError(f"request failed for {url}") from last_error
