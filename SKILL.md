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
- 用户要求提取 / 下载页面中的图片
- 用户要求从页面中提取特定元素（下载链接、CSS 属性、JSONP 字段等）
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

3. 默认使用 `scripts/run_cli.sh ingest --present --from-cache "URL"`，优先复用缓存，减少重复抓取。
4. 用户明确要求"最新/重新抓取/刷新"时，使用 `--refresh` 强制实时抓取（即使同时带 `--from-cache` 也会跳过缓存读取）。
5. 默认保持临时缓存写入（`--cache-temp`），便于后续深入分析 / 翻译复用全文。
6. 仅在用户明确要求保存 / 归档时使用 `--store`。默认只保存纯文本，用户要求保存图片时加 `--with-images`。

### LLM 输出回填

7. agent 用 LLM 整理完内容后（生成摘要、要点、标签），**立刻调用 `cache-backfill` 写入缓存**，不要等下次运行：
   ```bash
   bash scripts/run_cli.sh cache-backfill "URL" \
     --json-data '{"summary":"...","key_points":["...","..."],"tags":["..."]}'
   ```
   这样缓存第一时间就是完整的，后续任何操作（翻译、保存、再次查看）都能直接复用。
8. 若 `--store` 时 `llm_outputs_state` 为 `fallback` 或 `missing`，onefetch 会自动用规则从正文重新生成。agent 需用通俗语言提醒：正文已保存，但摘要 / 要点 / 标签为自动整理结果，可能不够准确；用户可稍后要求"重新整理"再覆盖。

### 提取图片（images 命令）

9. 当用户需要页面中的图片时，使用 `images` 命令：
   ```bash
   # 列出图片 URL
   bash scripts/run_cli.sh images "URL"

   # 输出 wsrv.nl 代理 URL（绕过防盗链）
   bash scripts/run_cli.sh images --proxy "URL"

   # 下载图片到本地目录
   bash scripts/run_cli.sh images --download /path/to/dir "URL"
   ```
   适用场景：
   - 用户说"下载这个帖子的图片"、"提取图片链接"
   - 用户说"保存这篇文章的图片"

   `images` 命令走完整的 adapter 流程，自动识别平台并从正确的位置提取图片（小红书从 state JSON、微信从文章内容区、知乎/通用从 img 标签）。

### 图文联合分析（--with-images）

10. 当用户需要图文一起分析（如多模态模型）时，在 `--present` 上加 `--with-images`：
    ```bash
    bash scripts/run_cli.sh ingest --present --with-images --from-cache "URL"
    ```
    输出中 body 保留 `[IMG:N]` 标记表示图片原始位置，同时列出每张图片的原始 URL 和 wsrv.nl 代理 URL：
    ```
    - full_body:
    ...文字内容...
    [IMG:1]
    ...文字内容...
    [IMG:2]
    ...
    - images:
      - [IMG:1]: https://原始URL
        proxy: https://wsrv.nl/?url=...
      - [IMG:2]: https://原始URL
        proxy: https://wsrv.nl/?url=...
    ```

    **占位符说明：**
    - `[IMG:N]` 是图片在原文中的位置标记，N 对应 images 列表的序号
    - 默认输出（不带 `--with-images`）的 body 中不含占位符，是干净的纯文本
    - 生成摘要/要点时，不要把 `[IMG:N]` 当成正文内容

    **给多模态模型分析图片时：**
    - 优先使用原始 URL 让模型直接访问
    - 如果原始 URL 不可访问（防盗链），改用 proxy URL
    - 如果两个 URL 都不可访问，告知用户"该图片无法查看"，仅根据正文整理
    - 将 body 文本 + 图片一起交给模型时，需告知模型 `[IMG:N]` 标记处对应哪张图片

### 获取原始 HTML（--raw）

