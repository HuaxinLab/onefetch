---
name: onefetch
description: 读取、总结、翻译任意网页内容，或从页面中提取特定元素。当用户给出一个 URL 并要求查看、阅读、总结、翻译、保存网页内容时使用；当用户要求从网页中提取图片、下载链接、特定字段等元素时也使用。支持小红书、微信公众号、知乎、通用网页及 SPA/JS 渲染页面。
---

# OneFetch Skill

## 何时使用

- 用户要求读取 / 总结 / 翻译任意网页内容
- 用户要求读取小红书笔记（含可选评论）
- 用户要求读取微信公众号文章
- 用户要求读取知乎专栏文章或问答
- 用户要求从页面中提取特定元素（图片 URL、下载链接、字段值等）
- 用户确认后需要保存 / 归档抓取结果

## 支持的平台

| 平台 | 自动识别的 URL | 说明 |
|---|---|---|
| 小红书 | `xiaohongshu.com`、`xhslink.com` | 笔记正文 + 可选评论 |
| 微信公众号 | `mp.weixin.qq.com` | 文章正文 |
| 知乎 | `zhuanlan.zhihu.com/p/*`、`zhihu.com/question/*` | 专栏文章、问答 |
| 通用网页 | 所有其他 URL | 自动去噪提取正文；SPA/JS 页面自动浏览器渲染 |

agent 不需要手动选择适配器，router 根据 URL 自动路由。

## Agent 执行规范

### 环境准备

1. 首次使用或环境异常时，先执行 `bash scripts/bootstrap.sh` 和 `bash scripts/doctor.sh` 完成依赖安装与检查。
2. 如果遇到 `error_code=dep.playwright_missing`，说明需要浏览器渲染组件。按 `action_hint` 字段的命令安装即可，通常为：
   ```bash
   .venv/bin/python -m pip install -e '.[browser]' && .venv/bin/python -m playwright install chromium
   ```

### 读取网页（主流程）

3. 默认使用 `scripts/run_ingest.sh --present --from-cache "URL"`，优先复用缓存，减少重复抓取。
4. 用户明确要求"最新/重新抓取/刷新"时，使用 `--refresh` 强制实时抓取（即使同时带 `--from-cache` 也会跳过缓存读取）。
5. 默认保持临时缓存写入（`--cache-temp`），便于后续深入分析 / 翻译复用全文。
6. 仅在用户明确要求保存 / 归档时使用 `--store`。

### 模型输出回填

7. 模型输出默认读取 `reports/llm_output.json` 并回填校验；仅在路径不同的情况下才使用 `--llm-output-file <path>`。
8. 若 `llm_outputs_state=fallback`，后续保存 / 归档前应基于 `full_body` 重新生成结构化输出，避免沿用失效结果。
9. 若最终走规则保底保存，agent 需用通俗语言提醒：正文已保存，但摘要 / 要点 / 标签为自动整理结果，可能不够准确；用户可稍后要求"重新整理"再覆盖。

### 平台特殊处理

10. **小红书评论**：默认不抓取评论。仅在用户需要评论时启用 `ONEFETCH_XHS_COMMENT_MODE='state+api'`。若用户未配置评论 Cookie，引导用户执行 `bash scripts/setup_xhs_cookie.sh` 粘贴一次。
11. **知乎风控**：若出现 `error_code=risk.blocked`，引导用户执行 `bash scripts/setup_zhihu_cookie.sh` 粘贴 Cookie 后重试。

### 错误处理

12. 关注结果中的 `error_code`、`error_type`、`retryable`、`action_hint` 字段：
    - `retryable=True`：先自动重试一次，仍失败再告知用户。
    - `action_hint` 非空：包含可直接执行的修复命令（如安装依赖），agent 应尝试自动执行。
    - 常见错误码速查：
      - `dep.playwright_missing` → 安装 Playwright（见 action_hint）
      - `risk.blocked` → 配置对应平台 Cookie
      - `network.timeout` → 重试
      - `route.not_found` → URL 格式有误

### 何时用插件而非主流程

13. 当用户需求是"提取某个页面字段 / 资源 URL（如 CSS 属性、JSONP 字段、下载链接）"时，优先使用 `onefetch plugin run ...`，不要走 `run_ingest.sh` 主流程。

## 插件列表与选型

当前可用插件（可通过 `.venv/bin/python -m onefetch.cli plugin list` 查看）：

### 1. `extract_css_attr`

- **作用**：从 HTML 中按 CSS 选择器提取属性或文本。
- **适用**：用户说"给我某个元素的 src / href / text"。
- **关键参数**：
  - `selector`：支持 `#id`、`.class`、`tag`、`tag.class`
  - `attr`：默认 `src`，可用 `text`
  - `index`：可选，默认 `0`

