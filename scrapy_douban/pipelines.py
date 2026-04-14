from __future__ import annotations

from douban_crawler.models import CommentRecord, MovieRecord
from douban_crawler.utils.storage import SQLiteStore


class SQLiteExportPipeline:
    def __init__(self) -> None:
        self.store = SQLiteStore()
        self.movies: list[MovieRecord] = []
        self.comments: list[CommentRecord] = []

    def process_item(self, item, spider):
        item_type = item.get("_item_type")
        if item_type == "movie":
            self.movies.append(
                MovieRecord(
                    movie_id=item["movie_id"],
                    rank=int(item["rank"]),
                    title_cn=item["title_cn"],
                    title_foreign=item.get("title_foreign", ""),
                    score=float(item["score"]),
                    votes=int(item["votes"]),
                    people_info=item.get("people_info", ""),
                    quote=item.get("quote", ""),
                    detail_url=item["detail_url"],
                    year=item.get("year"),
                    runtime=item.get("runtime", ""),
                    genres=list(item.get("genres", [])),
                    imdb_id=item.get("imdb_id", ""),
                    imdb_rating=item.get("imdb_rating"),
                    summary=item.get("summary", ""),
                    poster_url=item.get("poster_url", ""),
                    poster_path=item.get("poster_path", ""),
                )
            )
        elif item_type == "comment":
            self.comments.append(
                CommentRecord(
                    movie_id=item["movie_id"],
                    user_name=item["user_name"],
                    rating_text=item["rating_text"],
                    comment_time=item["comment_time"],
                    content=item["content"],
                )
            )
        return item

    def close_spider(self, spider):
        if self.movies:
            self.store.save_movies(self.movies)
        if self.comments:
            self.store.save_comments(self.comments)
