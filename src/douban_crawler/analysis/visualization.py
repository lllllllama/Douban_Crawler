from __future__ import annotations

import math
import re
from html import escape
from pathlib import Path
from typing import Any

import jieba
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import seaborn as sns
from snownlp import SnowNLP
from wordcloud import WordCloud

from douban_crawler.config import OUTPUT_DIR, POSTER_DIR, PROCESSED_DATA_DIR, ROOT_DIR, settings


PREMIUM_COLORS: dict[str, str] = {
    "bg": "#05070D",
    "bg_2": "#0B1020",
    "panel": "#101827",
    "panel_2": "#151F32",
    "gold": "#D6A84F",
    "gold_2": "#F2D27C",
    "blue": "#4AB3FF",
    "cyan": "#62E4FF",
    "green": "#56D39A",
    "red": "#FF6B6B",
    "muted": "#9BA8BA",
    "text": "#F6F0E6",
    "line": "rgba(214, 168, 79, 0.24)",
}

PLOTLY_COLORWAY = [
    PREMIUM_COLORS["gold"],
    PREMIUM_COLORS["blue"],
    PREMIUM_COLORS["green"],
    "#C87BFF",
    "#FF8A65",
    PREMIUM_COLORS["cyan"],
    PREMIUM_COLORS["gold_2"],
]

MOVIE_FIELDS = [
    "movie_id",
    "rank",
    "title_cn",
    "title_foreign",
    "score",
    "votes",
    "people_info",
    "quote",
    "detail_url",
    "year",
    "runtime",
    "genres",
    "imdb_id",
    "imdb_rating",
    "summary",
    "poster_url",
    "poster_path",
]

COMMENT_FIELDS = ["id", "movie_id", "user_name", "rating_text", "comment_time", "content"]

QUALITY_FIELDS = [
    ("movie_id", "电影ID"),
    ("rank", "排名"),
    ("title_cn", "中文片名"),
    ("score", "评分"),
    ("votes", "评价人数"),
    ("detail_url", "详情链接"),
    ("year", "年份"),
    ("genres", "类型"),
    ("poster_path", "海报"),
]


def configure_matplotlib() -> Path | None:
    """Configure a dark cinema theme for all static chart output."""
    plt.rcParams.update(
        {
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Arial Unicode MS",
                "DejaVu Sans",
            ],
            "axes.unicode_minus": False,
            "figure.facecolor": PREMIUM_COLORS["bg"],
            "savefig.facecolor": PREMIUM_COLORS["bg"],
            "axes.facecolor": PREMIUM_COLORS["panel"],
            "axes.edgecolor": "#2A3448",
            "axes.labelcolor": PREMIUM_COLORS["muted"],
            "xtick.color": PREMIUM_COLORS["muted"],
            "ytick.color": PREMIUM_COLORS["muted"],
            "text.color": PREMIUM_COLORS["text"],
            "grid.color": "#263247",
            "grid.alpha": 0.35,
            "figure.dpi": 140,
            "savefig.dpi": 220,
        }
    )
    sns.set_theme(
        style="darkgrid",
        rc={
            "figure.facecolor": PREMIUM_COLORS["bg"],
            "axes.facecolor": PREMIUM_COLORS["panel"],
            "axes.edgecolor": "#2A3448",
            "grid.color": "#263247",
            "text.color": PREMIUM_COLORS["text"],
            "axes.labelcolor": PREMIUM_COLORS["muted"],
            "xtick.color": PREMIUM_COLORS["muted"],
            "ytick.color": PREMIUM_COLORS["muted"],
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Arial Unicode MS",
                "DejaVu Sans",
            ],
        },
    )

    font_candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/msyh.ttf"),
    ]
    for path in font_candidates:
        if path.exists():
            return path
    return None


def apply_premium_plotly_theme(fig: go.Figure, title: str | None = None) -> go.Figure:
    """Apply the unified Premium Dark Cinema Dashboard style to Plotly figures."""
    fig.update_layout(
        template="plotly_dark",
        title={
            "text": title,
            "x": 0.02,
            "xanchor": "left",
            "font": {"size": 20, "color": PREMIUM_COLORS["text"]},
        }
        if title
        else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,12,22,0.88)",
        font={"family": "Microsoft YaHei, Segoe UI, Arial, sans-serif", "color": PREMIUM_COLORS["text"]},
        colorway=PLOTLY_COLORWAY,
        margin={"l": 58, "r": 32, "t": 70 if title else 36, "b": 52},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "bgcolor": "rgba(5,7,13,0.35)",
            "bordercolor": PREMIUM_COLORS["line"],
            "borderwidth": 1,
        },
        hoverlabel={
            "bgcolor": PREMIUM_COLORS["panel_2"],
            "bordercolor": PREMIUM_COLORS["gold"],
            "font": {"color": PREMIUM_COLORS["text"]},
        },
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.10)",
        zerolinecolor="rgba(214,168,79,0.32)",
        linecolor="rgba(214,168,79,0.32)",
        tickfont={"color": PREMIUM_COLORS["muted"]},
        title_font={"color": PREMIUM_COLORS["muted"]},
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.10)",
        zerolinecolor="rgba(214,168,79,0.32)",
        linecolor="rgba(214,168,79,0.32)",
        tickfont={"color": PREMIUM_COLORS["muted"]},
        title_font={"color": PREMIUM_COLORS["muted"]},
    )
    return fig


