from __future__ import annotations

import scrapy


class MovieItem(scrapy.Item):
    _item_type = scrapy.Field()
    movie_id = scrapy.Field()
    rank = scrapy.Field()
    title_cn = scrapy.Field()
    title_foreign = scrapy.Field()
    score = scrapy.Field()
    votes = scrapy.Field()
    people_info = scrapy.Field()
    quote = scrapy.Field()
    detail_url = scrapy.Field()
    year = scrapy.Field()
    runtime = scrapy.Field()
    genres = scrapy.Field()
    imdb_id = scrapy.Field()
    imdb_rating = scrapy.Field()
    summary = scrapy.Field()
    poster_url = scrapy.Field()
    poster_path = scrapy.Field()


class CommentItem(scrapy.Item):
    _item_type = scrapy.Field()
    movie_id = scrapy.Field()
    user_name = scrapy.Field()
    rating_text = scrapy.Field()
    comment_time = scrapy.Field()
    content = scrapy.Field()
