from _bootstrap import ROOT_DIR  # noqa: F401
from douban_crawler.crawlers.detail_requests import DetailRequestsCrawler
from douban_crawler.crawlers.top250_requests import Top250RequestsCrawler


if __name__ == "__main__":
    list_crawler = Top250RequestsCrawler()
    detail_crawler = DetailRequestsCrawler()
    movies = list_crawler.crawl()
    detail_crawler.enrich(movies)