class Analyzer:
    def __init__(self) -> None:
        settings.ensure_directories()
        self.chart_dir = OUTPUT_DIR / "charts"
        self.chart_dir.mkdir(parents=True, exist_ok=True)
        self.font_path = configure_matplotlib()

    def load_cleaned_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        movie_path = PROCESSED_DATA_DIR / "movies_cleaned.csv"
        comment_path = PROCESSED_DATA_DIR / "comments_cleaned.csv"
        movies = pd.read_csv(movie_path) if movie_path.exists() else pd.DataFrame(columns=MOVIE_FIELDS)
        comments = (
            pd.read_csv(comment_path) if comment_path.exists() else pd.DataFrame(columns=COMMENT_FIELDS)
        )
        return self._prepare_movies(movies), self._prepare_comments(comments)

    def analyze(self) -> dict[str, object]:
        movies, comments = self.load_cleaned_data()
        correlation = self._score_vote_correlation(movies)
        summary: dict[str, object] = {
            "movie_count": int(len(movies)),
            "comment_count": int(len(comments)),
            "top10_movies": self._top10_movies(movies),
            "director_distribution": self._director_distribution(movies),
            "genre_distribution": self._genre_distribution(movies),
            "score_vote_correlation": correlation,
            "sentiment_distribution": self._sentiment_distribution(comments),
            "field_coverage": self._field_coverage(movies),
            "field_coverage_rate": self._field_coverage_rate(movies),
        }
        self._plot_score_histogram(movies)
        self._plot_genre_pie(movies)
        self._plot_director_bar(movies)
        self._plot_score_votes_scatter(movies)
        self._plot_comment_trend(comments)
        self._plot_sentiment_pie(comments)
        self._plot_comment_wordcloud(comments)
        self._plot_top_movies_bar(movies)
        self._plot_genre_year_heatmap(movies)
        self._plot_sentiment_by_movie(movies, comments)
        self._write_interactive_dashboard(movies, comments, summary)
        self._write_data_quality_report(movies, comments)
        self._write_summary(summary)
        return summary

    def _prepare_movies(self, movies: pd.DataFrame) -> pd.DataFrame:
        frame = movies.copy()
        for column in MOVIE_FIELDS:
            if column not in frame.columns:
                frame[column] = pd.NA
        for column in ["rank", "score", "votes", "year", "runtime", "imdb_rating"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        for column in [
            "movie_id",
            "title_cn",
            "title_foreign",
            "people_info",
            "quote",
            "detail_url",
            "genres",
            "summary",
            "poster_url",
            "poster_path",
        ]:
            frame[column] = frame[column].astype("string")
        return frame

    def _prepare_comments(self, comments: pd.DataFrame) -> pd.DataFrame:
        frame = comments.copy()
        for column in COMMENT_FIELDS:
            if column not in frame.columns:
                frame[column] = pd.NA
        frame["comment_time"] = pd.to_datetime(frame["comment_time"], errors="coerce")
        frame["content"] = frame["content"].astype("string")
        return frame

    def _top10_movies(self, movies: pd.DataFrame) -> list[dict[str, Any]]:
        if movies.empty:
            return []
        top10 = (
            movies.sort_values(["score", "votes"], ascending=[False, False], na_position="last")
            .head(10)[["rank", "title_cn", "score", "votes"]]
            .fillna("")
            .to_dict(orient="records")
        )
        return top10

    def _director_distribution(self, movies: pd.DataFrame) -> dict[str, int]:
        if movies.empty or "people_info" not in movies.columns:
            return {}
        directors = (
            movies["people_info"]
            .fillna("")
            .apply(self._extract_director)
            .replace("", "未知")
            .value_counts()
            .head(10)
            .to_dict()
        )
        return {str(key): int(value) for key, value in directors.items() if str(key).strip()}

    def _genre_distribution(self, movies: pd.DataFrame) -> dict[str, int]:
        genres = self._explode_genres(movies)
        if genres.empty:
            return {}
        return {str(key): int(value) for key, value in genres.value_counts().head(10).to_dict().items()}

    def _sentiment_distribution(self, comments: pd.DataFrame) -> dict[str, int]:
        if comments.empty or "content" not in comments.columns:
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
        scores = pd.to_numeric(movies.get("score"), errors="coerce").dropna()
        if scores.empty:
            self._save_placeholder("score_histogram.png", "评分分布", "当前没有可用评分数据")
            return
        plt.figure(figsize=(11, 6.2))
        sns.histplot(scores, bins=15, kde=True, color=PREMIUM_COLORS["gold"], edgecolor="#2B3344")
        plt.title("豆瓣 Top250 评分分布", fontsize=18, weight="bold", pad=18)
        plt.xlabel("评分")
        plt.ylabel("电影数量")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "score_histogram.png", dpi=220)
        plt.close()

    def _plot_genre_pie(self, movies: pd.DataFrame) -> None:
        genre_series = self._explode_genres(movies).value_counts().head(8)
        if genre_series.empty:
            self._save_placeholder("genre_pie.png", "电影类型占比", "当前样本暂无类型字段")
            return
        plt.figure(figsize=(8, 8))
        wedges, texts, autotexts = plt.pie(
            genre_series.values,
            labels=genre_series.index,
            autopct="%1.1f%%",
            startangle=120,
            colors=PLOTLY_COLORWAY,
            wedgeprops={"linewidth": 1.1, "edgecolor": PREMIUM_COLORS["bg"]},
        )
        for item in [*texts, *autotexts]:
            item.set_color(PREMIUM_COLORS["text"])
        plt.title("电影类型占比", fontsize=18, weight="bold", pad=18)
        plt.tight_layout()
        plt.savefig(self.chart_dir / "genre_pie.png", dpi=220)
        plt.close()

    def _plot_director_bar(self, movies: pd.DataFrame) -> None:
        director_series = pd.Series(self._director_distribution(movies), dtype="int64")
        if director_series.empty:
            self._save_placeholder("director_distribution.png", "导演分布 Top10", "当前样本暂无导演字段")
            return
        director_frame = pd.DataFrame(
            {"director": director_series.index, "count": director_series.values}
        )
        plt.figure(figsize=(12, 6.2))
        sns.barplot(
            data=director_frame,
            x="director",
            y="count",
            hue="director",
            palette=sns.color_palette(PLOTLY_COLORWAY, n_colors=len(director_frame)),
            legend=False,
        )
        plt.xticks(rotation=35, ha="right")
        plt.title("导演分布 Top10", fontsize=18, weight="bold", pad=18)
        plt.xlabel("导演")
        plt.ylabel("电影数量")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "director_distribution.png", dpi=220)
        plt.close()

    def _plot_score_votes_scatter(self, movies: pd.DataFrame) -> None:
        frame = self._valid_movie_metric_frame(movies)
        if frame.empty:
            fig = self._empty_plotly_figure("评分与评价人数交互散点图", "当前没有可用评分/评价人数数据")
        else:
            fig = px.scatter(
                frame,
                x="votes",
                y="score",
                size="votes",
                color="year" if frame["year"].notna().any() else None,
                hover_data=[
                    col for col in ["title_cn", "rank", "genres", "runtime"] if col in frame.columns
                ],
                title="评分与评价人数交互散点图",
            )
            apply_premium_plotly_theme(fig, "评分与评价人数交互散点图")
        fig.write_html(
            self.chart_dir / "score_votes_scatter.html",
            include_plotlyjs=True,
            full_html=True,
            config={"responsive": True},
        )

    def _plot_comment_trend(self, comments: pd.DataFrame) -> None:
        if comments.empty:
            self._save_placeholder("comment_trend.png", "短评时间趋势", "当前样本暂无短评")
            return
        trend = (
            comments.dropna(subset=["comment_time"])
            .assign(comment_date=lambda frame: frame["comment_time"].dt.date)
            .groupby("comment_date")
            .size()
            .reset_index(name="count")
        )
        if trend.empty:
            self._save_placeholder("comment_trend.png", "短评时间趋势", "当前样本暂无有效短评时间")
            return
        plt.figure(figsize=(12, 6.2))
        sns.lineplot(data=trend, x="comment_date", y="count", marker="o", color=PREMIUM_COLORS["blue"])
        plt.title("短评时间趋势", fontsize=18, weight="bold", pad=18)
        plt.xlabel("日期")
        plt.ylabel("短评数量")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "comment_trend.png", dpi=220)
        plt.close()

    def _plot_sentiment_pie(self, comments: pd.DataFrame) -> None:
        distribution = self._sentiment_distribution(comments)
        total = sum(distribution.values())
        if total <= 0:
            self._save_placeholder("sentiment_pie.png", "短评情感分布", "当前样本暂无可分析短评")
            return
        plt.figure(figsize=(8, 8))
        wedges, texts, autotexts = plt.pie(
            distribution.values(),
            labels=["正向", "中性", "负向"],
            autopct="%1.1f%%",
            colors=[PREMIUM_COLORS["green"], PREMIUM_COLORS["gold"], PREMIUM_COLORS["red"]],
            wedgeprops={"linewidth": 1.1, "edgecolor": PREMIUM_COLORS["bg"]},
        )
        for item in [*texts, *autotexts]:
            item.set_color(PREMIUM_COLORS["text"])
        plt.title("短评情感分布", fontsize=18, weight="bold", pad=18)
        plt.tight_layout()
        plt.savefig(self.chart_dir / "sentiment_pie.png", dpi=220)
        plt.close()

    def _plot_comment_wordcloud(self, comments: pd.DataFrame) -> None:
        if comments.empty or self.font_path is None:
            self._save_placeholder("comment_wordcloud.png", "热门短评词云", "当前暂无短评文本或中文字体")
            return
        text = " ".join(comments["content"].fillna("").astype(str).tolist())
        tokens = [token for token in jieba.cut(text) if len(token.strip()) > 1]
        if not tokens:
            self._save_placeholder("comment_wordcloud.png", "热门短评词云", "当前样本暂无有效分词")
            return
        cloud = WordCloud(
            width=1400,
            height=900,
            background_color=PREMIUM_COLORS["bg"],
            font_path=str(self.font_path),
            colormap="cividis",
            max_words=180,
        ).generate(" ".join(tokens))
        plt.figure(figsize=(12, 8))
        plt.imshow(cloud, interpolation="bilinear")
        plt.axis("off")
        plt.title("热门短评词云", fontsize=18, weight="bold", pad=18)
        plt.tight_layout()
        plt.savefig(self.chart_dir / "comment_wordcloud.png", dpi=220)
        plt.close()

    def _plot_top_movies_bar(self, movies: pd.DataFrame) -> None:
        top = (
            movies.sort_values(["score", "votes"], ascending=[False, False], na_position="last")
            .head(10)
            .dropna(subset=["score", "title_cn"])
        )
        if top.empty:
            self._save_placeholder("top_movies_bar.png", "高分电影 Top10", "当前样本暂无电影数据")
            return
        plt.figure(figsize=(12, 6.2))
        sns.barplot(
            data=top,
            y="title_cn",
            x="score",
            hue="title_cn",
            palette=sns.color_palette(PLOTLY_COLORWAY, n_colors=len(top)),
            legend=False,
        )
        score_min = max(0, float(top["score"].min()) - 0.25)
        score_max = min(10, float(top["score"].max()) + 0.25)
        if score_max <= score_min:
            score_min, score_max = 0, 10
        plt.xlim(score_min, score_max)
        plt.title("高分电影 Top10", fontsize=18, weight="bold", pad=18)
        plt.xlabel("评分")
        plt.ylabel("电影")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "top_movies_bar.png", dpi=220)
        plt.close()

    def _plot_genre_year_heatmap(self, movies: pd.DataFrame) -> None:
        if movies.empty or "year" not in movies.columns or "genres" not in movies.columns:
            self._save_placeholder("genre_year_heatmap.png", "类型-年代热力图", "缺少年份或类型字段")
            return
        frame = movies.dropna(subset=["year"]).copy()
        frame = frame[frame["year"].between(1880, 2100)]
        if frame.empty:
            self._save_placeholder("genre_year_heatmap.png", "类型-年代热力图", "当前样本暂无有效年份")
            return
        frame["decade"] = (frame["year"].astype(int) // 10 * 10).astype(str) + "s"
        exploded = (
            frame.assign(genre=frame["genres"].apply(self._split_genres))
            .explode("genre")
            .assign(genre=lambda data: data["genre"].astype(str).str.strip())
        )
        exploded = exploded[exploded["genre"] != ""]
        if exploded.empty:
            self._save_placeholder("genre_year_heatmap.png", "类型-年代热力图", "当前样本暂无可用类型/年份组合")
            return
        pivot = exploded.pivot_table(
            index="genre", columns="decade", values="movie_id", aggfunc="count", fill_value=0
        )
        plt.figure(figsize=(12, 7))
        sns.heatmap(
            pivot,
            annot=True,
            fmt="d",
            cmap=sns.color_palette(["#101827", "#244868", "#7A6432", "#D6A84F"], as_cmap=True),
            linewidths=0.5,
            linecolor="#263247",
        )
        plt.title("电影类型与年代分布热力图", fontsize=18, weight="bold", pad=18)
        plt.xlabel("年代")
        plt.ylabel("类型")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "genre_year_heatmap.png", dpi=220)
        plt.close()

    def _plot_sentiment_by_movie(self, movies: pd.DataFrame, comments: pd.DataFrame) -> None:
        if comments.empty:
            self._save_placeholder("sentiment_by_movie.png", "各电影短评情感均值", "当前样本暂无短评")
            return
        title_map = movies.set_index("movie_id")["title_cn"].to_dict() if "movie_id" in movies.columns else {}
        frame = comments.copy()
        frame["sentiment_score"] = frame["content"].fillna("").apply(self._score_sentiment)
        mapped_titles = frame["movie_id"].map(title_map)
        frame["title_cn"] = mapped_titles.where(mapped_titles.notna(), frame["movie_id"]).astype(str)
        mean_scores = (
            frame.groupby("title_cn", as_index=False)["sentiment_score"]
            .mean()
            .sort_values("sentiment_score", ascending=False)
        )
        if mean_scores.empty:
            self._save_placeholder("sentiment_by_movie.png", "各电影短评情感均值", "当前样本暂无有效情感结果")
            return
        plt.figure(figsize=(12, 6.2))
        sns.barplot(
            data=mean_scores.head(15),
            y="title_cn",
            x="sentiment_score",
            hue="title_cn",
            palette=sns.color_palette(PLOTLY_COLORWAY, n_colors=min(15, len(mean_scores))),
            legend=False,
        )
        plt.xlim(0, 1)
        plt.title("各电影短评情感均值", fontsize=18, weight="bold", pad=18)
        plt.xlabel("SnowNLP 情感得分")
        plt.ylabel("电影")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "sentiment_by_movie.png", dpi=220)
        plt.close()

    def _write_interactive_dashboard(
        self, movies: pd.DataFrame, comments: pd.DataFrame, summary: dict[str, object]
    ) -> None:
        dashboard_path = OUTPUT_DIR / "report.html"
        insights = self._build_insights(movies, comments, summary)
        quality = self._quality_profile(movies)
        rankings = self._ranking_groups(movies)
        avg_score = self._safe_mean(movies.get("score"))
        avg_votes = self._safe_mean(movies.get("votes"))
        field_coverage_rate = float(summary.get("field_coverage_rate", 0.0) or 0.0)
        positive_rate = self._positive_rate(summary.get("sentiment_distribution", {}))
        correlation_text = self._correlation_label(summary.get("score_vote_correlation"))

        sankey_html = self._plotly_html(self._build_pipeline_sankey(), include_plotlyjs=True)
        radar_html = self._plotly_html(self._build_quality_radar(quality), include_plotlyjs=False)
        matrix_html = self._plotly_html(self._build_quality_matrix(quality), include_plotlyjs=False)
        quadrant_html = self._plotly_html(self._build_quadrant_scatter(movies), include_plotlyjs=False)

        hero_kpis = [
            ("电影数", self._format_int(len(movies)), "movies_cleaned.csv"),
            ("短评数", self._format_int(len(comments)), "comments_cleaned.csv"),
            ("平均评分", f"{avg_score:.2f}" if avg_score is not None else "样本不足", "score mean"),
            ("字段覆盖率", f"{field_coverage_rate:.0%}", "核心字段平均"),
        ]
        kpi_html = "".join(
            f"""
            <div class="kpi-card">
              <span>{escape(label)}</span>
              <strong>{escape(value)}</strong>
              <small>{escape(note)}</small>
            </div>
            """
            for label, value, note in hero_kpis
        )

        nav_items = [
            ("overview", "总览"),
            ("pipeline", "流程"),
            ("quality", "质量"),
            ("poster-loop", "影廊"),
            ("explorer", "海报墙"),
            ("table", "明细"),
            ("rankings", "榜单"),
            ("sentiment", "情感"),
        ]
        nav_html = "".join(f'<a href="#{target}">{label}</a>' for target, label in nav_items)

        quality_badges = "".join(
            f'<span class="quality-badge {item["status_class"]}">{escape(item["label"])} {item["rate"]:.0%}</span>'
            for item in quality
        )
        quality_tip = self._quality_tip(quality)

        explorer_cards = self._render_movie_cards(movies)
        genre_options = self._render_genre_options(movies)
        decade_options = self._render_decade_options(movies)
        poster_marquee = self._render_poster_marquee(movies)
        movie_table = self._render_movie_table(movies)
        ranking_tabs = self._render_ranking_tabs(rankings)
        static_gallery = self._render_static_gallery()
        sentiment_block = self._render_sentiment_section(comments, summary, insights)

        css = self._dashboard_css()
        js = self._dashboard_js()

        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>豆瓣电影 Top250 智能采集与可视化分析平台</title>
  <link rel="icon" href="data:,">
  <style>{css}</style>