10. 当需要原始 HTML 数据（如分析页面结构、调试抓取问题）时，使用 `--raw` 模式：
    ```bash
    bash scripts/run_cli.sh ingest --raw "URL"
    ```
    原始 HTML 保存到 `reports/raw/<timestamp>.html`，不进入缓存。agent 可按需处理文件，避免将大量 HTML 加载到上下文。

### 平台特殊处理

10. **小红书评论**：默认不抓取评论。仅在用户需要评论时启用 `ONEFETCH_XHS_COMMENT_MODE='state+api'`。若用户未配置评论 Cookie，引导用户配置（见下方 Cookie 配置说明）。
11. **知乎 Cookie**：知乎问答页面和回答页面无需 Cookie（自动通过 Playwright 渲染获取）。知乎专栏（`zhuanlan.zhihu.com`）需要 Cookie，若出现 `error_code=risk.blocked`，引导用户配置（见下方 Cookie 配置说明）。
12. **知乎问答页面的回答展开**：问答页面默认返回问题 + 高赞 5 个回答（可能截断）。每个回答后标注了 `answer_id`，如需获取某个回答的完整内容，拼接 URL 单独抓取：
    ```
    https://www.zhihu.com/question/{question_id}/answer/{answer_id}
    ```
    其中 `question_id` 从问答页面 URL 获取，`answer_id` 从正文中的 `answer_id: xxx` 获取。

### Cookie 配置说明

需要配置 Cookie 时，引导用户按以下步骤操作：

1. 在浏览器中登录对应平台
2. 获取 Cookie（任选一种方式）：
   - **F12 DevTools**：Network → 点击任意请求 → Headers → 复制 `Cookie:` 的值
   - **浏览器插件**：Cookie-Editor（导出选 Header String）、Get cookies.txt 等
3. 复制 Cookie 后，直接运行脚本（会自动读取剪贴板）：
   - 知乎：`bash scripts/setup_cookie.sh zhihu`
   - 小红书：`bash scripts/setup_cookie.sh xhs`

注意：Cookie 格式必须是 **Header String**（`key=value; key=value; ...`），不能是 Netscape/curl 格式。

### 错误处理

12. 关注结果中的 `error_code`、`error_type`、`retryable`、`action_hint` 字段：
    - `retryable=True`：先自动重试一次，仍失败再告知用户。
    - `action_hint` 非空：包含可直接执行的修复命令（如安装依赖），agent 应尝试自动执行。
    - 常见错误码速查：
      - `dep.playwright_missing` → 安装 Playwright（见 action_hint）
      - `risk.blocked` → 配置对应平台 Cookie
      - `network.timeout` → 重试
      - `route.not_found` → URL 格式有误

### 主流程 vs 插件：如何选择

两种能力解决不同问题：

| 用户需求 | 使用 | 原因 |
|---|---|---|
| 读取 / 总结 / 翻译整篇文章 | 主流程（`run_cli.sh ingest`） | 需要完整正文 |
| 提取页面中的特定元素（图片 URL、下载链接、某个字段） | 插件（`plugin run`） | 只需要一个值 |

判断规则：
- 用户关心的是"文章内容" → 主流程
- 用户关心的是"某个具体的 URL / 值 / 属性" → 插件

## 插件体系

### 核心概念：为什么 SPA 页面不一定需要浏览器

很多 SPA / JS 渲染页面虽然在浏览器里需要执行 JavaScript 才能看到内容，但数据本身往往存在于可直接 HTTP 请求的资源中：

```
用户看到的渲染页面
  └── 浏览器执行 JS 后填充到 DOM

数据的实际来源（可直接请求，不需要浏览器）：
  HTML 页面 → 里面引用了 JS bundle URL
    → JS bundle → 里面包含 API 地址或硬编码数据
      → API（通常是 JSONP 格式）→ 里面包含目标值（图片 URL、下载链接等）
```

插件的链路提取就是沿这条数据链逐步追溯，用正则从每一层提取下一层的地址，最终拿到目标值。**不需要浏览器，速度快，且更稳定。**

### 面对未知页面的推荐流程

