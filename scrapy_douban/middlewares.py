from __future__ import annotations

from urllib.parse import urlparse

from douban_crawler.config import settings
from douban_crawler.selenium.cookie_bootstrap import DoubanCookieBootstrapper


class DoubanHeaderMiddleware:
    def process_request(self, request, spider):
        request.headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.8"
        request.headers["Accept"] = (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        )
        request.headers["Referer"] = "https://movie.douban.com/"
        request.headers["User-Agent"] = spider.pick_user_agent()
        proxy = spider.pick_proxy()
        if proxy:
            request.meta["proxy"] = proxy
        return None


class DoubanCookieMiddleware:
    def __init__(self) -> None:
        self.bootstrapper = DoubanCookieBootstrapper()
        self.cookies: dict[str, str] = {}

    def process_request(self, request, spider):
        parsed = urlparse(request.url)
        if "movie.douban.com" not in parsed.netloc:
            return None
        if "/subject/" not in parsed.path:
            return None

        if not self.cookies:
            self.cookies = self.bootstrapper.fetch(request.url)
        request.headers["Cookie"] = "; ".join(
            f"{name}={value}" for name, value in self.cookies.items()
        )
        return None
