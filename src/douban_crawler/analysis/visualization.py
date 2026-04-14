from __future__ import annotations

from pathlib import Path

import jieba
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import seaborn as sns
from snownlp import SnowNLP
from wordcloud import WordCloud

from douban_crawler.config import OUTPUT_DIR, PROCESSED_DATA_DIR, settings


def configure_matplotlib() -> Path | None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    font_candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/msyh.ttf"),
    ]
    for path in font_candidates:
        if path.exists():
            return path
    return None


class Analyzer:
    def __init__(self) -> None:
        settings.ensure_directories()
        self.chart_dir = OUTPUT_DIR / "charts"
        self.chart_dir.mkdir(parents=True, exist_ok=True)
        self.font_path = configure_matplotlib()

    def load_cleaned_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        movies = pd.read_csv(PROCESSED_DATA_DIR / "movies_cleaned.csv")
        comments = pd.read_csv(PROCESSED_DATA_DIR / "comments_cleaned.csv")
        comments["comment_time"] = pd.to_datetime(comments["comment_time"], errors="coerce")
        return movies, comments

    def analyze(self) -> dict[str, object]:
        movies, comments = self.load_cleaned_data()
        summary = {
            "movie_count": int(len(movies)),
            "comment_count": int(len(comments)),
            "top10_movies": self._top10_movies(movies),
            "director_distribution": self._director_distribution(movies),
            "genre_distribution": self._genre_distribution(movies),
            "score_vote_correlation": float(movies["score"].corr(movies["votes"])),
            "sentiment_distribution": self._sentiment_distribution(comments),
        }
        self._plot_score_histogram(movies)
        self._plot_genre_pie(movies)
        self._plot_director_bar(movies)
        self._plot_score_votes_scatter(movies)
        self._plot_comment_trend(comments)
        self._plot_sentiment_pie(comments)
        self._plot_comment_wordcloud(comments)
        self._write_summary(summary)
        return summary

    def _top10_movies(self, movies: pd.DataFrame) -> list[dict]:
        top10 = (
            movies.sort_values(["score", "votes"], ascending=[False, False])
            .head(10)[["rank", "title_cn", "score", "votes"]]
            .to_dict(orient="records")
        )
        return top10

    def _director_distribution(self, movies: pd.DataFrame) -> dict[str, int]:
        directors = (
            movies["people_info"]
            .fillna("")
            .apply(self._extract_director)
            .value_counts()
            .head(10)
            .to_dict()
        )
        return {str(key): int(value) for key, value in directors.items()}

    def _genre_distribution(self, movies: pd.DataFrame) -> dict[str, int]:
        genres = (
            movies["genres"]
            .fillna("")
            .str.split(",")
            .explode()
            .str.strip()
        )
        genres = genres[genres != ""].value_counts().head(10).to_dict()
        return {str(key): int(value) for key, value in genres.items()}

    def _sentiment_distribution(self, comments: pd.DataFrame) -> dict[str, int]:
        if comments.empty:
            return {"positive": 0, "neutral": 0, "negative": 0}

        scores = comments["content"].fillna("").apply(self._score_sentiment)
        labels = scores.apply(
            lambda score: "positive" if score > 0.6 else "negative" if score < 0.4 else "neutral"
        )
        counts = labels.value_counts().to_dict()
        return {
            "positive": int(counts.get("positive", 0)),
            "neutral": int(counts.get("neutral", 0)),
            "negative": int(counts.get("negative", 0)),
        }

    def _plot_score_histogram(self, movies: pd.DataFrame) -> None:
        plt.figure(figsize=(10, 6))
        sns.histplot(movies["score"].dropna(), bins=15, kde=True, color="#2c7fb8")
        plt.title("豆瓣 Top250 评分分布")
        plt.xlabel("评分")
        plt.ylabel("电影数量")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "score_histogram.png", dpi=200)
        plt.close()

    def _plot_genre_pie(self, movies: pd.DataFrame) -> None:
        genre_series = (
            movies["genres"]
            .fillna("")
            .str.split(",")
            .explode()
            .str.strip()
        )
        genre_series = genre_series[genre_series != ""].value_counts().head(8)
        plt.figure(figsize=(8, 8))
        plt.pie(genre_series.values, labels=genre_series.index, autopct="%1.1f%%", startangle=120)
        plt.title("电影类型占比")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "genre_pie.png", dpi=200)
        plt.close()

    def _plot_director_bar(self, movies: pd.DataFrame) -> None:
        director_series = (
            movies["people_info"]
            .fillna("")
            .apply(self._extract_director)
            .value_counts()
            .head(10)
        )
        director_frame = pd.DataFrame(
            {"director": director_series.index, "count": director_series.values}
        )
        plt.figure(figsize=(12, 6))
        sns.barplot(
            data=director_frame,
            x="director",
            y="count",
            hue="director",
            palette="crest",
            legend=False,
        )
        plt.xticks(rotation=35, ha="right")
        plt.title("导演分布 Top10")
        plt.xlabel("导演")
        plt.ylabel("电影数量")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "director_distribution.png", dpi=200)
        plt.close()

    def _plot_score_votes_scatter(self, movies: pd.DataFrame) -> None:
        fig = px.scatter(
            movies,
            x="votes",
            y="score",
            hover_data=["title_cn", "rank", "year"],
            title="评分与评价人数相关性",
        )
        fig.write_html(self.chart_dir / "score_votes_scatter.html")

    def _plot_comment_trend(self, comments: pd.DataFrame) -> None:
        if comments.empty:
            return
        trend = (
            comments.dropna(subset=["comment_time"])
            .assign(comment_date=lambda frame: frame["comment_time"].dt.date)
            .groupby("comment_date")
            .size()
            .reset_index(name="count")
        )
        plt.figure(figsize=(12, 6))
        sns.lineplot(data=trend, x="comment_date", y="count", marker="o")
        plt.title("短评时间趋势")
        plt.xlabel("日期")
        plt.ylabel("短评数量")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "comment_trend.png", dpi=200)
        plt.close()

    def _plot_sentiment_pie(self, comments: pd.DataFrame) -> None:
        distribution = self._sentiment_distribution(comments)
        plt.figure(figsize=(8, 8))
        plt.pie(
            distribution.values(),
            labels=distribution.keys(),
            autopct="%1.1f%%",
            colors=["#4daf4a", "#ffbf00", "#e41a1c"],
        )
        plt.title("短评情感分布")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "sentiment_pie.png", dpi=200)
        plt.close()

    def _plot_comment_wordcloud(self, comments: pd.DataFrame) -> None:
        if comments.empty or self.font_path is None:
            return
        text = " ".join(comments["content"].fillna("").tolist())
        tokens = [token for token in jieba.cut(text) if len(token.strip()) > 1]
        cloud = WordCloud(
            width=1400,
            height=900,
            background_color="white",
            font_path=str(self.font_path),
        ).generate(" ".join(tokens))
        plt.figure(figsize=(12, 8))
        plt.imshow(cloud, interpolation="bilinear")
        plt.axis("off")
        plt.title("热门短评词云")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "comment_wordcloud.png", dpi=200)
        plt.close()

    def _write_summary(self, summary: dict[str, object]) -> None:
        summary_path = OUTPUT_DIR / "analysis_summary.md"
        lines = [
            "# 数据分析摘要",
            "",
            f"- 电影数量：{summary['movie_count']}",
            f"- 短评数量：{summary['comment_count']}",
            f"- 评分与评价人数相关系数：{summary['score_vote_correlation']:.4f}",
            "",
            "## 高分电影 Top10",
        ]
        for row in summary["top10_movies"]:
            lines.append(
                f"- {row['rank']}. {row['title_cn']} | 评分 {row['score']} | 评价人数 {row['votes']}"
            )
        lines.extend(["", "## 导演分布"])
        for key, value in summary["director_distribution"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## 类型分布"])
        for key, value in summary["genre_distribution"].items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## 情感分布"])
        for key, value in summary["sentiment_distribution"].items():
            lines.append(f"- {key}: {value}")
        summary_path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _extract_director(value: str) -> str:
        value = str(value)
        if "导演:" not in value:
            return "未知"
        if "主演:" in value:
            return value.split("导演:", 1)[1].split("主演:", 1)[0].strip()
        return value.split("导演:", 1)[1].split("  ", 1)[0].strip()

    @staticmethod
    def _score_sentiment(text: str) -> float:
        text = str(text).strip()
        if not text:
            return 0.5
        try:
            return float(SnowNLP(text).sentiments)
        except Exception:
            return 0.5
