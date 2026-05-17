import json
from _bootstrap import ROOT_DIR  # noqa: F401
from douban_crawler.crawlers.detail_requests import DetailRequestsCrawler
from douban_crawler.crawlers.top250_requests import Top250RequestsCrawler

if __name__ == "__main__":
    # 1. 直接读取 cookies.json 文件
    cookie_file = ROOT_DIR / "data" / "cookies.json"
    if not cookie_file.exists():
        raise FileNotFoundError(f"请先在 {cookie_file} 中配置豆瓣 Cookie")

    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    print("Loaded cookies:", cookies)

    # 2. 创建爬虫实例
    list_crawler = Top250RequestsCrawler()
    detail_crawler = DetailRequestsCrawler()

    # 3. 将 Cookie 注入到爬虫的会话对象中
    list_crawler.session.cookies.update(cookies)
    detail_crawler.cookies = cookies  # DetailRequestsCrawler 中使用 self.cookies

    # 4. 开始爬取
    movies = list_crawler.crawl()
    detail_crawler.enrich(movies)
