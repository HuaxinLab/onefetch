---
name: onefetch
description: 统一网页读取与采集（小红书 + 微信公众号 + 通用网页 + JS 页面）。默认读取展示，用户确认后再存储。
argument-hint: [url-or-free-text]
---

# OneFetch Skill

## 何时使用

- 读取网页内容
- 读取微信公众号文章
- 抓取小红书内容
- 用户要求时再保存抓取结果

## 初始化（首次）

```bash
bash scripts/bootstrap.sh
bash scripts/doctor.sh
```

## 默认抓取（不存储）

```bash
bash scripts/run_ingest.sh --present "https://example.com/article"
```

## 需要存储时

```bash
bash scripts/run_ingest.sh --store "URL"
```

## 可选参数

```bash
bash scripts/run_ingest.sh --list-crawlers
ONEFETCH_GENERIC_RENDER_MODE=browser bash scripts/run_ingest.sh "URL"
bash scripts/clean.sh
bash scripts/pack.sh --clean-before
bash scripts/pack.sh --name onefetch.zip --output release
```

## 小红书评论（可选）

```bash
ONEFETCH_XHS_COOKIE='...' \
ONEFETCH_XHS_COMMENT_MODE='state+api' \
bash scripts/run_ingest.sh "https://www.xiaohongshu.com/explore/..."
```
