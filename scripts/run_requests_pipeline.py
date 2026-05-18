from _bootstrap import ROOT_DIR  # noqa: F401
from douban_crawler.config import settings
from douban_crawler.crawlers.detail_requests import DetailRequestsCrawler
from douban_crawler.crawlers.top250_requests import Top250RequestsCrawler
from douban_crawler.models import CommentRecord
from douban_crawler.selenium.cookie_bootstrap import DoubanCookieBootstrapper
from douban_crawler.utils.storage import SQLiteStore

if __name__ == "__main__":
    settings.ensure_directories()

    # 1. 统一 Cookie 来源：优先复用 tmp/douban_cookies.json，不存在时用 Selenium 获取。
    cookies = DoubanCookieBootstrapper().load_or_fetch(settings.base_url)

    # 2. 创建爬虫实例
    list_crawler = Top250RequestsCrawler()
    detail_crawler = DetailRequestsCrawler()

    # 3. 将 Cookie 注入到爬虫的会话对象中
    list_crawler.session.cookies.update(cookies)
    detail_crawler.cookies = cookies
    detail_crawler.session.cookies.update(cookies)

    # 4. 开始爬取、补全详情并持久化
    movies = list_crawler.crawl()
    detail_crawler.enrich(movies)

    comments: list[CommentRecord] = []
    for movie in movies:
        for item in movie.comments:
            comments.append(
                CommentRecord(
                    movie_id=movie.movie_id,
                    user_name=str(item.get("user", "")),
                    rating_text=str(item.get("rating", "")),
                    comment_time=str(item.get("time", "")),
                    content=str(item.get("content", "")),
                )
            )

    store = SQLiteStore()
    store.save_movies(movies)
    store.save_comments(comments)
    print(f"Saved {len(movies)} movies and {len(comments)} comments to database.")
