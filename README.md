# Douban Crawler

豆瓣电影 Top250 课程实验项目，包含数据采集、清洗、存储、分析、可视化看板和实验报告生成。

## 在线看板

- GitHub Pages: <https://lllllllama.github.io/Douban_Crawler/>
- 发布目录: `docs/`
- 本地生成页面: `output/report.html`

如果页面还没有显示，在仓库 `Settings -> Pages` 中设置：

- Source: `Deploy from a branch`
- Branch: `main`
- Folder: `/docs`

保存后等待 1-2 分钟即可访问 Pages 地址。

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

常用流程：

```bash
python scripts/run_requests_pipeline.py
python scripts/clean_data.py
python scripts/analyze_data.py
python scripts/build_experiment_report.py
```

Scrapy 版本：

```bash
scrapy crawl top250
scrapy crawl top250 -a list_page_count=1 -a movie_limit=1
```

## 常用参数

Windows PowerShell 示例：

```powershell
$env:DOUBAN_LIST_PAGE_COUNT="10"
$env:DOUBAN_MOVIE_LIMIT="0"
$env:DOUBAN_MAX_WORKERS="2"
$env:DOUBAN_COOKIE_WAIT_SECONDS="8"
```

说明：

- `DOUBAN_LIST_PAGE_COUNT`: Top250 列表页数量。
- `DOUBAN_MOVIE_LIMIT`: 电影数量限制，`0` 表示不限制。
- `DOUBAN_MAX_WORKERS`: requests 详情页并发数，建议保持低并发。
- `DOUBAN_COOKIE_WAIT_SECONDS`: Selenium 获取 Cookie 时的等待时间。

## 输出目录

- `data/douban_movies.sqlite3`: SQLite 数据库。
- `data/raw/`: 原始 CSV/JSON 备份。
- `data/processed/`: 清洗后的 CSV/JSON。
- `posters/`: 本地海报缓存。
- `output/charts/`: 可视化图表。
- `output/report.html`: 本地交互式看板。
- `doc/`: Word/PDF 实验报告。
- `docs/`: 已提交到仓库的 GitHub Pages 静态发布快照。

## GitHub Actions

工作流文件：

```text
.github/workflows/auto-update-dashboard.yml
```

当前工作流用于低频更新分析结果，支持：

- 手动触发：`Actions -> Auto Update Douban Dashboard -> Run workflow`
- 定时触发：每周日 `03:00 UTC`

手动触发参数：

- `run_crawler`: 是否先运行爬虫，首次没有数据时设为 `true`。
- `list_page_count`: 列表页数量。
- `movie_limit`: 电影数量限制，`0` 表示不限制。
- `max_workers`: 最大并发数，建议保持低并发。

默认定时任务不执行全量高频爬取，只做低频分析刷新。

## 项目结构

```text
.
├── .github/workflows/          # GitHub Actions
├── data/                       # 本地数据库和导出数据
├── docs/                       # GitHub Pages 发布目录
├── output/                     # 本地看板和图表输出
├── posters/                    # 本地海报缓存
├── scrapy_douban/              # Scrapy 实现
├── scripts/                    # 采集、清洗、分析、报告脚本
├── src/douban_crawler/         # requests 版本核心代码
└── tests/                      # 测试
```

## 合规说明

- 项目用于课程实验和数据分析展示。
- 默认遵守目标站点 `robots.txt` 和访问频率限制。
- 不建议高频、并发或商业化抓取。
- 全量更新应手动触发，并使用低频、低并发参数。
