from __future__ import annotations

from dataclasses import asdict, dataclass, field


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
    runtime: str = ""
    genres: list[str] = field(default_factory=list)
    imdb_id: str = ""
    imdb_rating: float | None = None
    summary: str = ""
    poster_url: str = ""
    poster_path: str = ""

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
