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
12. 知乎专栏若出现 `risk.blocked`，引导用户执行 `bash scripts/setup_zhihu_cookie.sh` 粘贴 Cookie 后重试。
13. 当用户是“提取某个页面字段/资源 URL（如 css 属性、jsonp 字段）”这类需求时，优先使用 `onefetch plugin run ...`，不要走 `run_ingest.sh` 主流程。

## 插件列表与选型

当前可用插件（可通过 `.venv/bin/python -m onefetch.cli plugin list` 查看）：

1. `extract_css_attr`
- 作用：从 HTML 中按简单 CSS 选择器提取属性或文本。
- 适用：用户说“给我某个元素的 src/href/text”。
- 关键参数：
  - `selector`：支持 `#id`、`.class`、`tag`、`tag.class`
  - `attr`：默认 `src`，可用 `text`
  - `index`：可选，默认 `0`

2. `extract_jsonp_field`
- 作用：从 JSONP 响应提取字段值。
- 适用：用户说“这个接口 callback 返回里的某个字段”。
- 关键参数：
  - `jsonp_url`：JSONP 地址（不传则使用 `--url`）
  - `callback`：默认 `callback`
  - `field`：默认 `img_url`

3. `extract_html_js_jsonp`
- 作用：链路提取（HTML -> JS -> JSONP 字段）。
- 适用：目标值不在 HTML，需要先从 HTML 定位 JS，再从 JS 找 JSONP 地址，最后取字段。
- 关键参数：
  - `callback`：默认 `img_url`
  - `field`：默认 `img_url`
  - `append_version`：`true/false`，是否拼接 `?v=...`
  - `preset`：可直接使用预设参数（如 `template_html_js_jsonp`）
  - `js_url_regexes/jsonp_base_regexes`：支持多候选（数组或 `a||b`）
  - 可选直传：`html`、`js_body`、`jsonp_body`（便于调试/离线测试）

内置常用 preset（`onefetch/plugin_presets/*.json`）：
- `template_html_js_jsonp`：模板示例，给 agent 学习 preset 结构与字段写法
- `chain_cdn_js_jsonp_img`：优先提取图片 URL（`img_url`），支持版本拼接与默认图兜底
- `chain_cdn_js_jsonp_download`：优先提取下载链接字段（`download_url`）
- `chain_generic_js_jsonp_value`：未知站点快速探测（`callback/value`）
- `chain_js_only_jsonp_value`：已知 JS URL 场景，跳过 HTML 定位

选型规则：
- 页面 DOM 属性/文本提取：优先 `extract_css_attr`
- JSONP 字段提取：优先 `extract_jsonp_field`
- 需要“先抓 HTML 再追 JS/接口再提取”的链路：优先 `extract_html_js_jsonp`

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

# 知乎专栏被风控时，一次配置 Cookie 后重试
bash scripts/setup_zhihu_cookie.sh
bash scripts/run_ingest.sh --present --refresh "https://zhuanlan.zhihu.com/p/..."

# 插件列表（独立能力，不影响 ingest）
.venv/bin/python -m onefetch.cli plugin list

# 插件 + 预设总览（带每个插件可用 preset）
.venv/bin/python -m onefetch.cli plugin list --with-presets

# 单独查看 preset 列表（可按 plugin 过滤）
.venv/bin/python -m onefetch.cli plugin presets --plugin-id extract_html_js_jsonp

# 插件运行：按 CSS 选择器提取属性/文本
.venv/bin/python -m onefetch.cli plugin run extract_css_attr \
  --url "https://example.com" \
  --opt selector=.hero \
  --opt attr=src

# 插件运行：从 JSONP 中提取字段
.venv/bin/python -m onefetch.cli plugin run extract_jsonp_field \
  --opt jsonp_url="https://example.com/api.js?callback=img_url" \
  --opt callback=img_url \
  --opt field=img_url

# 插件运行：链路提取（HTML -> JS -> JSONP -> 字段）
.venv/bin/python -m onefetch.cli plugin run extract_html_js_jsonp \
  --url "https://www.dingtalk.com/wukong" \
  --opt preset=chain_cdn_js_jsonp_img

# 需要排查失败原因时，输出 JSON（含 trace）
.venv/bin/python -m onefetch.cli plugin run extract_html_js_jsonp \
  --url "https://www.dingtalk.com/wukong" \
  --opt preset=chain_cdn_js_jsonp_img \
  --json

# 自动探测（callback/field/regex 未知时）
.venv/bin/python -m onefetch.cli plugin run extract_html_js_jsonp \
  --url "https://example.com" \
  --opt auto_detect=true \
  --json

# 失败后做诊断（返回 error_code/suggestion/steps）
.venv/bin/python -m onefetch.cli plugin doctor extract_html_js_jsonp \
  --url "https://example.com" \
  --opt preset=chain_generic_js_jsonp_value \
  --json
```

## 参考文档

- 用户说明：`README.md`
- 文档索引：`references/INDEX.md`
- 架构：`references/ARCHITECTURE.md`
- 需求：`references/REQUIREMENTS.md`
- 工程：`references/ENGINEERING.md`
