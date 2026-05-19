from __future__ import annotations

from pathlib import Path

import pandas as pd

from douban_crawler.analysis.visualization import Analyzer
from douban_crawler.crawlers.detail_requests import DetailRequestsCrawler
from douban_crawler.crawlers.top250_requests import Top250RequestsCrawler
from douban_crawler.models import CommentRecord, MovieRecord
from douban_crawler.utils import storage as storage_module
from douban_crawler.utils.list_metadata import parse_list_people_info
from douban_crawler.utils.posters import poster_filename
from douban_crawler.utils.storage import SQLiteStore


def test_parse_top250_list_page_extracts_movie_fields() -> None:
    html = """
    <ol class="grid_view">
      <li>
        <div class="pic"><em>1</em></div>
        <div class="hd"><a href="https://movie.douban.com/subject/1292052/">
          <span class="title">肖申克的救赎</span><span class="title">The Shawshank Redemption</span>
        </a></div>
        <div class="bd"><p>导演: 弗兰克·德拉邦特 主演: 蒂姆·罗宾斯</p>
          <div class="star"><span class="rating_num">9.7</span><span>3277146人评价</span></div>
          <p class="quote"><span>希望让人自由。</span></p>
        </div>
      </li>
    </ol>
    """
    crawler = Top250RequestsCrawler.__new__(Top250RequestsCrawler)

    records = crawler._parse_list_page(html)

    assert len(records) == 1
    assert records[0].movie_id == "1292052"
    assert records[0].rank == 1
    assert records[0].score == 9.7
    assert records[0].votes == 3277146
    assert "希望" in records[0].quote


def test_parse_detail_and_comments_extracts_extended_fields() -> None:
    detail_html = """
    <div id="content"><span class="year">(1994)</span></div>
    <div id="mainpic"><img src="https://img.example.com/poster.jpg"></div>
    <div id="info">
      <span>导演</span>: <a rel="v:directedBy">弗兰克·德拉邦特</a><br/>
      <span>编剧</span>: <a>斯蒂芬·金</a><br/>
      <span>主演</span>: <a rel="v:starring">蒂姆·罗宾斯</a><br/>
      <span property="v:genre">剧情</span><span property="v:genre">犯罪</span>
      <span>制片国家/地区:</span> 美国<br/>
      <span>语言:</span> 英语<br/>
      <span>片长:</span> 142分钟<br/>
      <a href="https://www.imdb.com/title/tt0111161/">IMDb</a>
    </div>
    <span property="v:summary"> 银行家安迪的故事。 </span>
    """
    comments_html = """
    <div class="comment-item">
      <span class="comment-info"><a>用户A</a><span class="rating allstar50" title="力荐"></span></span>
      <span class="comment-time" title="2024-01-01 10:00:00"></span>
      <span class="short">非常精彩。</span>
    </div>
    """
    movie = MovieRecord(
        movie_id="1292052",
        rank=1,
        title_cn="肖申克的救赎",
        title_foreign="",
        score=9.7,
        votes=1,
        people_info="",
        quote="",
        detail_url="https://movie.douban.com/subject/1292052/",
    )
    crawler = DetailRequestsCrawler()

    crawler._parse_detail(detail_html, movie)
    crawler._parse_comments(comments_html, movie)

    assert movie.year == 1994
    assert movie.runtime == 142
    assert movie.genres == ["剧情", "犯罪"]
    assert movie.imdb_id == "tt0111161"
    assert movie.poster_url.endswith("poster.jpg")
    assert movie.comments[0]["user"] == "用户A"
    assert movie.comments[0]["rating"] == 5


def test_parse_list_people_info_extracts_metadata() -> None:
    info = (
        "导演: 弗兰克·德拉邦特 Frank Darabont 主演: 蒂姆·罗宾斯 Tim Robbins / "
        "摩根·弗里曼 Morgan Freeman 1994 / 美国 / 犯罪 剧情"
    )

    parsed = parse_list_people_info(info)

    assert parsed["year"] == 1994
    assert parsed["country"] == "美国"
    assert parsed["genres"] == ["犯罪", "剧情"]
    assert parsed["directors"] == ["弗兰克·德拉邦特 Frank Darabont"]
    assert parsed["actors"] == ["蒂姆·罗宾斯 Tim Robbins", "摩根·弗里曼 Morgan Freeman"]


def test_parse_list_people_info_handles_parenthesized_release_year() -> None:
    info = (
        "导演: 万籁鸣 Laiming Wan 主演: 邱岳峰 Yuefeng Qiu / 富润生 Runsheng Fu... "
        "1961(中国大陆) / 1964(中国大陆) / 1978(中国大陆) / 中国大陆 / 剧情 动画 奇幻 古装"
    )

    parsed = parse_list_people_info(info)

    assert parsed["year"] == 1961
    assert parsed["country"] == "中国大陆"
    assert parsed["genres"] == ["剧情", "动画", "奇幻", "古装"]
    assert parsed["actors"] == ["邱岳峰 Yuefeng Qiu", "富润生 Runsheng Fu"]


def test_sqlite_store_saves_extended_movie_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage_module, "RAW_DATA_DIR", tmp_path / "raw")
    store = SQLiteStore(tmp_path / "movies.sqlite3")
    movie = MovieRecord(
        movie_id="1",
        rank=1,
        title_cn="测试电影",
        title_foreign="",
        score=8.8,
        votes=100,
        people_info="导演: A",
        quote="",
        detail_url="https://example.test/movie/1",
        year=2020,
        runtime=120,
        genres=["剧情"],
        imdb_url="https://www.imdb.com/title/tt0000001/",
        imdb_id="tt0000001",
        directors=["导演A"],
        writers=["编剧A"],
        actors=["演员A"],
        country="中国",
        language="汉语普通话",
    )

    store.save_movies([movie])
    store.save_comments([CommentRecord("1", "用户", "5", "2024-01-01", "好看")])

    import sqlite3

    with sqlite3.connect(tmp_path / "movies.sqlite3") as conn:
        row = conn.execute(
            "SELECT title_cn, genres, imdb_url, directors, country, language FROM movies WHERE movie_id='1'"
        ).fetchone()
        comment_count = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    assert row == ("测试电影", "剧情", "https://www.imdb.com/title/tt0000001/", "导演A", "中国", "汉语普通话")
    assert comment_count == 1


def test_visualization_handles_empty_genres() -> None:
    analyzer = Analyzer()
    movies = pd.DataFrame(
        [
            {"movie_id": "1", "title_cn": "A", "rank": 1, "score": 9.0, "votes": 10, "genres": None, "year": None},
            {"movie_id": "2", "title_cn": "B", "rank": 2, "score": 8.0, "votes": 20, "genres": None, "year": None},
        ]
    )

    assert analyzer._genre_distribution(movies) == {}


def test_poster_filename_is_safe() -> None:
    assert poster_filename(1, "肖申克/救赎:*?", "https://img.example.com/a.webp") == "001_肖申克_救赎_.webp"
