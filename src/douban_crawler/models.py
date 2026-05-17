from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class MovieRecord:
    movie_id: str
    rank: int
    title_cn: str
    title_foreign: str
    score: float
    votes: int
    people_info: str
    quote: str
    detail_url: str
    year: int | None = None
    runtime: int | None = None
    genres: list[str] = field(default_factory=list)
    imdb_id: str = ""
    imdb_url: str = ""
    imdb_rating: float | None = None
    summary: str = ""
    poster_url: str = ""
    poster_path: str = ""
    # 新增：详情页爬取的属性
    directors: list[str] = field(default_factory=list)
    writers: list[str] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)
    country: str = ""
    language: str = ""
    comments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["genres"] = ",".join(self.genres)
        return payload


@dataclass(slots=True)
class CommentRecord:
    movie_id: str
    user_name: str
    rating_text: str
    comment_time: str
    content: str

    def to_dict(self) -> dict:
        return asdict(self)
