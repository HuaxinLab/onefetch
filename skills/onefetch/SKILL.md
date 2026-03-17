---
name: onefetch
description: Focused cross-platform URL ingestion for Xiaohongshu and generic HTML pages. Use when users share links and want deterministic capture into local artifacts (raw/feed/note).
argument-hint: [url-or-free-text]
---

# OneFetch Skill

当用户提出以下需求时使用 OneFetch：
- 采集 / 抓取 / 归档网页链接
- 抓取小红书链接内容
- 将通用网页保存为结构化本地记录

## 前置条件

执行前请确认：

1. 项目目录存在于 `~/Projects/acusp/OneFetch`（或已设置 `ONEFETCH_PROJECT_ROOT`）
2. 虚拟环境存在于 `PROJECT_ROOT/.venv`
3. 该环境已安装 CLI（`pip install -e ".[dev]"`）

如果不满足，请先按 `docs/INSTALLATION.md` 初始化环境。

## 工作流

1. 从用户输入中提取 URL。
2. 通过 wrapper 脚本调用 OneFetch CLI。
3. 如果用户需要小红书评论，按配置启用评论模式（可选登录 Cookie）。
4. 向用户汇报状态、产物路径、评论抓取状态。

## 常用命令

列出可用爬虫：

```bash
bash scripts/run_ingest.sh --list-crawlers
```

抓取 URL：

```bash
bash scripts/run_ingest.sh "https://www.xiaohongshu.com/explore/xxxxx"
bash scripts/run_ingest.sh "https://example.com/article"
```

强制爬虫（调试用）：

```bash
bash scripts/run_ingest.sh --crawler xiaohongshu "URL"
```

生成运行报告：

```bash
bash scripts/run_ingest.sh "URL" \
  --report-json "./reports/latest-run.json" \
  --report-md "./reports/latest-run.md"
```

## 小红书评论模式

默认模式（推荐）：

```bash
ONEFETCH_XHS_COMMENT_MODE='state+api' bash scripts/run_ingest.sh "URL"
```

包含 DOM 兜底（成本更高）：

```bash
ONEFETCH_XHS_COMMENT_MODE='state+api+dom' bash scripts/run_ingest.sh "URL"
```

关闭评论抓取：

```bash
ONEFETCH_XHS_COMMENT_MODE='off' bash scripts/run_ingest.sh "URL"
```

登录态评论抓取：

```bash
ONEFETCH_XHS_COOKIE='...' \
ONEFETCH_XHS_COMMENT_MODE='state+api' \
ONEFETCH_XHS_COMMENT_MAX_PAGES=3 \
ONEFETCH_XHS_COMMENT_MAX_ITEMS=50 \
bash scripts/run_ingest.sh "URL"
```

风控友好参数：

```bash
ONEFETCH_XHS_API_MIN_INTERVAL_SEC=1.0 \
ONEFETCH_XHS_API_MAX_RETRIES=2 \
ONEFETCH_XHS_API_BACKOFF_SEC=1.0 \
ONEFETCH_XHS_API_RISK_COOLDOWN_SEC=900 \
bash scripts/run_ingest.sh "URL"
```

## 备注

- 始终在项目虚拟环境（`.venv`）下执行。
- 产物默认写入项目本地 `data/` 目录。
- 若依赖缺失，引导用户先执行 `docs/INSTALLATION.md`。
- 小红书无有效登录 Cookie 时，评论可能为空。
- `comment_fetch` 状态会写入 feed metadata，应在汇报中体现。

## 输出模板

抓取完成后，建议按以下结构回复：

1. URL 总处理结果（stored / duplicate / failed）
2. 每条 URL 的产物路径（`raw` / `feed` / `note`）
3. 小红书评论状态：`comment_fetch.source`、`api.status/code/msg`、评论条数
4. 若生成报告：返回 JSON/Markdown 报告路径
