from _bootstrap import ROOT_DIR  # noqa: F401
from douban_crawler.crawlers.top250_requests import Top250RequestsCrawler


if __name__ == "__main__":
    crawler = Top250RequestsCrawler()
    crawler.crawl()
