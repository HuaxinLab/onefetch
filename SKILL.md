---
name: onefetch
description: 统一网页读取与采集（小红书 + 微信公众号 + 通用网页 + JS 页面）。默认读取展示，用户确认后再存储。
argument-hint: [url-or-free-text]
---

# OneFetch Skill

## 何时使用

- 用户要求读取网页内容
- 用户要求读取微信公众号文章
- 用户要求抓取小红书内容
- 用户确认后需要保存抓取结果

## Agent 执行规范

1. 优先使用 `scripts/run_ingest.sh --present "URL"` 返回可读摘要。
2. 仅在用户明确要求保存/归档时使用 `--store`。
3. 小红书评论默认可选；仅在用户需要评论时启用 `ONEFETCH_XHS_COMMENT_MODE='state+api'`。
4. 若用户未配置评论 Cookie，agent 需引导用户完成插件导出并执行 `bash scripts/setup_xhs_cookie.sh` 粘贴一次。
5. 报错时按可恢复性处理：可重试错误先重试一次，再给用户建议。

## Agent 常用命令

```bash
# 默认抓取（不存储）
bash scripts/run_ingest.sh --present "https://example.com/article"

# 用户明确要求保存
bash scripts/run_ingest.sh --store "URL"

# 查看适配器
bash scripts/run_ingest.sh --list-crawlers

# 小红书评论（可选）
bash scripts/setup_xhs_cookie.sh
ONEFETCH_XHS_COMMENT_MODE='state+api' \
  bash scripts/run_ingest.sh "https://www.xiaohongshu.com/explore/..."
```

## 参考文档

- 用户说明：`references/USER_GUIDE.md`
- 文档索引：`references/INDEX.md`
- 架构：`references/ARCHITECTURE.md`