```
用户说"帮我提取这个页面的 XXX"
  │
  ├─ 页面是服务端渲染（HTML 里有目标内容）？
  │    → 用 extract_css_attr 按选择器提取
  │
  ├─ 用户已经给出了 JSONP 接口地址？
  │    → 用 extract_jsonp_field 直接提取字段
  │
  ├─ 页面是 SPA / 目标值不在 HTML 中？
  │    → 用 extract_html_js_jsonp，推荐步骤：
  │      1. 先试 auto_detect=true 自动探测
  │      2. 若探测成功，直接使用返回的参数
  │      3. 若失败，用 plugin doctor 诊断，根据 suggestion 调整
  │
  └─ 完全不确定？
       → 先用 extract_html_js_jsonp + auto_detect=true 探测
         它会分析页面结构并尝试自动找到数据链路
```

### 插件列表

当前可用插件（可通过 `.venv/bin/python -m onefetch.cli plugin list` 查看）：

#### 1. `extract_css_attr`

- **作用**：从 HTML 中按 CSS 选择器提取属性或文本。
- **适用**：目标内容直接存在于 HTML 中（服务端渲染页面）。
- **局限**：对 SPA 页面无效 — HTML 中只有空骨架（如"加载中..."），目标值不在 DOM 里。
- **关键参数**：
  - `selector`：支持 `#id`、`.class`、`tag`、`tag.class`
  - `attr`：默认 `src`，可用 `text`
  - `index`：可选，默认 `0`

#### 2. `extract_jsonp_field`

- **作用**：从 JSONP 响应提取字段值。
- **适用**：已知 JSONP 接口地址，只需提取其中某个字段。
- **关键参数**：
  - `jsonp_url`：JSONP 地址（不传则使用 `--url`）
  - `callback`：默认 `callback`
  - `field`：默认 `img_url`

#### 3. `extract_html_js_jsonp`（最常用）

- **作用**：链路提取（HTML → JS → JSONP → 字段），沿 SPA 的数据链逐层追溯。
- **适用**：目标值不在 HTML 中，需要追溯到 JS bundle 或 API 中获取。这是处理 SPA 页面元素提取的首选。
- **关键参数**：
  - `callback`：JSONP 回调函数名，默认 `img_url`
  - `field`：要提取的字段名，默认 `img_url`
  - `append_version`：`true/false`，是否拼接 `?v=...`
  - `preset`：使用内置预设参数（推荐优先尝试）
  - `auto_detect`：`true` 时自动分析页面结构并探测数据链路
  - `js_url_regexes` / `jsonp_base_regexes`：自定义正则，支持多候选（数组或 `a||b`）
  - 可选直传：`html`、`js_body`、`jsonp_body`（便于调试 / 离线测试）

### 插件选型速查

| 场景 | 选择 | 示例命令 |
|---|---|---|
| HTML 里有目标内容 | `extract_css_attr` | `plugin run extract_css_attr --url URL --opt selector=.hero --opt attr=src` |
| 已知 JSONP 接口地址 | `extract_jsonp_field` | `plugin run extract_jsonp_field --opt jsonp_url=URL --opt field=img_url` |
| SPA 页面提取图片 | `extract_html_js_jsonp` + preset | `plugin run extract_html_js_jsonp --url URL --opt preset=chain_cdn_js_jsonp_img` |
| SPA 页面提取下载链接 | `extract_html_js_jsonp` + preset | `plugin run extract_html_js_jsonp --url URL --opt preset=chain_cdn_js_jsonp_download` |
| 未知站点，不确定结构 | `extract_html_js_jsonp` + auto_detect | `plugin run extract_html_js_jsonp --url URL --opt auto_detect=true --json` |
| 提取失败，需要诊断 | plugin doctor | `plugin doctor extract_html_js_jsonp --url URL --opt preset=chain_generic_js_jsonp_value --json` |

### 内置 preset

preset 是预配置的参数组合，agent 可直接复用，无需手动填参数：