</head>
<body>
  <div class="cinema-bg" aria-hidden="true"></div>
  <header class="topbar">
    <div class="brand">Douban Top250 Dashboard</div>
    <nav aria-label="页面导航">{nav_html}</nav>
    <button id="presentationToggle" class="ghost-button" type="button">进入演示模式</button>
  </header>

  <main>
    <section id="overview" class="hero-section snap-section">
      <div class="hero-copy">
        <p class="eyebrow">Premium Dark Cinema Dashboard</p>
        <h1>豆瓣电影 Top250 智能采集与可视化分析平台</h1>
        <p class="hero-subtitle">从公开网页采集、清洗、存储、分析到交互式展示的一体化数据工程原型</p>
      </div>
      <div class="hero-kpis">{kpi_html}</div>
      <div class="hero-strip">
        <span>样本状态：{escape("完整样本" if len(movies) >= 250 else "演示样本")}</span>
        <span>正向短评：{positive_rate:.0%}</span>
        <span>评分-热度相关：{escape(correlation_text)}</span>
      </div>
    </section>

    <section id="pipeline" class="content-section snap-section">
      <div class="section-title">
        <p class="eyebrow">Pipeline Sankey</p>
        <h2>数据工程链路</h2>
        <p>从豆瓣公开页面到 HTML 看板与 Word 报告，展示采集、存储、清洗、分析和交付路径。</p>
      </div>
      <div class="two-column">
        <div class="glass-panel plot-panel">{sankey_html}</div>
        {self._render_insight_card("流程洞察", insights["pipeline"])}
      </div>
    </section>

    <section id="poster-loop" class="poster-loop-section snap-section">
      <div class="section-title">
        <p class="eyebrow">Top250 Poster Loop</p>
        <h2>循环式电影海报展示</h2>
        <p>按排名循环展示已爬取电影海报；海报缺失时使用黑金电影占位卡，补跑详情页后会自动替换为真实图片。</p>
      </div>
      {poster_marquee}
    </section>

    <section id="quality" class="content-section snap-section">
      <div class="section-title">
        <p class="eyebrow">Data Quality</p>
        <h2>字段覆盖与数据质量</h2>
        <p>用雷达图、覆盖矩阵和状态标签展示当前样本是否足以支撑汇报结论。</p>
      </div>
      <div class="quality-badges">{quality_badges}</div>
      <div class="two-column quality-grid">
        <div class="glass-panel plot-panel">{radar_html}</div>
        <div class="glass-panel plot-panel">{matrix_html}</div>
      </div>
      <div class="two-column">
        <div class="quality-tip">{escape(quality_tip)}</div>
        {self._render_insight_card("质量结论", insights["quality"])}
      </div>
    </section>

    <section id="explorer" class="content-section snap-section">
      <div class="section-title">
        <p class="eyebrow">Movie Explorer</p>
        <h2>电影海报墙</h2>
        <p>支持关键词、类型、最低评分和年代筛选；缺失海报时自动使用黑金占位卡。</p>
      </div>
      <div class="explorer-toolbar">
        <input id="movieSearch" type="search" placeholder="搜索片名、外文名、类型">
        <select id="genreFilter"><option value="">全部类型</option>{genre_options}</select>
        <select id="scoreFilter">
          <option value="0">全部评分</option>
          <option value="9.5">9.5 分以上</option>
          <option value="9">9.0 分以上</option>
          <option value="8">8.0 分以上</option>
        </select>
        <select id="decadeFilter"><option value="">全部年代</option>{decade_options}</select>
        <button id="resetFilters" type="button">重置</button>
      </div>
      <div class="explorer-meta"><span id="movieCount">{len(movies)}</span> 部电影匹配当前筛选</div>
      <div id="posterGrid" class="poster-grid">{explorer_cards}</div>
      <div id="emptyState" class="empty-state">没有匹配的电影记录。</div>
    </section>

    <section id="table" class="content-section snap-section">
      <div class="section-title">
        <p class="eyebrow">Searchable Table</p>
        <h2>电影数据明细表</h2>
        <p>保留原有表格搜索能力，便于答辩时快速定位具体记录和字段缺口。</p>
      </div>
      {movie_table}
    </section>

    <section id="rankings" class="content-section snap-section">
      <div class="section-title">
        <p class="eyebrow">Quadrant & Advanced Rankings</p>
        <h2>评分-热度四象限与进阶榜单</h2>
        <p>以评分均值和评价人数中位数划分象限，并基于评分与热度组合生成多维排行。</p>
      </div>
      <div class="two-column rankings-layout">
        <div class="glass-panel plot-panel">{quadrant_html}</div>
        <div class="glass-panel ranking-panel">{ranking_tabs}</div>
      </div>
      <div class="two-column">
        {self._render_insight_card("榜单洞察", insights["rankings"])}
        <div class="formula-card">综合口碑分 = normalized_score * 0.65 + normalized_log_votes * 0.35</div>
      </div>
    </section>

    {sentiment_block}

    <section id="charts" class="content-section snap-section">
      <div class="section-title">
        <p class="eyebrow">Static Chart Gallery</p>
        <h2>离线图表图库</h2>
        <p>PNG 图表继续输出到 output/charts，可用于 Word 报告和答辩截图。</p>
      </div>
      <div class="chart-gallery">{static_gallery}</div>
    </section>
  </main>

  <footer>生成来源：SQLite + pandas + Matplotlib/Seaborn + Plotly。页面可离线打开，重新运行分析脚本后自动刷新。</footer>
  <script>{js}</script>