### 2. `extract_jsonp_field`

- **作用**：从 JSONP 响应提取字段值。
- **适用**：用户说"这个接口 callback 返回里的某个字段"。
- **关键参数**：
  - `jsonp_url`：JSONP 地址（不传则使用 `--url`）
  - `callback`：默认 `callback`
  - `field`：默认 `img_url`

### 3. `extract_html_js_jsonp`

- **作用**：链路提取（HTML → JS → JSONP → 字段）。
- **适用**：目标值不在 HTML，需要先从 HTML 定位 JS，再从 JS 找 JSONP 地址，最后取字段。
- **关键参数**：
  - `callback`：默认 `img_url`
  - `field`：默认 `img_url`
  - `append_version`：`true/false`，是否拼接 `?v=...`
  - `preset`：可直接使用预设参数（如 `template_html_js_jsonp`）
  - `js_url_regexes` / `jsonp_base_regexes`：支持多候选（数组或 `a||b`）
  - 可选直传：`html`、`js_body`、`jsonp_body`（便于调试 / 离线测试）

### 插件选型规则

| 用户需求 | 选择插件 |
|---|---|
| 页面 DOM 属性 / 文本提取 | `extract_css_attr` |
| JSONP 接口字段提取 | `extract_jsonp_field` |
| 需要"HTML → JS → 接口 → 字段"的链路 | `extract_html_js_jsonp` |
| 不确定该用哪个 | 先用 `extract_html_js_jsonp` + `auto_detect=true` 探测 |

### 内置 preset

preset 是预配置的参数组合，agent 可直接复用，无需手动填参数：

| preset 名称 | 用途 |
|---|---|
| `template_html_js_jsonp` | 模板示例，用于学习 preset 结构 |
| `chain_cdn_js_jsonp_img` | 提取图片 URL |
| `chain_cdn_js_jsonp_download` | 提取下载链接 |
| `chain_generic_js_jsonp_value` | 未知站点快速试探 |
| `chain_js_only_jsonp_value` | 已知 JS URL 场景 |

## Agent 常用命令

```bash
# 环境初始化 / 修复
bash scripts/bootstrap.sh
bash scripts/doctor.sh

# 默认读取（优先缓存，不存储）
bash scripts/run_ingest.sh --present --from-cache "https://example.com/article"

# 用户要求刷新内容（实时抓取）
bash scripts/run_ingest.sh --present --refresh "https://example.com/article"

# 用户明确要求保存
bash scripts/run_ingest.sh --store --from-cache "URL"

# 模型输出路径非默认时，手动指定
bash scripts/run_ingest.sh --present --from-cache \
  --llm-output-file /path/to/llm_output.json "URL"

# 查看可用适配器
bash scripts/run_ingest.sh --list-crawlers

# 小红书评论（可选，需先配置 Cookie）
bash scripts/setup_xhs_cookie.sh
ONEFETCH_XHS_COMMENT_MODE='state+api' \
  bash scripts/run_ingest.sh "https://www.xiaohongshu.com/explore/..."

# 知乎被风控时，配置 Cookie 后重试
bash scripts/setup_zhihu_cookie.sh
bash scripts/run_ingest.sh --present --refresh "https://zhuanlan.zhihu.com/p/..."

# 安装浏览器渲染组件（SPA/JS 页面需要）
.venv/bin/python -m pip install -e '.[browser]' && .venv/bin/python -m playwright install chromium
```

### 插件命令

```bash
# 查看插件列表
.venv/bin/python -m onefetch.cli plugin list

# 查看插件 + 可用 preset
.venv/bin/python -m onefetch.cli plugin list --with-presets

# 查看某插件的 preset
.venv/bin/python -m onefetch.cli plugin presets --plugin-id extract_html_js_jsonp

# CSS 选择器提取
.venv/bin/python -m onefetch.cli plugin run extract_css_attr \
  --url "https://example.com" \
  --opt selector=.hero \
  --opt attr=src

# JSONP 字段提取
.venv/bin/python -m onefetch.cli plugin run extract_jsonp_field \
  --opt jsonp_url="https://example.com/api.js?callback=img_url" \
  --opt callback=img_url \
  --opt field=img_url

# 链路提取（使用 preset）
.venv/bin/python -m onefetch.cli plugin run extract_html_js_jsonp \
  --url "https://www.dingtalk.com/wukong" \
  --opt preset=chain_cdn_js_jsonp_img

# 自动探测（callback/field/regex 未知时）
.venv/bin/python -m onefetch.cli plugin run extract_html_js_jsonp \
  --url "https://example.com" \
  --opt auto_detect=true \
  --json

# 失败后诊断（返回 error_code / suggestion / steps）
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
