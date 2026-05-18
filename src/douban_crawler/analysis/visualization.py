from __future__ import annotations

from html import escape
from pathlib import Path

import jieba
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.io as pio
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
        self._plot_top_movies_bar(movies)
        self._plot_genre_year_heatmap(movies)
        self._plot_sentiment_by_movie(movies, comments)
        self._write_interactive_dashboard(movies, comments, summary)
        self._write_data_quality_report(movies, comments)
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
            .astype("string")
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
            .astype("string")
            .fillna("")
            .str.split(",")
            .explode()
            .str.strip()
        )
        genre_series = genre_series[genre_series != ""].value_counts().head(8)
        if genre_series.empty:
            self._save_placeholder("genre_pie.png", "电影类型占比", "当前样本暂无类型字段")
            return
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
            self._save_placeholder("comment_wordcloud.png", "热门短评词云", "当前样本暂无短评文本或中文字体")
            return
        text = " ".join(comments["content"].fillna("").tolist())
        tokens = [token for token in jieba.cut(text) if len(token.strip()) > 1]
        if not tokens:
            self._save_placeholder("comment_wordcloud.png", "热门短评词云", "当前样本暂无有效分词")
            return
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

    def _plot_top_movies_bar(self, movies: pd.DataFrame) -> None:
        top = movies.sort_values(["score", "votes"], ascending=[False, False]).head(10)
        if top.empty:
            self._save_placeholder("top_movies_bar.png", "高分电影 Top10", "当前样本暂无电影数据")
            return
        plt.figure(figsize=(12, 6))
        sns.barplot(data=top, y="title_cn", x="score", hue="title_cn", palette="viridis", legend=False)
        plt.xlim(max(0, top["score"].min() - 0.2), min(10, top["score"].max() + 0.2))
        plt.title("高分电影 Top10")
        plt.xlabel("评分")
        plt.ylabel("电影")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "top_movies_bar.png", dpi=200)
        plt.close()

    def _plot_genre_year_heatmap(self, movies: pd.DataFrame) -> None:
        if "year" not in movies.columns or "genres" not in movies.columns:
            self._save_placeholder("genre_year_heatmap.png", "类型-年代热力图", "缺少年份或类型字段")
            return
        frame = movies.dropna(subset=["year"]).copy()
        frame["decade"] = (frame["year"].astype(int) // 10 * 10).astype(str) + "s"
        exploded = (
            frame.assign(genre=frame["genres"].astype("string").fillna("").str.split(","))
            .explode("genre")
            .assign(genre=lambda data: data["genre"].astype(str).str.strip())
        )
        exploded = exploded[exploded["genre"] != ""]
        if exploded.empty:
            self._save_placeholder("genre_year_heatmap.png", "类型-年代热力图", "当前样本暂无可用类型/年份组合")
            return
        pivot = exploded.pivot_table(index="genre", columns="decade", values="movie_id", aggfunc="count", fill_value=0)
        plt.figure(figsize=(12, 7))
        sns.heatmap(pivot, annot=True, fmt="d", cmap="YlGnBu", linewidths=0.5)
        plt.title("电影类型与年代分布热力图")
        plt.xlabel("年代")
        plt.ylabel("类型")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "genre_year_heatmap.png", dpi=200)
        plt.close()

    def _plot_sentiment_by_movie(self, movies: pd.DataFrame, comments: pd.DataFrame) -> None:
        if comments.empty:
            self._save_placeholder("sentiment_by_movie.png", "各电影短评情感均值", "当前样本暂无短评")
            return
        title_map = movies.set_index("movie_id")["title_cn"].to_dict() if "movie_id" in movies.columns else {}
        frame = comments.copy()
        frame["sentiment_score"] = frame["content"].fillna("").apply(self._score_sentiment)
        frame["title_cn"] = frame["movie_id"].map(title_map).fillna(frame["movie_id"])
        mean_scores = frame.groupby("title_cn", as_index=False)["sentiment_score"].mean().sort_values("sentiment_score", ascending=False)
        if mean_scores.empty:
            self._save_placeholder("sentiment_by_movie.png", "各电影短评情感均值", "当前样本暂无有效情感结果")
            return
        plt.figure(figsize=(12, 6))
        sns.barplot(data=mean_scores.head(15), y="title_cn", x="sentiment_score", hue="title_cn", palette="mako", legend=False)
        plt.xlim(0, 1)
        plt.title("各电影短评情感均值")
        plt.xlabel("SnowNLP 情感得分")
        plt.ylabel("电影")
        plt.tight_layout()
        plt.savefig(self.chart_dir / "sentiment_by_movie.png", dpi=200)
        plt.close()

    def _write_interactive_dashboard(self, movies: pd.DataFrame, comments: pd.DataFrame, summary: dict[str, object]) -> None:
        dashboard_path = OUTPUT_DIR / "report.html"
        plotly_blocks = []
        if not movies.empty:
            plotly_blocks.append(
                pio.to_html(
                    px.scatter(
                        movies,
                        x="votes",
                        y="score",
                        size="votes",
                        color="year" if "year" in movies.columns else None,
                        hover_data=[col for col in ["title_cn", "rank", "genres", "runtime"] if col in movies.columns],
                        title="评分与评价人数交互散点图",
                    ),
                    full_html=False,
                    include_plotlyjs=True,
                )
            )
            plotly_blocks.append(
                pio.to_html(
                    px.bar(
                        movies.sort_values(["score", "votes"], ascending=[False, False]).head(15),
                        x="score",
                        y="title_cn",
                        orientation="h",
                        hover_data=[col for col in ["votes", "year", "genres"] if col in movies.columns],
                        title="高分电影交互排行",
                    ),
                    full_html=False,
                    include_plotlyjs=False,
                )
            )

        def non_empty_rate(column: str) -> float:
            if column not in movies.columns or movies.empty:
                return 0.0
            values = movies[column]
            filled = ~(values.isna() | (values.astype(str).str.strip() == ""))
            return float(filled.mean())

        detail_fields = ["year", "genres", "poster_path"]
        detail_coverage = sum(non_empty_rate(column) for column in detail_fields) / len(detail_fields)
        avg_score = float(movies["score"].mean()) if "score" in movies.columns and not movies.empty else 0.0
        avg_votes = int(movies["votes"].mean()) if "votes" in movies.columns and not movies.empty else 0
        sample_status = "演示样本" if len(movies) < 25 else "完整样本"
        quality_status = "需补跑详情" if detail_coverage < 0.6 else "字段覆盖良好"
        sentiment = summary.get("sentiment_distribution", {})
        sentiment_total = max(sum(int(value) for value in sentiment.values()), 1) if isinstance(sentiment, dict) else 1
        positive_rate = int(round(int(sentiment.get("positive", 0)) / sentiment_total * 100)) if isinstance(sentiment, dict) else 0

        static_charts = [
            ("score_histogram.png", "评分分布", "观察榜单评分集中区间"),
            ("top_movies_bar.png", "高分排行", "按评分与热度快速定位核心电影"),
            ("director_distribution.png", "导演分布", "识别样本中的导演集中度"),
            ("sentiment_pie.png", "情感占比", "SnowNLP 统计短评情绪结构"),
            ("sentiment_by_movie.png", "电影情感均值", "对比不同电影的评论倾向"),
            ("comment_wordcloud.png", "短评词云", "jieba 分词后的高频表达"),
            ("genre_year_heatmap.png", "类型-年代热力", "字段不足时展示数据质量提醒"),
        ]
        gallery_html = []
        for filename, title, desc in static_charts:
            if (self.chart_dir / filename).exists():
                gallery_html.append(
                    f"""
                    <figure class="gallery-item" data-chart="{escape(title)}">
                      <img src="charts/{filename}" alt="{escape(title)}">
                      <figcaption>
                        <strong>{escape(title)}</strong>
                        <span>{escape(desc)}</span>
                      </figcaption>
                    </figure>
                    """
                )

        table_rows = []
        for row in movies.fillna("").sort_values("rank").to_dict(orient="records"):
            score = row.get("score", "")
            score_value = float(score) if str(score).strip() else 0.0
            genres = str(row.get("genres", ""))
            row_quality = "完整" if all(str(row.get(field, "")).strip() for field in ["year", "genres"]) else "待补全"
            table_rows.append(
                f'<tr data-score="{score_value}" data-title="{escape(str(row.get("title_cn", ""))).lower()}" data-genre="{escape(genres).lower()}">'
                f"<td>{escape(str(row.get('rank', '')))}</td>"
                f"<td><strong>{escape(str(row.get('title_cn', '')))}</strong><span>{escape(str(row.get('title_foreign', '')))}</span></td>"
                f"<td>{escape(str(row.get('score', '')))}</td>"
                f"<td>{escape(str(row.get('votes', '')))}</td>"
                f"<td>{escape(str(row.get('year', '') or '待补全'))}</td>"
                f"<td>{escape(genres or '待补全')}</td>"
                f'<td><span class="status-dot {"ok" if row_quality == "完整" else "warn"}"></span>{row_quality}</td>'
                "</tr>"
            )

        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>豆瓣电影数据智能分析平台</title>
  <style>
    :root {{
      --ink: #1b2430;
      --muted: #667085;
      --line: #d9e1ea;
      --panel: #ffffff;
      --surface: #f6f4ef;
      --navy: #22354d;
      --teal: #117c80;
      --amber: #bd7b16;
      --rose: #9b3d45;
      --green: #25765c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      background: var(--surface);
      color: var(--ink);
      letter-spacing: 0;
    }}
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: center;
      padding: 12px 32px;
      background: rgba(246, 244, 239, .92);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
    }}
    .brand {{
      font-weight: 700;
      color: var(--navy);
      white-space: nowrap;
    }}
    .topbar nav {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .topbar a {{
      color: var(--muted);
      text-decoration: none;
      padding: 7px 10px;
      border-radius: 6px;
      font-size: 13px;
    }}
    .topbar a:hover {{ background: #e8edf2; color: var(--ink); }}
    header {{
      padding: 34px 32px 26px;
      background: #24364d;
      color: white;
      border-bottom: 5px solid var(--teal);
    }}
    .hero {{
      max-width: 1320px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(280px, .6fr);
      gap: 32px;
      align-items: end;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(30px, 4vw, 56px);
      line-height: 1.05;
      letter-spacing: 0;
    }}
    .subtitle {{
      max-width: 760px;
      margin: 14px 0 0;
      color: #d7e0eb;
      font-size: 15px;
      line-height: 1.8;
    }}
    .run-meta {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      font-size: 13px;
    }}
    .meta-cell {{
      border-left: 2px solid rgba(255,255,255,.35);
      padding: 6px 0 6px 12px;
    }}
    .meta-cell span {{ display: block; color: #b9c7d8; }}
    .meta-cell strong {{ font-size: 17px; }}
    main {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 26px 32px 46px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: end;
      margin: 8px 0 14px;
    }}
    .section-head h2 {{ margin: 0; font-size: 22px; }}
    .section-head p {{ margin: 6px 0 0; color: var(--muted); max-width: 720px; line-height: 1.7; }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 116px;
      animation: rise .55s ease both;
    }}
    .metric:nth-child(2) {{ animation-delay: .05s; }}
    .metric:nth-child(3) {{ animation-delay: .1s; }}
    .metric:nth-child(4) {{ animation-delay: .15s; }}
    .metric label {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 10px; font-size: clamp(28px, 4vw, 42px); color: var(--navy); }}
    .metric small {{ color: var(--muted); }}
    .workspace {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(320px, .55fr);
      gap: 18px;
      align-items: start;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 18px;
    }}
    .panel.compact {{ padding: 16px; }}
    .status-list {{ display: grid; gap: 12px; }}
    .status-row {{
      display: grid;
      grid-template-columns: 120px 1fr auto;
      gap: 10px;
      align-items: center;
      font-size: 13px;
    }}
    .bar {{
      height: 8px;
      background: #edf1f5;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar span {{ display: block; height: 100%; background: var(--teal); border-radius: inherit; }}
    .bar.warn span {{ background: var(--amber); }}
    .callout {{
      border-left: 4px solid var(--amber);
      background: #fff8ec;
      padding: 14px 14px 14px 16px;
      border-radius: 8px;
      line-height: 1.7;
      color: #5e4220;
    }}
    .chart-panel .js-plotly-plot, .chart-panel .plotly-graph-div {{ min-height: 440px; }}
    .chart-panel {{ overflow: hidden; }}
    .chart-tabs {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    button {{
      border: 1px solid var(--line);
      background: white;
      color: var(--ink);
      border-radius: 6px;
      padding: 9px 12px;
      cursor: pointer;
      font-family: inherit;
      transition: transform .18s ease, border-color .18s ease, background .18s ease;
    }}
    button:hover {{ transform: translateY(-1px); border-color: var(--teal); }}
    button.active {{ background: var(--navy); color: white; border-color: var(--navy); }}
    .gallery {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .gallery-item {{
      margin: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #fff;
      transition: transform .18s ease, box-shadow .18s ease;
    }}
    .gallery-item:hover {{ transform: translateY(-2px); box-shadow: 0 12px 28px rgba(34, 53, 77, .12); }}
    .gallery-item img {{ display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: contain; background: #f8fafc; }}
    figcaption {{ padding: 11px 12px 13px; display: grid; gap: 4px; }}
    figcaption span {{ color: var(--muted); font-size: 12px; line-height: 1.55; }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) auto auto;
      gap: 10px;
      align-items: center;
      margin-bottom: 12px;
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      background: white;
    }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 840px; background: white; }}
    th, td {{ padding: 12px 13px; border-bottom: 1px solid #edf1f5; text-align: left; vertical-align: middle; }}
    th {{ background: #eef3f7; color: #35465a; font-size: 13px; position: sticky; top: 0; }}
    td span {{ display: block; color: var(--muted); font-size: 12px; margin-top: 3px; }}
    .status-dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 7px; background: var(--amber); }}
    .status-dot.ok {{ background: var(--green); }}
    .empty-state {{ padding: 18px; color: var(--muted); display: none; }}
    footer {{ max-width: 1320px; margin: 0 auto; padding: 0 32px 38px; color: var(--muted); font-size: 13px; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @media (max-width: 980px) {{
      .hero, .workspace {{ grid-template-columns: 1fr; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .gallery {{ grid-template-columns: 1fr; }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
    }}
    @media (max-width: 620px) {{
      header {{ padding: 28px 18px 22px; }}
      main {{ padding: 18px; }}
      .metrics {{ grid-template-columns: 1fr 1fr; gap: 10px; }}
      .metric {{ min-height: auto; padding: 12px; }}
      .metric strong {{ font-size: 26px; }}
      .controls {{ grid-template-columns: 1fr; }}
      .run-meta {{ grid-template-columns: 1fr 1fr; }}
      .chart-panel .js-plotly-plot, .chart-panel .plotly-graph-div {{ min-height: 360px; }}
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="brand">Douban Analytics</div>
    <nav aria-label="页面导航">
      <a href="#overview">概览</a>
      <a href="#charts">图表</a>
      <a href="#gallery">图库</a>
      <a href="#table">数据表</a>
    </nav>
  </div>
  <header id="overview">
    <div class="hero">
      <div>
        <h1>豆瓣电影数据智能分析平台</h1>
        <p class="subtitle">面向课程演示的爬虫数据工作台：展示采集规模、字段质量、交互图表、静态图表和可检索电影明细。</p>
      </div>
      <div class="run-meta" aria-label="当前运行状态">
        <div class="meta-cell"><span>样本状态</span><strong>{sample_status}</strong></div>
        <div class="meta-cell"><span>字段质量</span><strong>{quality_status}</strong></div>
        <div class="meta-cell"><span>图表输出</span><strong>{len(gallery_html)} 张</strong></div>
        <div class="meta-cell"><span>正向短评</span><strong>{positive_rate}%</strong></div>
      </div>
    </div>
  </header>
  <main>
    <section class="metrics" aria-label="关键指标">
      <div class="metric"><label>电影记录</label><strong>{summary['movie_count']}</strong><small>SQLite movies 表</small></div>
      <div class="metric"><label>短评记录</label><strong>{summary['comment_count']}</strong><small>SQLite comments 表</small></div>
      <div class="metric"><label>平均评分</label><strong>{avg_score:.2f}</strong><small>当前样本均值</small></div>
      <div class="metric"><label>详情字段覆盖</label><strong>{detail_coverage:.0%}</strong><small>年份/类型/海报路径</small></div>
    </section>

    <section class="workspace">
      <div>
        <section class="panel chart-panel" id="charts">
          <div class="section-head">
            <div>
              <h2>交互图表</h2>
              <p>用于课堂演示的核心交互区域，可在散点关系与高分排行之间切换。</p>
            </div>
            <div class="chart-tabs">
              <button class="active" type="button" data-chart-target="plot-0">散点</button>
              <button type="button" data-chart-target="plot-1">排行</button>
            </div>
          </div>
          {''.join(f'<div class="plot-slot" id="plot-{index}" style="display: {"block" if index == 0 else "none"}">{block}</div>' for index, block in enumerate(plotly_blocks))}
        </section>

        <section class="panel" id="gallery">
          <div class="section-head">
            <div>
              <h2>图表图库</h2>
              <p>静态图表可直接用于报告和答辩截图，网络不可用时仍能展示。</p>
            </div>
          </div>
          <div class="gallery">{''.join(gallery_html)}</div>
        </section>
      </div>

      <aside>
        <section class="panel compact">
          <div class="section-head">
            <div>
              <h2>数据质量</h2>
              <p>先判断样本是否足以支撑结论。</p>
            </div>
          </div>
          <div class="status-list">
            <div class="status-row"><span>年份</span><div class="bar warn"><span style="width: {non_empty_rate('year'):.0%}"></span></div><strong>{non_empty_rate('year'):.0%}</strong></div>
            <div class="status-row"><span>类型</span><div class="bar warn"><span style="width: {non_empty_rate('genres'):.0%}"></span></div><strong>{non_empty_rate('genres'):.0%}</strong></div>
            <div class="status-row"><span>海报</span><div class="bar warn"><span style="width: {non_empty_rate('poster_path'):.0%}"></span></div><strong>{non_empty_rate('poster_path'):.0%}</strong></div>
          </div>
        </section>
        <section class="panel compact">
          <div class="callout">
            当前页面已经适合演示系统形态；若要让结论更有说服力，应先补跑详情页，让年份、类型、海报字段覆盖率提升。
          </div>
        </section>
        <section class="panel compact">
          <div class="section-head">
            <div>
              <h2>运行摘要</h2>
              <p>平均评价人数 {avg_votes:,}，评分与评价人数相关系数 {summary['score_vote_correlation']:.4f}。</p>
            </div>
          </div>
        </section>
      </aside>
    </section>

    <section class="panel" id="table">
      <div class="section-head">
        <div>
          <h2>电影数据检索表</h2>
          <p>支持标题/类型搜索和评分筛选，便于现场定位样本记录。</p>
        </div>
      </div>
      <div class="controls">
        <input id="movieSearch" placeholder="搜索标题、外文名或类型">
        <select id="scoreFilter" aria-label="评分筛选">
          <option value="0">全部评分</option>
          <option value="9.5">9.5 分以上</option>
          <option value="9">9.0 分以上</option>
          <option value="8">8.0 分以上</option>
        </select>
        <button id="resetFilters" type="button">重置</button>
      </div>
      <div class="table-wrap">
        <table id="movieTable">
          <thead><tr><th>排名</th><th>电影</th><th>评分</th><th>评价人数</th><th>年份</th><th>类型</th><th>质量</th></tr></thead>
          <tbody>{''.join(table_rows)}</tbody>
        </table>
        <div id="emptyState" class="empty-state">没有匹配的电影记录。</div>
      </div>
    </section>
  </main>
  <footer>生成来源：SQLite + pandas + Plotly。页面由分析脚本自动生成，可随数据更新重新构建。</footer>
  <script>
    const searchInput = document.getElementById('movieSearch');
    const scoreFilter = document.getElementById('scoreFilter');
    const emptyState = document.getElementById('emptyState');
    function filterTable() {{
      const query = document.getElementById('movieSearch').value.toLowerCase();
      const minScore = Number(scoreFilter.value || 0);
      let visibleCount = 0;
      for (const row of document.querySelectorAll('#movieTable tbody tr')) {{
        const score = Number(row.dataset.score || 0);
        const textMatch = row.innerText.toLowerCase().includes(query);
        const scoreMatch = score >= minScore;
        const visible = textMatch && scoreMatch;
        row.style.display = visible ? '' : 'none';
        if (visible) visibleCount += 1;
      }}
      emptyState.style.display = visibleCount ? 'none' : 'block';
    }}
    searchInput.addEventListener('input', filterTable);
    scoreFilter.addEventListener('change', filterTable);
    document.getElementById('resetFilters').addEventListener('click', () => {{
      searchInput.value = '';
      scoreFilter.value = '0';
      filterTable();
    }});
    for (const button of document.querySelectorAll('[data-chart-target]')) {{
      button.addEventListener('click', () => {{
        document.querySelectorAll('[data-chart-target]').forEach(item => item.classList.remove('active'));
        button.classList.add('active');
        document.querySelectorAll('.plot-slot').forEach(slot => slot.style.display = slot.id === button.dataset.chartTarget ? 'block' : 'none');
        window.dispatchEvent(new Event('resize'));
      }});
    }}
  </script>
</body>
</html>"""
        dashboard_path.write_text(html, encoding="utf-8")

    def _write_data_quality_report(self, movies: pd.DataFrame, comments: pd.DataFrame) -> None:
        important_movie_fields = ["movie_id", "rank", "title_cn", "score", "votes", "detail_url", "year", "genres", "poster_path"]
        lines = [
            "# 数据质量报告",
            "",
            f"- 电影记录数：{len(movies)}",
            f"- 短评记录数：{len(comments)}",
            "",
            "## 关键字段缺失率",
        ]
        for column in important_movie_fields:
            if column not in movies.columns:
                lines.append(f"- {column}: 字段不存在")
                continue
            missing = movies[column].isna() | (movies[column].astype(str).str.strip() == "")
            rate = float(missing.mean()) if len(movies) else 0.0
            lines.append(f"- {column}: {rate:.1%}")
        lines.extend(
            [
                "",
                "## 说明",
                "- 该报告用于判断当前样本是否足以支撑可视化结论。",
                "- 若电影数或详情字段覆盖率偏低，应优先补跑爬虫再解释统计结论。",
            ]
        )
        (OUTPUT_DIR / "data_quality_report.md").write_text("\n".join(lines), encoding="utf-8")

    def _save_placeholder(self, filename: str, title: str, message: str) -> None:
        plt.figure(figsize=(10, 5))
        plt.text(0.5, 0.55, title, ha="center", va="center", fontsize=18, weight="bold")
        plt.text(0.5, 0.4, message, ha="center", va="center", fontsize=12)
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(self.chart_dir / filename, dpi=200)
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
