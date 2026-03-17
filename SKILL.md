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

1. 首次使用或环境异常时，先执行 `bash scripts/bootstrap.sh` 和 `bash scripts/doctor.sh` 完成依赖安装与检查。
2. 默认使用 `scripts/run_ingest.sh --present --from-cache "URL"`，优先复用缓存，减少重复抓取。
3. 用户明确要求“最新/重新抓取/刷新”时，使用 `--refresh` 强制实时抓取（即使同时带 `--from-cache` 也会跳过缓存读取）。
4. 默认保持临时缓存写入（`--cache-temp`），便于后续深入分析/翻译复用全文。
5. 仅在用户明确要求保存/归档时使用 `--store`。
6. 模型输出默认读取 `reports/llm_output.json` 并回填校验；仅在路径不同的情况下才使用 `--llm-output-file <path>`。
7. 若 `llm_outputs_state=fallback`，后续保存/归档前应基于 `full_body` 重新生成结构化输出，避免沿用失效结果。
8. 若最终走规则保底保存，agent 需用通俗语言提醒：正文已保存，但摘要/要点/标签为自动整理结果，可能不够准确；用户可稍后要求“重新整理”再覆盖。
9. 小红书评论默认可选；仅在用户需要评论时启用 `ONEFETCH_XHS_COMMENT_MODE='state+api'`。
10. 若用户未配置评论 Cookie，agent 需引导用户完成插件导出并执行 `bash scripts/setup_xhs_cookie.sh` 粘贴一次。
11. 报错时按可恢复性处理：可重试错误先重试一次，再给用户建议。

## Agent 常用命令

```bash
# 首次初始化/修复环境
bash scripts/bootstrap.sh
bash scripts/doctor.sh

# 默认读取（优先缓存，不存储）
bash scripts/run_ingest.sh --present --from-cache "https://example.com/article"

# 用户要求刷新内容（实时抓取）
bash scripts/run_ingest.sh --present --refresh "https://example.com/article"

# 用户明确要求保存
bash scripts/run_ingest.sh --store --from-cache "URL"

# 默认从 reports/llm_output.json 解析并回填模型输出
bash scripts/run_ingest.sh --present --from-cache "URL"

# 模型输出路径非默认时，手动指定覆盖路径
bash scripts/run_ingest.sh --present --from-cache \
  --llm-output-file /path/to/llm_output.json "URL"

# 查看适配器
bash scripts/run_ingest.sh --list-crawlers

# 小红书评论（可选）
bash scripts/setup_xhs_cookie.sh
ONEFETCH_XHS_COMMENT_MODE='state+api' \
  bash scripts/run_ingest.sh "https://www.xiaohongshu.com/explore/..."
```

## 参考文档

- 用户说明：`README.md`
- 文档索引：`references/INDEX.md`
- 架构：`references/ARCHITECTURE.md`
- 需求：`references/REQUIREMENTS.md`
- 工程：`references/ENGINEERING.md`