</body>
</html>"""
        dashboard_path.write_text(html, encoding="utf-8")

    def _build_pipeline_sankey(self) -> go.Figure:
        labels = [
            "豆瓣公开页面",
            "Top250 列表页",
            "详情页",
            "短评页",
            "SQLite",
            "CSV/JSON",
            "pandas 清洗",
            "情感分析",
            "图表",
            "HTML 看板",
            "Word 报告",
        ]
        source = list(range(len(labels) - 1))
        target = list(range(1, len(labels)))
        value = [10, 9, 8, 8, 7, 7, 6, 5, 5, 4]
        fig = go.Figure(
            data=[
                go.Sankey(
                    arrangement="snap",
                    node={
                        "pad": 18,
                        "thickness": 16,
                        "line": {"color": "rgba(242,210,124,0.35)", "width": 1},
                        "label": labels,
                        "color": [
                            PREMIUM_COLORS["gold"],
                            "#B88A3B",
                            "#9E7534",
                            PREMIUM_COLORS["blue"],
                            "#2B82C6",
                            "#2FA7C8",
                            PREMIUM_COLORS["green"],
                            "#7DD3A8",
                            PREMIUM_COLORS["gold_2"],
                            "#E0B75F",
                            "#F1DFA3",
                        ],
                    },
                    link={
                        "source": source,
                        "target": target,
                        "value": value,
                        "color": ["rgba(214,168,79,0.22)"] * len(source),
                    },
                )
            ]
        )
        return apply_premium_plotly_theme(fig, "采集-清洗-分析-交付链路")

    def _build_quality_radar(self, quality: list[dict[str, Any]]) -> go.Figure:
        if not quality:
            return self._empty_plotly_figure("字段覆盖率雷达图", "当前没有可评估字段")
        labels = [item["label"] for item in quality]
        values = [item["rate"] for item in quality]
        fig = go.Figure(
            data=[
                go.Scatterpolar(
                    r=values + values[:1],
                    theta=labels + labels[:1],
                    fill="toself",
                    name="覆盖率",
                    line={"color": PREMIUM_COLORS["gold"], "width": 3},
                    fillcolor="rgba(214,168,79,0.24)",
                )
            ]
        )
        fig.update_layout(
            polar={
                "bgcolor": "rgba(8,12,22,0.86)",
                "radialaxis": {
                    "visible": True,
                    "range": [0, 1],
                    "tickformat": ".0%",
                    "gridcolor": "rgba(255,255,255,0.14)",
                },
                "angularaxis": {"gridcolor": "rgba(255,255,255,0.12)"},
            }
        )
        return apply_premium_plotly_theme(fig, "字段覆盖率雷达图")

    def _build_quality_matrix(self, quality: list[dict[str, Any]]) -> go.Figure:
        if not quality:
            return self._empty_plotly_figure("字段覆盖矩阵", "当前没有可评估字段")
        labels = [item["label"] for item in quality]
        covered = [item["rate"] for item in quality]
        missing = [1 - item["rate"] for item in quality]
        z = [[rate, miss] for rate, miss in zip(covered, missing)]
        fig = go.Figure(
            data=[
                go.Heatmap(
                    z=z,
                    x=["覆盖率", "缺失率"],
                    y=labels,
                    colorscale=[
                        [0, "#182236"],
                        [0.45, "#2A5C80"],
                        [0.75, "#8A6D2E"],
                        [1, PREMIUM_COLORS["gold_2"]],
                    ],
                    text=[[f"{rate:.0%}", f"{miss:.0%}"] for rate, miss in zip(covered, missing)],
                    texttemplate="%{text}",
                    hovertemplate="%{y} %{x}: %{text}<extra></extra>",
                    showscale=False,
                )
            ]
        )
        return apply_premium_plotly_theme(fig, "字段覆盖矩阵")

    def _build_quadrant_scatter(self, movies: pd.DataFrame) -> go.Figure:
        frame = self._valid_movie_metric_frame(movies)
        if frame.empty:
            return self._empty_plotly_figure("评分-热度四象限", "当前没有可用评分/评价人数数据")
        avg_score = float(frame["score"].mean())
        median_votes = float(frame["votes"].median())
        max_votes = max(float(frame["votes"].max()), 1.0)
        frame = frame.copy()
        frame["quadrant"] = frame.apply(
            lambda row: self._quadrant_label(row["score"], row["votes"], avg_score, median_votes),
            axis=1,
        )
        frame["marker_size"] = frame["votes"].apply(lambda votes: 12 + 42 * math.sqrt(max(votes, 0) / max_votes))
        color_map = {
            "大众神作": PREMIUM_COLORS["gold"],
            "小众高分": PREMIUM_COLORS["green"],
            "热门争议": PREMIUM_COLORS["red"],
            "边缘样本": PREMIUM_COLORS["blue"],
        }
        fig = go.Figure()
        for label, group in frame.groupby("quadrant"):
            fig.add_trace(
                go.Scatter(
                    x=group["votes"],
                    y=group["score"],
                    mode="markers",
                    name=label,
                    marker={
                        "size": group["marker_size"],
                        "color": color_map.get(label, PREMIUM_COLORS["blue"]),
                        "opacity": 0.82,
                        "line": {"color": "rgba(255,255,255,0.72)", "width": 1},
                    },
                    customdata=group[["title_cn", "rank", "year", "genres"]].fillna(""),
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "排名：%{customdata[1]}<br>"
                        "年份：%{customdata[2]}<br>"
                        "类型：%{customdata[3]}<br>"
                        "评价人数：%{x:,}<br>"
                        "评分：%{y:.1f}<extra></extra>"
                    ),
                )
            )
        fig.add_vline(x=median_votes, line_dash="dash", line_color=PREMIUM_COLORS["gold"])
        fig.add_hline(y=avg_score, line_dash="dash", line_color=PREMIUM_COLORS["blue"])
        x_min, x_max = float(frame["votes"].min()), float(frame["votes"].max())
        y_min, y_max = float(frame["score"].min()), float(frame["score"].max())
        x_pad = max((x_max - x_min) * 0.08, 1)
        y_pad = max((y_max - y_min) * 0.08, 0.12)
        fig.update_xaxes(range=[max(0, x_min - x_pad), x_max + x_pad], title="评价人数 votes")
        fig.update_yaxes(range=[max(0, y_min - y_pad), min(10, y_max + y_pad)], title="评分 score")
        annotations = [
            ("大众神作", x_max, y_max, "right", "top"),
            ("小众高分", x_min, y_max, "left", "top"),
            ("热门争议", x_max, y_min, "right", "bottom"),
            ("边缘样本", x_min, y_min, "left", "bottom"),
        ]
        for text, x, y, xanchor, yanchor in annotations:
            fig.add_annotation(
                text=text,
                x=x,
                y=y,
                showarrow=False,
                xanchor=xanchor,
                yanchor=yanchor,
                font={"size": 14, "color": PREMIUM_COLORS["text"]},
                bgcolor="rgba(5,7,13,0.58)",
                bordercolor="rgba(214,168,79,0.45)",
                borderwidth=1,
                borderpad=6,
            )
        return apply_premium_plotly_theme(fig, "评分-热度四象限")

    def _ranking_groups(self, movies: pd.DataFrame) -> dict[str, dict[str, Any]]:
        frame = self._valid_movie_metric_frame(movies)
        empty = {
            "high": {"label": "高分榜", "rows": []},
            "heat": {"label": "热度榜", "rows": []},
            "composite": {"label": "综合口碑榜", "rows": []},
            "niche": {"label": "小众高分榜", "rows": []},
            "controversial": {"label": "热门争议榜", "rows": []},
        }
        if frame.empty:
            return empty
        frame = frame.copy()
        score_min, score_max = float(frame["score"].min()), float(frame["score"].max())
        log_votes = frame["votes"].apply(lambda value: math.log1p(max(float(value), 0.0)))
        log_min, log_max = float(log_votes.min()), float(log_votes.max())
        frame["normalized_score"] = (
            (frame["score"] - score_min) / (score_max - score_min) if score_max != score_min else 1.0
        )
        frame["normalized_log_votes"] = (
            (log_votes - log_min) / (log_max - log_min) if log_max != log_min else 1.0
        )
        frame["composite_score"] = frame["normalized_score"] * 0.65 + frame["normalized_log_votes"] * 0.35
        avg_score = float(frame["score"].mean())
        median_votes = float(frame["votes"].median())
        groups = {
            "high": {
                "label": "高分榜",
                "rows": frame.sort_values(["score", "votes"], ascending=[False, False]).head(10),
            },
            "heat": {
                "label": "热度榜",
                "rows": frame.sort_values("votes", ascending=False).head(10),
            },
            "composite": {
                "label": "综合口碑榜",
                "rows": frame.sort_values("composite_score", ascending=False).head(10),
            },
            "niche": {
                "label": "小众高分榜",
                "rows": frame[(frame["score"] >= avg_score) & (frame["votes"] < median_votes)]
                .sort_values(["score", "votes"], ascending=[False, True])
                .head(10),
            },
            "controversial": {
                "label": "热门争议榜",
                "rows": frame[(frame["score"] < avg_score) & (frame["votes"] >= median_votes)]
                .sort_values(["votes", "score"], ascending=[False, True])
                .head(10),
            },
        }
        return groups

    def _render_ranking_tabs(self, rankings: dict[str, dict[str, Any]]) -> str:
        buttons = []
        panels = []
        for index, (key, group) in enumerate(rankings.items()):
            active = " active" if index == 0 else ""
            hidden = "" if index == 0 else " hidden"
            buttons.append(
                f'<button class="tab-button{active}" type="button" data-tab-target="rank-{key}">{escape(group["label"])}</button>'
            )
            rows = group["rows"]
            if isinstance(rows, pd.DataFrame) and not rows.empty:
                row_html = "".join(self._render_ranking_row(i + 1, row) for i, (_, row) in enumerate(rows.iterrows()))
            else:
                row_html = '<div class="empty-mini">当前样本没有符合该榜单规则的电影。</div>'
            panels.append(f'<div id="rank-{key}" class="tab-panel{hidden}">{row_html}</div>')
        return f"""
        <div class="tab-buttons">{''.join(buttons)}</div>
        <div class="tab-panels">{''.join(panels)}</div>
        """

    def _render_ranking_row(self, index: int, row: pd.Series) -> str:
        title = self._safe_text(row.get("title_cn"), "未命名电影")
        score = self._safe_float(row.get("score"))
        votes = self._safe_int(row.get("votes"))
        composite = self._safe_float(row.get("composite_score"))
        sub = f"评分 {score:.1f}" if score is not None else "评分缺失"
        sub += f" / {self._format_int(votes)} 人评价" if votes is not None else " / 评价人数缺失"
        if composite is not None:
            sub += f" / 综合 {composite:.3f}"
        return f"""
        <article class="rank-row">
          <span class="rank-index">{index:02d}</span>
          <div>
            <strong>{escape(title)}</strong>
            <small>{escape(sub)}</small>
          </div>
        </article>
        """

    def _render_movie_cards(self, movies: pd.DataFrame) -> str:
        if movies.empty:
            return ""
        cards = []
        frame = movies.sort_values("rank", na_position="last").copy()
        for _, row in frame.iterrows():
            title = self._safe_text(row.get("title_cn"), "未命名电影")
            foreign = self._safe_text(row.get("title_foreign"), "")
            genres = self._safe_text(row.get("genres"), "")
            genre_list = self._split_genres(genres)
            year = self._safe_int(row.get("year"))
            decade = f"{year // 10 * 10}s" if year else ""
            score = self._safe_float(row.get("score"))
            votes = self._safe_int(row.get("votes"))
            rank = self._safe_int(row.get("rank"))
            poster_src = self._poster_src(row.get("poster_path"), rank=rank, title=title)
            poster = (
                f'<img src="{escape(poster_src, quote=True)}" alt="{escape(title, quote=True)}">'
                if poster_src
                else '<div class="poster-placeholder"><span>DOUBAN</span><strong>TOP250</strong></div>'
            )
            cards.append(
                f"""
                <article class="poster-card"
                  data-title="{escape((title + ' ' + foreign).lower(), quote=True)}"
                  data-genre="{escape(' '.join(genre_list).lower(), quote=True)}"
                  data-score="{score if score is not None else 0}"
                  data-decade="{escape(decade, quote=True)}">
                  <div class="poster-media">
                    {poster}
                    <div class="poster-overlay">
                      <span>#{rank if rank is not None else '-'}</span>
                      <p>{escape(self._safe_text(row.get("quote"), "暂无短评摘录"))}</p>
                    </div>
                  </div>
                  <div class="poster-info">
                    <div>
                      <strong>{escape(title)}</strong>
                      <small>{escape(foreign)}</small>
                    </div>
                    <div class="poster-stats">
                      <span>{escape(f"{score:.1f}" if score is not None else "N/A")} 分</span>
                      <span>{escape(str(year) if year else "年份待补")}</span>
                    </div>
                    <div class="poster-meta">
                      <span>{escape(" / ".join(genre_list) if genre_list else "类型待补")}</span>
                      <span>{escape(self._format_int(votes) if votes is not None else "评价待补")}</span>
                    </div>
                  </div>
                </article>
                """
            )
        return "".join(cards)

    def _render_poster_marquee(self, movies: pd.DataFrame) -> str:
        if movies.empty:
            return '<div class="empty-hero">暂无电影海报数据。</div>'

        items = []
        frame = movies.sort_values("rank", na_position="last").copy()
        for _, row in frame.iterrows():
            title = self._safe_text(row.get("title_cn"), "未命名电影")
            score = self._safe_float(row.get("score"))
            rank = self._safe_int(row.get("rank"))
            poster_src = self._poster_src(row.get("poster_path"), rank=rank, title=title)
            media = (
                f'<img src="{escape(poster_src, quote=True)}" alt="{escape(title, quote=True)}">'
                if poster_src
                else '<div class="poster-placeholder compact"><span>DOUBAN</span><strong>TOP250</strong></div>'
            )
            items.append(
                f"""
                <article class="loop-poster">
                  <div class="loop-media">{media}</div>
                  <div class="loop-caption">
                    <span>#{rank if rank is not None else "-"}</span>
                    <strong>{escape(title)}</strong>
                    <small>{escape(f"{score:.1f} 分" if score is not None else "评分待补")}</small>
                  </div>
                </article>
                """
            )

        while len(items) < 12:
            items.extend(items[: max(1, len(items))])
        items = items[: max(12, len(frame))]
        set_html = "".join(items)
        return f"""
        <div class="poster-marquee" aria-label="循环式电影海报展示">
          <div class="poster-marquee-track">
            <div class="poster-marquee-set">{set_html}</div>
            <div class="poster-marquee-set" aria-hidden="true">{set_html}</div>
          </div>
        </div>
        """

    def _render_genre_options(self, movies: pd.DataFrame) -> str:
        genres = sorted(self._explode_genres(movies).dropna().unique().tolist())
        return "".join(f'<option value="{escape(str(item).lower(), quote=True)}">{escape(str(item))}</option>' for item in genres)

    def _render_decade_options(self, movies: pd.DataFrame) -> str:
        years = pd.to_numeric(movies.get("year"), errors="coerce").dropna()
        years = years[years.between(1880, 2100)].astype(int)
        decades = sorted({f"{year // 10 * 10}s" for year in years})
        return "".join(f'<option value="{escape(item, quote=True)}">{escape(item)}</option>' for item in decades)

    def _render_movie_table(self, movies: pd.DataFrame) -> str:
        if movies.empty:
            return '<div class="empty-hero">暂无电影明细数据。</div>'
        rows = []
        frame = movies.sort_values("rank", na_position="last").copy()
        for _, row in frame.iterrows():
            title = self._safe_text(row.get("title_cn"), "未命名电影")
            foreign = self._safe_text(row.get("title_foreign"), "")
            genres = self._safe_text(row.get("genres"), "")
            score = self._safe_float(row.get("score"))
            votes = self._safe_int(row.get("votes"))
            year = self._safe_int(row.get("year"))
            rank = self._safe_int(row.get("rank"))
            row_quality = "完整" if year and genres else "待补全"
            rows.append(
                f"""
                <tr data-title="{escape((title + ' ' + foreign).lower(), quote=True)}"
                    data-genre="{escape(genres.lower(), quote=True)}"
                    data-score="{score if score is not None else 0}">
                  <td>{escape(str(rank) if rank is not None else "-")}</td>
                  <td><strong>{escape(title)}</strong><span>{escape(foreign)}</span></td>
                  <td>{escape(f"{score:.1f}" if score is not None else "N/A")}</td>
                  <td>{escape(self._format_int(votes) if votes is not None else "待补")}</td>
                  <td>{escape(str(year) if year else "待补")}</td>
                  <td>{escape(genres or "待补")}</td>
                  <td><span class="status-dot {'ok' if row_quality == '完整' else 'warn'}"></span>{escape(row_quality)}</td>
                </tr>
                """
            )
        return f"""
        <div class="table-toolbar">
          <input id="tableSearch" type="search" placeholder="搜索片名、外文名或类型">
          <select id="tableScoreFilter">
            <option value="0">全部评分</option>
            <option value="9.5">9.5 分以上</option>
            <option value="9">9.0 分以上</option>
            <option value="8">8.0 分以上</option>
          </select>
          <button id="tableReset" type="button">重置</button>
        </div>
        <div class="table-wrap">
          <table id="movieTable">
            <thead>
              <tr><th>排名</th><th>电影</th><th>评分</th><th>评价人数</th><th>年份</th><th>类型</th><th>质量</th></tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
          <div id="tableEmptyState" class="empty-state">没有匹配的电影记录。</div>
        </div>
        """

    def _render_static_gallery(self) -> str:
        static_charts = [
            ("score_histogram.png", "评分分布", "观察榜单评分集中区间"),
            ("top_movies_bar.png", "高分排行", "按评分与热度定位核心电影"),
            ("director_distribution.png", "导演分布", "识别样本中的导演集中度"),
            ("genre_pie.png", "类型占比", "展示类型结构或缺失提示"),
            ("comment_trend.png", "短评时间趋势", "观察短评发布时间变化"),
            ("sentiment_pie.png", "情感占比", "SnowNLP 统计短评情绪结构"),
            ("sentiment_by_movie.png", "电影情感均值", "对比不同电影的评论倾向"),
            ("comment_wordcloud.png", "短评词云", "jieba 分词后的高频表达"),
            ("genre_year_heatmap.png", "类型-年代热力", "观察类型与年代组合"),
        ]
        html = []
        for filename, title, desc in static_charts:
            if (self.chart_dir / filename).exists():
                html.append(
                    f"""
                    <figure class="gallery-item">
                      <img src="charts/{escape(filename, quote=True)}" alt="{escape(title, quote=True)}">
                      <figcaption>
                        <strong>{escape(title)}</strong>
                        <span>{escape(desc)}</span>
                      </figcaption>
                    </figure>
                    """
                )
        return "".join(html) or '<div class="empty-state visible">暂无可展示的静态图表。</div>'

    def _render_sentiment_section(
        self, comments: pd.DataFrame, summary: dict[str, object], insights: dict[str, str]
    ) -> str:
        if comments.empty:
            body = """
            <section id="sentiment" class="content-section snap-section">
              <div class="section-title">
                <p class="eyebrow">Sentiment</p>
                <h2>短评情感分析</h2>
                <p>当前 comments 为空，页面保留分析入口并给出优雅提示。</p>
              </div>
              <div class="empty-hero">暂无短评数据。补跑短评页后将自动生成情感饼图、电影情感均值和词云。</div>
            </section>
            """
            return body
        distribution = summary.get("sentiment_distribution", {})
        positive_rate = self._positive_rate(distribution)
        charts = [
            ("sentiment_pie.png", "短评情感饼图"),
            ("sentiment_by_movie.png", "电影情感均值"),
            ("comment_wordcloud.png", "热门短评词云"),
        ]
        chart_html = "".join(
            f"""
            <figure class="sentiment-chart">
              <img src="charts/{escape(filename, quote=True)}" alt="{escape(title, quote=True)}">
              <figcaption>{escape(title)}</figcaption>
            </figure>
            """
            for filename, title in charts
            if (self.chart_dir / filename).exists()
        )
        return f"""
        <section id="sentiment" class="content-section snap-section">
          <div class="section-title">
            <p class="eyebrow">Sentiment</p>
            <h2>短评情感分析</h2>
            <p>保留情感饼图、电影情感均值和词云，并给出适合汇报的自动洞察。</p>
          </div>
          <div class="sentiment-summary">
            <div class="big-number"><span>正向短评</span><strong>{positive_rate:.0%}</strong></div>
            {self._render_insight_card("情感洞察", insights["sentiment"])}
          </div>
          <div class="sentiment-grid">{chart_html}</div>
        </section>
        """

    def _build_insights(
        self, movies: pd.DataFrame, comments: pd.DataFrame, summary: dict[str, object]
    ) -> dict[str, str]:
        movie_count = len(movies)
        comment_count = len(comments)
        coverage = float(summary.get("field_coverage_rate", 0.0) or 0.0)
        correlation = summary.get("score_vote_correlation")
        top_title = "暂无"
        if not movies.empty:
            top = movies.sort_values(["score", "votes"], ascending=[False, False], na_position="last").head(1)
            if not top.empty:
                top_title = self._safe_text(top.iloc[0].get("title_cn"), "暂无")
        genre_distribution = summary.get("genre_distribution", {})
        top_genre = next(iter(genre_distribution.keys()), "暂无") if isinstance(genre_distribution, dict) else "暂无"
        sentiment_distribution = summary.get("sentiment_distribution", {})
        positive_rate = self._positive_rate(sentiment_distribution)
        quality_text = (
            "详情字段覆盖偏低，建议先补跑详情页与海报下载。"
            if coverage < 0.65
            else "核心字段覆盖较好，可以支撑课堂汇报。"
        )
        rankings_text = (
            "样本不足，四象限更适合演示方法而非外推结论。"
            if movie_count < 25
            else f"当前高分代表为《{top_title}》，类型分布以 {top_genre} 较突出。"
        )
        return {
            "pipeline": f"当前链路已形成闭环：{movie_count} 部电影、{comment_count} 条短评可进入清洗、分析、HTML 与 Word 交付。",
            "quality": quality_text,
            "rankings": f"{rankings_text} 评分-热度相关为 {self._correlation_label(correlation)}。",
            "sentiment": f"短评情感以正向为主的比例为 {positive_rate:.0%}；样本量为 {comment_count} 条，适合做趋势展示。",
        }

    def _render_insight_card(self, title: str, body: str) -> str:
        return f"""
        <aside class="insight-card">
          <span>自动洞察</span>
          <h3>{escape(title)}</h3>
          <p>{escape(body)}</p>
        </aside>
        """

    def _write_data_quality_report(self, movies: pd.DataFrame, comments: pd.DataFrame) -> None:
        quality = self._quality_profile(movies)
        lines = [
            "# 数据质量报告",
            "",
            f"- 电影记录数：{len(movies)}",
            f"- 短评记录数：{len(comments)}",
            f"- 核心字段平均覆盖率：{self._field_coverage_rate(movies):.1%}",
            f"- 质量建议：{self._quality_tip(quality)}",
            "",
            "## 关键字段覆盖率",
        ]
        for item in quality:
            lines.append(f"- {item['label']} ({item['column']}): 覆盖率 {item['rate']:.1%}")
        lines.extend(
            [
                "",
                "## 说明",
                "- 覆盖率按照非空值统计，字段不存在时按 0% 处理。",
                "- 年份、类型、海报覆盖率偏低时，建议优先补跑详情页与海报下载。",
                "- 本报告用于判断当前样本是否足以支撑可视化结论。",
            ]
        )
        (OUTPUT_DIR / "data_quality_report.md").write_text("\n".join(lines), encoding="utf-8")

    def _write_summary(self, summary: dict[str, object]) -> None:
        summary_path = OUTPUT_DIR / "analysis_summary.md"
        correlation = summary.get("score_vote_correlation")
        lines = [
            "# 数据分析摘要",
            "",
            f"- 电影数量：{summary['movie_count']}",
            f"- 短评数量：{summary['comment_count']}",
            f"- 核心字段平均覆盖率：{float(summary.get('field_coverage_rate', 0.0) or 0.0):.1%}",
            f"- 评分与评价人数相关系数：{self._correlation_label(correlation)}",
            "",
            "## 高分电影 Top10",
        ]
        for row in summary["top10_movies"]:
            lines.append(
                f"- {row.get('rank', '')}. {row.get('title_cn', '')} | 评分 {row.get('score', '')} | 评价人数 {row.get('votes', '')}"
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

    def _save_placeholder(self, filename: str, title: str, message: str) -> None:
        plt.figure(figsize=(10, 5.2))
        ax = plt.gca()
        ax.set_facecolor(PREMIUM_COLORS["panel"])
        plt.text(
            0.5,
            0.58,
            title,
            ha="center",
            va="center",
            fontsize=20,
            weight="bold",
            color=PREMIUM_COLORS["gold"],
        )
        plt.text(
            0.5,
            0.42,
            message,
            ha="center",
            va="center",
            fontsize=12,
            color=PREMIUM_COLORS["muted"],
        )
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(self.chart_dir / filename, dpi=220)
        plt.close()

    def _plotly_html(self, fig: go.Figure, *, include_plotlyjs: bool) -> str:
        return pio.to_html(
            fig,
            full_html=False,
            include_plotlyjs=True if include_plotlyjs else False,
            config={"responsive": True, "displayModeBar": False},
        )

    def _empty_plotly_figure(self, title: str, message: str) -> go.Figure:
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"size": 16, "color": PREMIUM_COLORS["muted"]},
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        return apply_premium_plotly_theme(fig, title)

    def _quality_profile(self, movies: pd.DataFrame) -> list[dict[str, Any]]:
        profile = []
        for column, label in QUALITY_FIELDS:
            rate = self._non_empty_rate(movies, column)
            if rate >= 0.9:
                status_class = "ok"
            elif rate >= 0.65:
                status_class = "warn"
            else:
                status_class = "bad"
            profile.append(
                {
                    "column": column,
                    "label": label,
                    "rate": rate,
                    "missing_rate": 1 - rate,
                    "status_class": status_class,
                }
            )
        return profile

    def _quality_tip(self, quality: list[dict[str, Any]]) -> str:
        detail_columns = {"year", "genres", "poster_path"}
        detail_rates = [item["rate"] for item in quality if item["column"] in detail_columns]
        detail_coverage = sum(detail_rates) / len(detail_rates) if detail_rates else 0.0
        if detail_coverage < 0.6:
            return "详情页字段覆盖率偏低，建议补跑详情页采集与海报下载后再做完整结论。"
        if detail_coverage < 0.85:
            return "详情字段基本可用，但仍有缺口；汇报时应说明样本限制。"
        return "详情字段覆盖充分，可以支撑较完整的可视化汇报。"

    def _field_coverage(self, movies: pd.DataFrame) -> dict[str, float]:
        return {column: self._non_empty_rate(movies, column) for column, _ in QUALITY_FIELDS}

    def _field_coverage_rate(self, movies: pd.DataFrame) -> float:
        coverage = self._field_coverage(movies)
        return sum(coverage.values()) / len(coverage) if coverage else 0.0

    def _non_empty_rate(self, movies: pd.DataFrame, column: str) -> float:
        if movies.empty or column not in movies.columns:
            return 0.0
        values = movies[column]
        filled = ~(values.isna() | (values.astype(str).str.strip() == ""))
        return float(filled.mean()) if len(values) else 0.0

    def _valid_movie_metric_frame(self, movies: pd.DataFrame) -> pd.DataFrame:
        if movies.empty:
            return pd.DataFrame(columns=movies.columns)
        frame = movies.copy()
        frame["score"] = pd.to_numeric(frame["score"], errors="coerce")
        frame["votes"] = pd.to_numeric(frame["votes"], errors="coerce")
        frame = frame.dropna(subset=["score", "votes"])
        frame = frame[(frame["votes"] >= 0) & (frame["score"].between(0, 10))]
        for column in frame.columns:
            if column not in {"rank", "score", "votes", "year", "runtime", "imdb_rating"}:
                frame[column] = frame[column].fillna("").astype(str)
        return frame

    def _score_vote_correlation(self, movies: pd.DataFrame) -> float | None:
        frame = self._valid_movie_metric_frame(movies)
        if len(frame) < 2 or frame["score"].nunique() < 2 or frame["votes"].nunique() < 2:
            return None
        correlation = frame["score"].corr(frame["votes"])
        if pd.isna(correlation):
            return None
        return float(correlation)

    def _explode_genres(self, movies: pd.DataFrame) -> pd.Series:
        if movies.empty or "genres" not in movies.columns:
            return pd.Series(dtype="string")
        exploded = movies["genres"].fillna("").apply(self._split_genres).explode()
        exploded = exploded.astype("string").fillna("").str.strip()
        return exploded[exploded != ""]

    def _poster_src(self, value: Any, *, rank: int | None = None, title: str = "") -> str:
        text = self._safe_text(value, "")
        path = Path(text) if text else self._cached_poster_path(rank=rank, title=title)
        if path is None:
            return ""
        if not path.is_absolute():
            path = ROOT_DIR / path
        if not path.exists():
            return ""
        try:
            return path.relative_to(OUTPUT_DIR).as_posix()
        except ValueError:
            return f"../{path.relative_to(ROOT_DIR).as_posix()}" if path.is_relative_to(ROOT_DIR) else path.as_posix()

    def _cached_poster_path(self, *, rank: int | None, title: str = "") -> Path | None:
        if not POSTER_DIR.exists():
            return None
        if rank is not None:
            matches = sorted(POSTER_DIR.glob(f"{rank:03d}_*"))
            if matches:
                return matches[0]
        title = self._safe_text(title, "")
        if title:
            for path in sorted(POSTER_DIR.iterdir()):
                if path.is_file() and title in path.name:
                    return path
        return None

    def _positive_rate(self, distribution: object) -> float:
        if not isinstance(distribution, dict):
            return 0.0
        total = sum(int(value) for value in distribution.values())
        return int(distribution.get("positive", 0)) / total if total else 0.0

    def _safe_mean(self, values: Any) -> float | None:
        series = pd.to_numeric(values, errors="coerce").dropna()
        return float(series.mean()) if not series.empty else None

    def _safe_float(self, value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(number) else number

    def _safe_int(self, value: Any) -> int | None:
        number = self._safe_float(value)
        return int(number) if number is not None else None

    def _safe_text(self, value: Any, default: str = "") -> str:
        if value is None or pd.isna(value):
            return default
        text = str(value).strip()
        return text if text else default

    def _format_int(self, value: int | float | None) -> str:
        if value is None:
            return "0"
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return "0"

    def _correlation_label(self, value: object) -> str:
        number = self._safe_float(value)
        return "样本不足" if number is None else f"{number:.4f}"

    def _quadrant_label(self, score: float, votes: float, avg_score: float, median_votes: float) -> str:
        if score >= avg_score and votes >= median_votes:
            return "大众神作"
        if score >= avg_score and votes < median_votes:
            return "小众高分"
        if score < avg_score and votes >= median_votes:
            return "热门争议"
        return "边缘样本"

    def _split_genres(self, value: Any) -> list[str]:
        text = self._safe_text(value, "")
        if not text:
            return []
        parts = re.split(r"[,，/、\s]+", text)
        return [part.strip() for part in parts if part.strip()]

    @staticmethod
    def _extract_director(value: str) -> str:
        text = str(value)
        if "导演:" not in text:
            return "未知"
        director = text.split("导演:", 1)[1]
        if "主演:" in director:
            director = director.split("主演:", 1)[0]
        return director.split("  ", 1)[0].strip() or "未知"

    @staticmethod
    def _score_sentiment(text: str) -> float:
        text = str(text).strip()
        if not text:
            return 0.5
        try:
            return float(SnowNLP(text).sentiments)
        except Exception:
            return 0.5

    def _dashboard_css(self) -> str:
        return """
