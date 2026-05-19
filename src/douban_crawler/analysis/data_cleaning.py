from __future__ import annotations

import sqlite3

import pandas as pd

from douban_crawler.config import DB_FILE, PROCESSED_DATA_DIR, settings
from douban_crawler.utils.list_metadata import parse_list_people_info


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
        movies = self._fill_list_metadata(movies)

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

    def _fill_list_metadata(self, movies: pd.DataFrame) -> pd.DataFrame:
        if movies.empty or "people_info" not in movies.columns:
            return movies

        for column in ["year", "genres", "directors", "actors", "country"]:
            if column not in movies.columns:
                movies[column] = pd.NA

        for index, people_info in movies["people_info"].items():
            parsed = parse_list_people_info(people_info)
            self._fill_scalar(movies, index, "year", parsed["year"])
            self._fill_scalar(movies, index, "country", parsed["country"])
            self._fill_sequence(movies, index, "genres", parsed["genres"])
            self._fill_sequence(movies, index, "directors", parsed["directors"])
            self._fill_sequence(movies, index, "actors", parsed["actors"])

        return movies

    @staticmethod
    def _fill_scalar(movies: pd.DataFrame, index: int, column: str, value: object) -> None:
        if value in (None, ""):
            return
        current = movies.at[index, column]
        if pd.isna(current) or str(current).strip() == "":
            movies.at[index, column] = value

    @staticmethod
    def _fill_sequence(movies: pd.DataFrame, index: int, column: str, values: list[str]) -> None:
        if not values:
            return
        current = movies.at[index, column]
        if pd.isna(current) or str(current).strip() == "":
            movies.at[index, column] = ",".join(values)
