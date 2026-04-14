# Douban Crawler

豆瓣电影 Top250 课程实验项目。项目同时提供 `requests` 版本与 `Scrapy` 版本的爬虫流程，并包含数据存储、清洗、分析与可视化脚本。

## 功能概览

- Top250 列表页采集：排名、标题、评分、评价人数、导演/主演、简介、详情链接
- 详情页扩展采集：年份、片长、类型、IMDb 链接、海报地址
- 热门短评采集：评论者、评分、时间、内容
- Selenium 无头浏览器获取豆瓣校验 Cookie
- SQLite 主表/短评关联表存储，同时导出 CSV/JSON
- Scrapy 版本重构：`Item`、`Spider`、`Pipeline`、`Downloader Middleware`
- pandas 数据清洗、情感分析、5 类图表输出

## 目录结构

```text
.
├─data
├─logs
├─posters
├─scripts
├─src
│  └─douban_crawler
└─scrapy_douban
```

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

后续功能完成后，可通过以下入口执行：

```bash
python scripts/run_requests_pipeline.py
python scripts/clean_data.py
python scripts/analyze_data.py
scrapy crawl top250
```

常用环境变量：

```bash
set DOUBAN_LIST_PAGE_COUNT=10
set DOUBAN_MOVIE_LIMIT=0
set DOUBAN_MAX_WORKERS=4
set DOUBAN_COOKIE_WAIT_SECONDS=8
```

说明：

- `DOUBAN_MOVIE_LIMIT=0` 表示全量抓取
- 豆瓣详情页与短评页先由 Selenium 获取 Cookie，再交给 `requests` 抓取
- IMDb 会优先尝试抓取评分；若目标站返回 WAF/403，则保留 `imdb_id` 并将 `imdb_rating` 置空

## 合规说明

- 仅针对公开、无需登录页面
- 默认遵守 `robots.txt`
- 默认启用随机延时、重试、日志记录
- 不建议高频抓取