:root {
  --bg: #05070d;
  --bg-2: #0b1020;
  --panel: rgba(16, 24, 39, 0.72);
  --panel-strong: rgba(21, 31, 50, 0.9);
  --gold: #d6a84f;
  --gold-2: #f2d27c;
  --blue: #4ab3ff;
  --cyan: #62e4ff;
  --green: #56d39a;
  --red: #ff6b6b;
  --text: #f6f0e6;
  --muted: #9ba8ba;
  --line: rgba(214, 168, 79, 0.24);
  --shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--text);
  background: var(--bg);
  font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
  letter-spacing: 0;
  overflow-x: hidden;
}
.cinema-bg {
  position: fixed;
  inset: 0;
  z-index: -2;
  background:
    radial-gradient(circle at 12% 16%, rgba(214,168,79,0.22), transparent 28%),
    radial-gradient(circle at 82% 10%, rgba(74,179,255,0.18), transparent 32%),
    linear-gradient(135deg, #04060c 0%, #0a0f1d 48%, #120f0a 100%);
}
.cinema-bg::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(255,255,255,0.028) 1px, transparent 1px),
    linear-gradient(0deg, rgba(255,255,255,0.018) 1px, transparent 1px);
  background-size: 46px 46px;
  mask-image: linear-gradient(to bottom, rgba(0,0,0,0.85), rgba(0,0,0,0.15));
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 22px;
  align-items: center;
  padding: 14px 36px;
  border-bottom: 1px solid var(--line);
  background: rgba(5, 7, 13, 0.72);
  backdrop-filter: blur(18px);
}
.brand {
  font-weight: 800;
  color: var(--gold-2);
  white-space: nowrap;
}
.topbar nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.topbar a {
  color: var(--muted);
  text-decoration: none;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 13px;
}
.topbar a:hover { color: var(--text); background: rgba(255,255,255,0.08); }
button, input, select {
  font: inherit;
}
button {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 9px 13px;
  color: var(--text);
  background: rgba(255,255,255,0.06);
  cursor: pointer;
  transition: transform .18s ease, border-color .18s ease, background .18s ease;
}
button:hover { transform: translateY(-1px); border-color: var(--gold); background: rgba(214,168,79,0.14); }
.ghost-button { color: var(--gold-2); white-space: nowrap; }
main { width: min(1760px, calc(100vw - 72px)); margin: 0 auto; }
.snap-section { scroll-margin-top: 82px; }
.hero-section {
  position: relative;
  min-height: calc(100svh - 140px);
  display: grid;
  align-content: center;
  gap: 36px;
  padding: 48px 0 42px;
}
.hero-section::before {
  content: "";
  position: absolute;
  inset: 28px -36px 24px;
  z-index: -1;
  border-bottom: 1px solid rgba(214,168,79,0.34);
  background:
    linear-gradient(100deg, rgba(5,7,13,0.98) 0%, rgba(5,7,13,0.82) 44%, rgba(214,168,79,0.16) 100%),
    repeating-linear-gradient(90deg, rgba(255,255,255,0.025) 0 2px, transparent 2px 14px);
}
.eyebrow {
  margin: 0 0 10px;
  color: var(--gold-2);
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: .14em;
}
.hero-copy { max-width: 1120px; animation: rise .55s ease both; }
h1 {
  margin: 0;
  max-width: 1320px;
  font-size: clamp(42px, 5vw, 90px);
  line-height: 1.02;
  letter-spacing: 0;
}
.hero-subtitle {
  max-width: 820px;
  margin: 20px 0 0;
  color: #d8dfeb;
  font-size: clamp(18px, 1.6vw, 28px);
  line-height: 1.55;
}
.hero-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.kpi-card, .glass-panel, .insight-card, .quality-tip, .formula-card, .empty-hero {
  border: 1px solid var(--line);
  background: linear-gradient(145deg, rgba(255,255,255,0.105), rgba(255,255,255,0.035));
  box-shadow: var(--shadow);
  backdrop-filter: blur(18px);
}
.kpi-card {
  min-height: 138px;
  padding: 18px;
  border-radius: 8px;
  animation: rise .55s ease both;
}
.kpi-card:nth-child(2) { animation-delay: .05s; }
.kpi-card:nth-child(3) { animation-delay: .1s; }
.kpi-card:nth-child(4) { animation-delay: .15s; }
.kpi-card span { color: var(--muted); font-size: 14px; }
.kpi-card strong { display: block; margin-top: 12px; font-size: clamp(34px, 4.6vw, 66px); color: var(--gold-2); }
.kpi-card small { color: var(--muted); }
.hero-strip {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: #dfe6f0;
}
.hero-strip span {
  border: 1px solid rgba(255,255,255,0.13);
  border-radius: 999px;
  padding: 8px 13px;
  background: rgba(255,255,255,0.055);
}
.content-section { padding: 62px 0; }
.section-title {
  display: grid;
  gap: 8px;
  margin-bottom: 22px;
}
.section-title h2 { margin: 0; font-size: clamp(28px, 3vw, 46px); }
.section-title p:not(.eyebrow) { margin: 0; max-width: 900px; color: var(--muted); line-height: 1.7; }
.two-column {
  display: grid;
  grid-template-columns: minmax(0, 1.48fr) minmax(360px, .52fr);
  gap: 18px;
  align-items: stretch;
}
.quality-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.rankings-layout { grid-template-columns: minmax(0, 1.28fr) minmax(420px, .72fr); }
.glass-panel, .insight-card, .quality-tip, .formula-card, .empty-hero {
  border-radius: 8px;
  overflow: hidden;
}
.plot-panel { min-height: 520px; padding: 8px; }
.plot-panel .js-plotly-plot, .plot-panel .plotly-graph-div { min-height: 500px; }
.insight-card {
  padding: 24px;
  min-height: 180px;
  display: grid;
  align-content: start;
  gap: 10px;
}
.insight-card span { color: var(--blue); font-size: 12px; text-transform: uppercase; letter-spacing: .12em; }
.insight-card h3 { margin: 0; color: var(--gold-2); font-size: 22px; }
.insight-card p { margin: 0; color: #d9e0ec; line-height: 1.72; }
.quality-badges { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
.quality-badge {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 8px 12px;
  color: var(--text);
  background: rgba(255,255,255,0.06);
}
.quality-badge.ok { border-color: rgba(86,211,154,0.55); color: var(--green); }
.quality-badge.warn { border-color: rgba(214,168,79,0.65); color: var(--gold-2); }
.quality-badge.bad { border-color: rgba(255,107,107,0.62); color: #ff9a9a; }
.quality-tip, .formula-card {
  padding: 22px;
  color: #efe7d8;
  line-height: 1.7;
}
.formula-card {
  display: grid;
  place-items: center;
  text-align: center;
  color: var(--gold-2);
  font-size: 18px;
}
.poster-loop-section {
  padding: 58px 0 68px;
  overflow: hidden;
}
.poster-marquee {
  position: relative;
  margin: 0 -36px;
  padding: 8px 0 18px;
  overflow: hidden;
  mask-image: linear-gradient(90deg, transparent, #000 7%, #000 93%, transparent);
}
.poster-marquee-track {
  display: flex;
  width: max-content;
  gap: 18px;
  animation: posterLoop 82s linear infinite;
}
.poster-marquee:hover .poster-marquee-track {
  animation-play-state: paused;
}
.poster-marquee-set {
  display: flex;
  gap: 18px;
  padding-right: 18px;
}
.loop-poster {
  flex: 0 0 164px;
  border: 1px solid rgba(214,168,79,0.2);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(9, 14, 25, 0.76);
  box-shadow: 0 18px 54px rgba(0,0,0,0.34);
}
.loop-media {
  width: 100%;
  aspect-ratio: 2 / 3;
  overflow: hidden;
  background: linear-gradient(145deg, rgba(214,168,79,0.24), rgba(74,179,255,0.10));
}
.loop-media img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.poster-placeholder.compact strong {
  font-size: 20px;
}
.loop-caption {
  display: grid;
  gap: 4px;
  padding: 11px 12px 13px;
}
.loop-caption span {
  color: var(--gold-2);
  font-weight: 800;
  font-size: 12px;
}
.loop-caption strong {
  color: var(--text);
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.loop-caption small {
  color: var(--muted);
}
.explorer-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 180px 160px 150px auto;
  gap: 12px;
  margin-bottom: 12px;
}
input, select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 11px 12px;
  color: var(--text);
  background: rgba(9, 14, 25, 0.78);
  outline: none;
}
input:focus, select:focus { border-color: var(--gold); box-shadow: 0 0 0 3px rgba(214,168,79,0.12); }
.explorer-meta { color: var(--muted); margin-bottom: 16px; }
.poster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.poster-card {
  border: 1px solid rgba(214,168,79,0.18);
  border-radius: 8px;
  background: rgba(9, 14, 25, 0.74);
  overflow: hidden;
  min-height: 420px;
  transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
}
.poster-card:hover {
  transform: translateY(-7px);
  border-color: rgba(214,168,79,0.7);
  box-shadow: 0 22px 64px rgba(0,0,0,0.45);
}
.poster-media {
  position: relative;
  aspect-ratio: 2 / 3;
  overflow: hidden;
  background: linear-gradient(145deg, rgba(214,168,79,0.24), rgba(74,179,255,0.10));
}
.poster-media img { width: 100%; height: 100%; object-fit: cover; display: block; }
.poster-placeholder {
  width: 100%;
  height: 100%;
  display: grid;
  place-content: center;
  text-align: center;
  gap: 8px;
  color: var(--gold-2);
  background:
    linear-gradient(145deg, rgba(214,168,79,0.28), rgba(5,7,13,0.28)),
    repeating-linear-gradient(90deg, rgba(255,255,255,0.04) 0 2px, transparent 2px 18px);
}
.poster-placeholder span { color: var(--muted); letter-spacing: .22em; font-size: 12px; }
.poster-placeholder strong { font-size: 26px; }
.poster-overlay {
  position: absolute;
  inset: auto 0 0;
  padding: 18px;
  color: var(--text);
  background: linear-gradient(to top, rgba(0,0,0,0.86), transparent);
  transform: translateY(42%);
  transition: transform .22s ease;
}
.poster-card:hover .poster-overlay { transform: translateY(0); }
.poster-overlay span { color: var(--gold-2); font-weight: 800; }
.poster-overlay p { margin: 8px 0 0; color: #d8dfeb; line-height: 1.5; }
.poster-info { padding: 14px; display: grid; gap: 12px; }
.poster-info strong { display: block; font-size: 17px; }
.poster-info small { display: block; margin-top: 4px; color: var(--muted); min-height: 18px; }
.poster-stats, .poster-meta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: var(--muted);
  font-size: 13px;
}
.poster-stats span:first-child { color: var(--gold-2); font-weight: 800; }
.table-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 180px auto;
  gap: 12px;
  margin-bottom: 14px;
}
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(9, 14, 25, 0.72);
}
table {
  width: 100%;
  min-width: 900px;
  border-collapse: collapse;
}
th, td {
  padding: 13px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  text-align: left;
  vertical-align: middle;
}
th {
  color: var(--gold-2);
  background: rgba(214,168,79,0.08);
  font-size: 13px;
}
td { color: #e7edf7; }
td span {
  display: block;
  margin-top: 4px;
  color: var(--muted);
  font-size: 12px;
}
.status-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin: 0 8px 0 0;
  background: var(--gold);
}
.status-dot.ok { background: var(--green); }
.status-dot.warn { background: var(--red); }
.ranking-panel { padding: 16px; }
.tab-buttons { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.tab-button.active { color: #090e19; background: var(--gold-2); border-color: var(--gold-2); }
.tab-panel.hidden { display: none; }
.rank-row {
  display: grid;
  grid-template-columns: 46px 1fr;
  gap: 12px;
  align-items: center;
  padding: 13px 0;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.rank-row:last-child { border-bottom: 0; }
.rank-index { color: var(--gold-2); font-weight: 800; font-size: 18px; }
.rank-row strong { display: block; }
.rank-row small { display: block; margin-top: 5px; color: var(--muted); }
.empty-mini { color: var(--muted); padding: 18px 0; }
.sentiment-summary {
  display: grid;
  grid-template-columns: minmax(280px, .42fr) minmax(0, .58fr);
  gap: 18px;
  margin-bottom: 18px;
}
.big-number {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 24px;
  background: rgba(255,255,255,0.055);
  display: grid;
  align-content: center;
  min-height: 180px;
}
.big-number span { color: var(--muted); }
.big-number strong { color: var(--green); font-size: clamp(52px, 8vw, 96px); }
.sentiment-grid, .chart-gallery {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.sentiment-chart, .gallery-item {
  margin: 0;
  border: 1px solid rgba(214,168,79,0.18);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(9, 14, 25, 0.7);
}
.sentiment-chart img, .gallery-item img {
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: contain;
  display: block;
  background: #05070d;
}
.sentiment-chart figcaption, .gallery-item figcaption {
  padding: 12px 14px 14px;
  display: grid;
  gap: 4px;
}
.gallery-item span, .sentiment-chart figcaption { color: var(--muted); font-size: 13px; }
.empty-state {
  display: none;
  margin-top: 18px;
  padding: 24px;
  border: 1px solid var(--line);
  border-radius: 8px;
  color: var(--muted);
  text-align: center;
  background: rgba(255,255,255,0.055);
}
.empty-state.visible, .empty-hero { display: block; }
.empty-hero {
  padding: 46px;
  color: var(--muted);
  text-align: center;
}
footer {
  width: min(1760px, calc(100vw - 72px));
  margin: 0 auto;
  padding: 20px 0 40px;
  color: var(--muted);
}
body.presentation {
  scroll-snap-type: y mandatory;
}
body.presentation .snap-section {
  min-height: 100svh;
  scroll-snap-align: start;
  display: grid;
  align-content: center;
}
body.presentation .topbar {
  background: rgba(5,7,13,0.88);
}
@keyframes rise {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes posterLoop {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}
@media (max-width: 1180px) {
  .topbar { grid-template-columns: 1fr; }
  .topbar nav { justify-content: flex-start; }
  .two-column, .rankings-layout, .quality-grid, .sentiment-summary { grid-template-columns: 1fr; }
  .hero-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .explorer-toolbar, .table-toolbar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sentiment-grid, .chart-gallery { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 720px) {
  main, footer { width: min(100vw - 32px, 1760px); }
  .topbar { padding: 12px 16px; }
  .hero-section { min-height: auto; padding: 42px 0; }
  .hero-section::before { inset: 12px -16px; }
  .poster-marquee { margin: 0 -16px; }
  .loop-poster { flex-basis: 136px; }
  .hero-kpis, .explorer-toolbar, .table-toolbar, .sentiment-grid, .chart-gallery { grid-template-columns: 1fr; }
  h1 { font-size: 40px; }
  .content-section { padding: 40px 0; }
  .plot-panel, .plot-panel .js-plotly-plot, .plot-panel .plotly-graph-div { min-height: 390px; }
}
"""

    def _dashboard_js(self) -> str:
        return """
(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  const searchInput = $('#movieSearch');
  const genreFilter = $('#genreFilter');
  const scoreFilter = $('#scoreFilter');
  const decadeFilter = $('#decadeFilter');
  const resetFilters = $('#resetFilters');
  const posterGrid = $('#posterGrid');
  const emptyState = $('#emptyState');
  const movieCount = $('#movieCount');

  function filterMovies() {
    if (!posterGrid) return;
    const query = (searchInput?.value || '').trim().toLowerCase();
    const genre = (genreFilter?.value || '').trim().toLowerCase();
    const minScore = Number(scoreFilter?.value || 0);
    const decade = (decadeFilter?.value || '').trim();
    let visible = 0;
    $$('.poster-card', posterGrid).forEach((card) => {
      const titleMatch = !query || (card.dataset.title || '').includes(query) || (card.dataset.genre || '').includes(query);
      const genreMatch = !genre || (card.dataset.genre || '').split(' ').includes(genre);
      const scoreMatch = Number(card.dataset.score || 0) >= minScore;
      const decadeMatch = !decade || card.dataset.decade === decade;
      const show = titleMatch && genreMatch && scoreMatch && decadeMatch;
      card.style.display = show ? '' : 'none';
      if (show) visible += 1;
    });
    if (movieCount) movieCount.textContent = String(visible);
    if (emptyState) emptyState.style.display = visible ? 'none' : 'block';
  }

  [searchInput, genreFilter, scoreFilter, decadeFilter].forEach((element) => {
    if (!element) return;
    element.addEventListener(element.tagName === 'INPUT' ? 'input' : 'change', filterMovies);
  });
  if (resetFilters) {
    resetFilters.addEventListener('click', () => {
      if (searchInput) searchInput.value = '';
      if (genreFilter) genreFilter.value = '';
      if (scoreFilter) scoreFilter.value = '0';
      if (decadeFilter) decadeFilter.value = '';
      filterMovies();
    });
  }

  const tableSearch = $('#tableSearch');
  const tableScoreFilter = $('#tableScoreFilter');
  const tableReset = $('#tableReset');
  const movieTable = $('#movieTable');
  const tableEmptyState = $('#tableEmptyState');

  function filterTable() {
    if (!movieTable) return;
    const query = (tableSearch?.value || '').trim().toLowerCase();
    const minScore = Number(tableScoreFilter?.value || 0);
    let visible = 0;
    $$('#movieTable tbody tr').forEach((row) => {
      const haystack = `${row.dataset.title || ''} ${row.dataset.genre || ''} ${row.innerText || ''}`.toLowerCase();
      const score = Number(row.dataset.score || 0);
      const show = (!query || haystack.includes(query)) && score >= minScore;
      row.style.display = show ? '' : 'none';
      if (show) visible += 1;
    });
    if (tableEmptyState) tableEmptyState.style.display = visible ? 'none' : 'block';
  }
  [tableSearch, tableScoreFilter].forEach((element) => {
    if (!element) return;
    element.addEventListener(element.tagName === 'INPUT' ? 'input' : 'change', filterTable);
  });
  if (tableReset) {
    tableReset.addEventListener('click', () => {
      if (tableSearch) tableSearch.value = '';
      if (tableScoreFilter) tableScoreFilter.value = '0';
      filterTable();
    });
  }

  $$('[data-tab-target]').forEach((button) => {
    button.addEventListener('click', () => {
      const target = button.dataset.tabTarget;
      if (!target) return;
      const panel = document.getElementById(target);
      if (!panel) return;
      const container = button.closest('.ranking-panel') || document;
      $$('[data-tab-target]', container).forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      $$('.tab-panel', container).forEach((slot) => slot.classList.toggle('hidden', slot.id !== target));
      window.dispatchEvent(new Event('resize'));
    });
  });

  const presentationToggle = $('#presentationToggle');
  const sections = () => $$('.snap-section');
  function setPresentation(enabled) {
    document.body.classList.toggle('presentation', enabled);
    if (presentationToggle) presentationToggle.textContent = enabled ? '退出演示模式' : '进入演示模式';
  }
  if (presentationToggle) {
    presentationToggle.addEventListener('click', () => setPresentation(!document.body.classList.contains('presentation')));
  }

  function activeSectionIndex() {
    const list = sections();
    if (!list.length) return -1;
    const middle = window.scrollY + window.innerHeight * 0.45;
    let best = 0;
    list.forEach((section, index) => {
      if (section.offsetTop <= middle) best = index;
    });
    return best;
  }
  function goSection(delta) {
    const list = sections();
    if (!list.length) return;
    const next = Math.max(0, Math.min(list.length - 1, activeSectionIndex() + delta));
    list[next].scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  document.addEventListener('keydown', (event) => {
    const target = event.target;
    const tag = target?.tagName;
    const isEditing = target?.isContentEditable || ['INPUT', 'SELECT', 'TEXTAREA'].includes(tag);
    if (isEditing) return;
    const enabled = document.body.classList.contains('presentation');
    if (event.key === 'Escape' && enabled) {
      event.preventDefault();
      setPresentation(false);
      return;
    }
    if (!enabled) return;
    if (['ArrowDown', 'PageDown', ' '].includes(event.key)) {
      event.preventDefault();
      goSection(1);
    } else if (['ArrowUp', 'PageUp'].includes(event.key)) {
      event.preventDefault();
      goSection(-1);
    }
  });

  filterMovies();
  filterTable();
})();
"""