| preset 名称 | 用途 | 推荐场景 |
|---|---|---|
| `chain_cdn_js_jsonp_img` | 提取图片 URL | 用户要提取页面中的动态图片 |
| `chain_cdn_js_jsonp_download` | 提取下载链接 | 用户要提取页面中的下载地址 |
| `chain_generic_js_jsonp_value` | 通用字段提取 | 未知站点，先用此 preset 试探 |
| `chain_js_only_jsonp_value` | 已知 JS URL 场景 | 已经拿到 JS 地址，跳过 HTML 定位 |
| `template_html_js_jsonp` | 模板示例 | 学习 preset 结构，用于编写新 preset |

## Agent 常用命令

```bash
# 环境初始化 / 修复
bash scripts/bootstrap.sh
bash scripts/doctor.sh

# 默认读取（优先缓存，不存储）
bash scripts/run_cli.sh ingest --present --from-cache "https://example.com/article"

# 用户要求刷新内容（实时抓取）
bash scripts/run_cli.sh ingest --present --refresh "https://example.com/article"

# 用户明确要求保存（纯文本）
bash scripts/run_cli.sh ingest --store --from-cache "URL"

# 保存文本 + 图片
bash scripts/run_cli.sh ingest --store --with-images --from-cache "URL"

# LLM 整理完内容后，立刻回填到缓存
bash scripts/run_cli.sh cache-backfill "URL" \
  --json-data '{"summary":"...","key_points":["..."],"tags":["..."]}'

# 提取图片 URL
bash scripts/run_cli.sh images "URL"

# 下载图片到本地
bash scripts/run_cli.sh images --download /path/to/dir "URL"

# 输出 wsrv.nl 代理 URL（防盗链场景）
bash scripts/run_cli.sh images --proxy "URL"

# 获取原始 HTML（分析页面结构、调试）
bash scripts/run_cli.sh ingest --raw "URL"

# 查看可用适配器
bash scripts/run_cli.sh ingest --list-crawlers

# 小红书评论（可选，需先配置 Cookie）
bash scripts/setup_cookie.sh xhs
ONEFETCH_XHS_COMMENT_MODE='state+api' \
  bash scripts/run_cli.sh ingest "https://www.xiaohongshu.com/explore/..."

# 知乎被风控时，配置 Cookie 后重试
bash scripts/setup_cookie.sh zhihu
bash scripts/run_cli.sh ingest --present --refresh "https://zhuanlan.zhihu.com/p/..."

# 安装浏览器渲染组件（SPA/JS 页面需要）
.venv/bin/python -m pip install -e '.[browser]' && .venv/bin/python -m playwright install chromium
```

### 插件命令

```bash
# 查看插件列表
bash scripts/run_cli.sh plugin list

# 查看插件 + 可用 preset
bash scripts/run_cli.sh plugin list --with-presets

# 查看某插件的 preset
bash scripts/run_cli.sh plugin presets --plugin-id extract_html_js_jsonp

# CSS 选择器提取
bash scripts/run_cli.sh plugin run extract_css_attr \
  --url "https://example.com" \
  --opt selector=.hero \
  --opt attr=src

# JSONP 字段提取
bash scripts/run_cli.sh plugin run extract_jsonp_field \
  --opt jsonp_url="https://example.com/api.js?callback=img_url" \
  --opt callback=img_url \
  --opt field=img_url

# 链路提取（使用 preset）
bash scripts/run_cli.sh plugin run extract_html_js_jsonp \
  --url "https://www.dingtalk.com/wukong" \
  --opt preset=chain_cdn_js_jsonp_img

# 自动探测（callback/field/regex 未知时）
bash scripts/run_cli.sh plugin run extract_html_js_jsonp \
  --url "https://example.com" \
  --opt auto_detect=true \
  --json

# 失败后诊断（返回 error_code / suggestion / steps）
bash scripts/run_cli.sh plugin doctor extract_html_js_jsonp \
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
