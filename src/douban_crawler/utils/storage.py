from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from douban_crawler.config import DB_FILE, RAW_DATA_DIR
from douban_crawler.models import CommentRecord, MovieRecord
from douban_crawler.utils.exporters import export_csv, export_json


class SQLiteStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS movies (
                    movie_id TEXT PRIMARY KEY,
                    rank INTEGER NOT NULL,
                    title_cn TEXT,
                    title_foreign TEXT,
                    score REAL,
                    votes INTEGER,
                    people_info TEXT,
                    quote TEXT,
                    detail_url TEXT,
                    year INTEGER,
                    runtime TEXT,
                    genres TEXT,
                    imdb_url TEXT,
                    imdb_id TEXT,
                    imdb_rating REAL,
                    summary TEXT,
                    directors TEXT,
                    writers TEXT,
                    actors TEXT,
                    country TEXT,
                    language TEXT,
                    poster_url TEXT,
                    poster_path TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    movie_id TEXT NOT NULL,
                    user_name TEXT,
                    rating_text TEXT,
                    comment_time TEXT,
                    content TEXT,
                    FOREIGN KEY (movie_id) REFERENCES movies(movie_id)
                )
                """
            )
            self._ensure_movie_columns(conn)
            conn.commit()

    def _ensure_movie_columns(self, conn: sqlite3.Connection) -> None:
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(movies)").fetchall()
        }
        desired = {
            "imdb_url": "TEXT",
            "directors": "TEXT",
            "writers": "TEXT",
            "actors": "TEXT",
            "country": "TEXT",
            "language": "TEXT",
            "poster_url": "TEXT",
            "poster_path": "TEXT",
        }
        for column, column_type in desired.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE movies ADD COLUMN {column} {column_type}")

    def save_movies(self, movies: Iterable[MovieRecord]) -> None:
        rows = [movie.to_dict() for movie in movies]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO movies (
                    movie_id, rank, title_cn, title_foreign, score, votes, people_info,
                    quote, detail_url, year, runtime, genres, imdb_url, imdb_id, imdb_rating,
                    summary, directors, writers, actors, country, language, poster_url,
                    poster_path
                ) VALUES (
                    :movie_id, :rank, :title_cn, :title_foreign, :score, :votes, :people_info,
                    :quote, :detail_url, :year, :runtime, :genres, :imdb_url, :imdb_id,
                    :imdb_rating, :summary, :directors, :writers, :actors, :country,
                    :language, :poster_url, :poster_path
                )
                """,
                rows,
            )
            conn.commit()

        export_json(rows, RAW_DATA_DIR / "movies_full.json")
        export_csv(rows, RAW_DATA_DIR / "movies_full.csv")

    def save_comments(self, comments: Iterable[CommentRecord]) -> None:
        rows = [comment.to_dict() for comment in comments]
        movie_ids = sorted({row["movie_id"] for row in rows})
        with self._connect() as conn:
            for movie_id in movie_ids:
                conn.execute("DELETE FROM comments WHERE movie_id = ?", (movie_id,))
            conn.executemany(
                """
                INSERT INTO comments (movie_id, user_name, rating_text, comment_time, content)
                VALUES (:movie_id, :user_name, :rating_text, :comment_time, :content)
                """,
                rows,
            )
            conn.commit()

        export_json(rows, RAW_DATA_DIR / "comments.json")
        export_csv(rows, RAW_DATA_DIR / "comments.csv")
