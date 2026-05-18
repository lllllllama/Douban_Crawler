from __future__ import annotations

import sqlite3

import pandas as pd

from douban_crawler.config import DB_FILE, PROCESSED_DATA_DIR, settings


class DataCleaner:
    def __init__(self) -> None:
        settings.ensure_directories()

    def clean(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        with sqlite3.connect(DB_FILE) as conn:
            movies = pd.read_sql_query("SELECT * FROM movies", conn)
            comments = pd.read_sql_query("SELECT * FROM comments", conn)

        if movies.empty:
            raise RuntimeError("movies table is empty, run crawler first")

        movies = movies.replace({"": pd.NA}).drop_duplicates(subset=["movie_id"]).copy()
        comments = comments.replace({"": pd.NA}).drop_duplicates(
            subset=["movie_id", "user_name", "comment_time", "content"]
        ).copy()

        for column in ["rank", "score", "votes", "year", "imdb_rating"]:
            if column in movies.columns:
                movies[column] = pd.to_numeric(movies[column], errors="coerce")
        if "runtime" in movies.columns:
            movies["runtime"] = (
                movies["runtime"]
                .astype("string")
                .str.extract(r"(\d+)", expand=False)
                .pipe(pd.to_numeric, errors="coerce")
            )

        if "comment_time" in comments.columns:
            comments["comment_time"] = pd.to_datetime(
                comments["comment_time"], errors="coerce"
            )

        movies.to_csv(PROCESSED_DATA_DIR / "movies_cleaned.csv", index=False, encoding="utf-8-sig")
        comments.to_csv(PROCESSED_DATA_DIR / "comments_cleaned.csv", index=False, encoding="utf-8-sig")
        movies.to_json(
            PROCESSED_DATA_DIR / "movies_cleaned.json",
            orient="records",
            force_ascii=False,
            indent=2,
        )
        comments.to_json(
            PROCESSED_DATA_DIR / "comments_cleaned.json",
            orient="records",
            force_ascii=False,
            indent=2,
            date_format="iso",
        )
        return movies, comments
