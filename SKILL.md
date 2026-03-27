---
name: onefetch
description: 读取、总结、翻译任意网页内容，或从页面中提取特定元素。当用户给出一个 URL 并要求查看、阅读、总结、翻译、保存网页内容时使用；当用户要求从网页中提取图片、下载链接、特定字段等元素时也使用；当用户要求总结 B 站视频内容时也使用（通过字幕提取）；当用户要求总结抖音视频内容或获取视频文字版时也使用（通过抖音 AI 助手）；当用户分享小红书图片笔记并要求解析图片中的文字时也使用（通过豆包 OCR）。支持小红书、抖音、微信公众号、知乎、B 站、通用网页及 SPA/JS 渲染页面。
---

# OneFetch Skill

## 何时使用

- 用户给出 URL 并要求读取 / 总结 / 翻译网页内容
- 用户要求读取小红书笔记（含可选评论）
- 用户要求读取微信公众号文章
- 用户要求读取知乎专栏文章或问答
- 用户要求读取 / 总结 B 站视频内容（通过 AI 字幕）或 B 站专栏文章
- 用户要求提取 / 下载页面中的图片
- 用户要求从页面中提取特定元素（下载链接、CSS 属性、JSONP 字段等）
- 用户给出目录页 URL，要求批量抓取全部内容
- 用户确认后需要保存 / 归档抓取结果

## 支持的平台

| 平台 | 自动识别的 URL | 说明 | Cookie |
|---|---|---|---|
| 小红书 | `xiaohongshu.com`、`xhslink.com` | 笔记正文 + 可选评论 | 评论需要 |
| 抖音 | `douyin.com/video/*`、`v.douyin.com` | 视频总结 + 完整文字版（通过抖音 AI 助手） | 需要 |
| 微信公众号 | `mp.weixin.qq.com` | 文章正文 | 不需要 |
| 知乎 | `zhuanlan.zhihu.com/p/*`、`zhihu.com/question/*` | 专栏文章、问答 | 专栏需要；问答不需要 |
| B 站 | `bilibili.com/video/*`、`bilibili.com/opus/*` | 视频（AI 字幕）、专栏 | 字幕需要；专栏不需要 |
| 扩展站点 | 由已安装扩展定义（如 `b.geekbang.org`） | 专用解析，噪音更少 | 视站点而定 |
| 通用网页 | 所有其他 URL | 自动去噪提取正文；SPA/JS 页面自动浏览器渲染 | 视站点而定 |

agent 不需要手动选择适配器，CLI 根据 URL 自动路由。短链（如 `xhslink.com`）也会自动展开处理。

## 路由总览：拿到 URL 后先判断走哪条路

```
用户给出 URL + 需求
  │
  ├─ 用户关心"文章内容"（读取/总结/翻译/保存）
  │    → 主流程 ingest（见下方"读取网页"）
  │
  ├─ 用户关心"从目录页批量抓全部内容"
  │    → discover 批量流程（见下方"批量抓取与合集"）
  │
  ├─ 用户关心"页面中的图片"
  │    → images 命令（见下方"提取图片"）
  │
  └─ 用户关心"某个具体的 URL / 值 / 属性"（下载链接、CSS、JSONP 字段）
       → 插件 plugin（见下方"插件体系"）
```

---

## 环境准备

首次使用或环境异常时：
```bash
bash scripts/bootstrap.sh
bash scripts/doctor.sh
```

遇到 `error_code=dep.playwright_missing` 时，按 `action_hint` 字段的命令安装，通常为：
```bash
.venv/bin/python -m pip install -e '.[browser]' && .venv/bin/python -m playwright install chromium
```

---

## 读取网页（主流程 ingest）

### 默认读取

```bash
bash scripts/run_cli.sh ingest --present --from-cache "URL"
```

- `--present`：输出 LLM 友好的规范化格式
- `--from-cache`：优先复用临时缓存，减少重复抓取
- `--cache-temp`：写入临时缓存（默认启用，无需显式传）

### 刷新内容

用户明确要求"最新/重新抓取/刷新"时：
```bash
bash scripts/run_cli.sh ingest --present --refresh "URL"
```

`--refresh` 会跳过缓存读取，强制实时抓取。

### 保存 / 归档

仅在用户明确要求保存时使用 `--store`：
```bash
# 仅保存正文
bash scripts/run_cli.sh ingest --store --from-cache "URL"

# 保存正文 + 图片
bash scripts/run_cli.sh ingest --store --with-images --from-cache "URL"
```

保存前 agent 主动确认一次：「是否连图片一起保存？默认仅保存正文。」

保存产物写入 `data/<timestamp>-<hash>/`：
- `feed.json`：结构化数据（含 `llm_outputs`，暂无则为空结构）
- `note.md`：人可读归档（仅在已有 LLM 结果时写入摘要/要点/标签）
- `images/`：图片副本（仅 `--with-images` 时下载）

若内容已保存但后续才决定要图片，可直接使用缓存补下载，不需要重新抓取页面。

### 翻译网页内容

1. 先用 `ingest --present --from-cache "URL"` 获取全文
2. agent 基于返回的 `full_body` 进行翻译，直接呈现给用户
3. 如果用户翻译后还要求总结/提取要点，再基于原文生成 summary/key_points/tags 并 backfill

### `--present` 输出字段说明

`--present` 返回的每条结果包含以下字段：

| 字段 | 说明 |
|---|---|
| `status` | 状态（ok / error） |
| `crawler` | 使用的适配器 ID |
| `source_url` | 原始 URL |
| `title` | 标题 |
| `author` | 作者 |
| `published_at` | 发布时间 |
| `comments` | 评论数和来源 |
| `key_points` | CLI 自动提取的关键句（非 LLM 生成） |
| `summary` | 正文预览（截断） |
| `full_body` | 完整去噪正文（代码块包裹） |
| `llm_summary` | LLM 生成的摘要（若缓存中有） |
| `llm_outputs_state` | LLM 输出状态（none / cached / backfilled） |
| `llm_key_points` | LLM 生成的要点列表 |
| `llm_tags` | LLM 生成的标签 |
| `cache_path` | 临时缓存文件路径 |

默认输出的 `full_body` 是干净的纯文本，不含图片占位符。加 `--with-images` 后 body 中会保留 `[IMG:N]` 标记，并额外输出 `images` 列表。

### 获取原始 HTML

调试或分析页面结构时：
```bash
bash scripts/run_cli.sh ingest --raw "URL"
```
原始 HTML 保存到 `reports/raw/<timestamp>.html`，不进入缓存。避免将大量 HTML 加载到上下文。

---

## LLM 输出回填（cache-backfill）

agent 用 LLM 整理完内容后（生成摘要、要点、标签），立刻写入缓存：

```bash
bash scripts/run_cli.sh cache-backfill "URL" \
  --json-data '{"summary":"...","key_points":["...","..."],"tags":["..."]}'
```

### 何时回填

- agent 为用户生成了结构化的 summary / key_points / tags 时，就应该 backfill
- 仅口头回复用户、未生成结构化内容时，不需要 backfill

### 注意事项

- 生成 summary / key_points / tags 时，必须忽略并删除图片标记（`[IMG:N]`、`[IMG_CAPTION:N]`），这些只用于图文位置映射，不是正文语义
- 回填后，后续任何操作（翻译、保存、再次查看）都能直接复用 LLM 结果

---

## 提取图片（images 命令）

```bash
# 列出图片 URL
bash scripts/run_cli.sh images "URL"

# 输出 wsrv.nl 代理 URL（绕过防盗链）
bash scripts/run_cli.sh images --proxy "URL"

# 下载图片到本地目录
bash scripts/run_cli.sh images --download /path/to/dir "URL"
```

`images` 命令走完整的 adapter 流程，自动从正确的位置提取图片（小红书从 state JSON、微信从文章内容区、知乎/通用从 img 标签）。

### 图文联合分析（--with-images）

当用户需要图文一起分析（如多模态模型）时：
```bash
bash scripts/run_cli.sh ingest --present --with-images --from-cache "URL"
```

输出中 body 保留 `[IMG:N]` 标记表示图片原始位置，同时列出每张图片的 URL：
```
- full_body:
...文字内容...
[IMG:1]
...文字内容...
[IMG:2]
- images:
  - [IMG:1]: https://原始URL
    proxy: https://wsrv.nl/?url=...
  - [IMG:2]: https://原始URL
    proxy: https://wsrv.nl/?url=...
```

占位符说明：
- `[IMG:N]`：图片在原文中的位置，N 对应 images 列表序号
- `[IMG_CAPTION:N]`：图片说明文本

给多模态模型分析图片时：
- 优先使用原始 URL 让模型直接访问
- 原始 URL 不可访问（防盗链）时，改用 proxy URL
- 两个都不可访问时，告知用户该图片无法查看，仅根据正文整理

---

## 批量抓取与合集（discover）

当用户给出目录页/入口页 URL，要求批量抓取全部内容时使用。

### 典型流程

```bash
# 第 1 步：先看会发现哪些 URL
bash scripts/run_cli.sh discover "SEED_URL" --present

# 第 2 步：确认后批量抓取 + 保存 + 图片（完整链路）
bash scripts/run_cli.sh discover "SEED_URL" \
  --ingest --ingest-store --ingest-with-images --ingest-from-cache
```

### 输出结构

发现报告：`reports/discover/seed-<key>.json`（多 seed 时为 `batch-<key>.json`）

保存为合集时，结果整理到 `data/collections/<key>/`：
- `manifest.json`：用户可读索引（`seed_urls`、`discovered_urls`、`items`）
- `items/`：按顺序编号的文章目录（`001-...`、`002-...`，每个含 `feed.json` + `note.md`）

同一个 key 再次执行会覆盖更新为最新合集。`--ingest-store` 时 seed_url 对应的页面也会一起保存。

### discover 参数速查

| 参数 | 说明 |
|---|---|
| `--present` | 展示发现的 URL 列表 |
| `--ingest` | 发现后立即批量抓取 |
| `--ingest-store` | 抓取结果持久化到 data/ |
| `--ingest-with-images` | 下载图片 |
| `--ingest-from-cache` | 抓取时优先缓存 |
| `--ingest-refresh` | 强制实时抓取 |
| `--expander EXPANDER_ID` | 强制使用特定扩展器 |

### discover 依赖扩展的 expander

`discover` 需要目标站点安装了提供 expander 的扩展才能工作。如果用户给出的 URL 没有对应扩展，agent 应：
1. 检查是否有可用扩展：`bash scripts/run_cli.sh ext list --remote --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"`
2. 有则安装后重试
3. 没有则告知用户：「该站点暂不支持自动发现内容页，你可以手动提供要抓取的 URL 列表。」

---

## 平台特殊处理

### 小红书

- 默认不抓取评论。仅在用户需要评论时启用：
  ```bash
  ONEFETCH_XHS_COMMENT_MODE='state+api' \
    bash scripts/run_cli.sh ingest --present "https://www.xiaohongshu.com/explore/..."
  ```
- 评论需要 Cookie，未配置时引导用户配置

#### 图片内容识别（豆包 OCR）

很多小红书笔记的核心内容在图片中（图片里是文字），正文 `desc` 可能很短甚至为空。

**判断时机：** 当 ingest 返回的 `full_body` 几乎为空（仅标题+标签）但有多张图片时，提示用户：
「这篇笔记的内容主要在图片里，需要我解析图片中的文字吗？」

**不要自动 OCR**，原因：
- 图片可能很多（10+张），每张需要单独调用豆包 API
- 使用用户个人账号 Cookie，需控制调用频率
- 不是所有图片都包含文字（可能是纯配图）

**操作流程：**

1. 用户确认后，逐张调用豆包 API 提取文字：
   ```bash
   .venv/bin/python scripts/doubao_chat.py "提取图片中的所有文字，保持排版结构：<图片URL>"
   ```
2. **串行调用，每张间隔 2-3 秒**，避免触发风控
3. 将每张图片的 OCR 结果按顺序整合，呈现给用户
4. 如果用户要求，可以 `cache-backfill` 回填到缓存

**用户主动要求时也可以使用：** 用户说「帮我看看图片里写了什么」「解析图片内容」等。

**Cookie 配置：** 豆包 API 需要登录态 Cookie。
首次使用时引导用户配置：`bash scripts/setup_cookie.sh doubao.com`

### 抖音

抖音视频通过抖音内置的 AI 助手获取内容，不直接爬取页面。

- **需要 Cookie**：`bash scripts/setup_cookie.sh douyin.com`
- **自动两步获取**：adapter 自动先总结视频内容，再用深度思考模式获取完整文字版
- **支持短链接**：`v.douyin.com` 短链会自动解析为完整 URL
- **输出格式**：body 包含「视频总结」和「完整文字版」两个部分

#### 独立脚本（灵活使用）

除了通过 `ingest` 命令自动处理，也可以直接用脚本：
```bash
# 总结视频
.venv/bin/python scripts/douyin_ai.py <视频URL或ID> "总结视频内容"

# 完整文字版（深度思考模式）
.venv/bin/python scripts/douyin_ai.py --deep <视频URL或ID> "给我完整的视频文字版"

# 两步走：总结 + 完整文字版
.venv/bin/python scripts/douyin_ai.py --full <视频URL或ID>
```

#### 注意事项

- 抖音 AI 助手对部分视频可能无法返回完整文字版，此时总结仍然可用
- 深度思考模式（`--deep`）耗时更长但结果更完整
- 视频内容分两类：
  - **知识分享类**（类似 B 站）：完整文字版最有价值
  - **画面叙事类**：视频总结更有价值
- Cookie 有效期有限，过期后需重新配置

### 知乎

- **问答页面**：无需 Cookie，自动通过 Playwright 渲染获取。默认返回问题 + 高赞 5 个回答（可能截断）。每个回答后标注了 `answer_id`，如需完整内容：
  ```
  https://www.zhihu.com/question/{question_id}/answer/{answer_id}
  ```
- **专栏文章**：需要 Cookie。出现 `error_code=risk.blocked` 时引导配置

### B 站

- **视频**：自动通过 API 获取信息和 AI 字幕。字幕需要 Cookie。无 Cookie 时仍可获取标题、作者、简介
- **专栏**：无需 Cookie，自动 Playwright 渲染

---

## 外置扩展

扩展仓库：`https://github.com/HuaxinLab/onefetch-extensions`
（若设置了 `ONEFETCH_EXT_REPO` 环境变量则优先使用）

### 当前可用扩展

| 扩展 ID | 站点 | 提供 | 说明 |
|---|---|---|---|
| `geekbang` | `b.geekbang.org` | adapter + expander | 极客时间课程解析，支持 discover 批量抓取 |

### 扩展管理命令

```bash
# 查看远程可安装的扩展
bash scripts/run_cli.sh ext list --remote --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"

# 安装扩展
bash scripts/run_cli.sh ext install <ext_id> --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"

# 更新扩展（已安装但效果异常时）
bash scripts/run_cli.sh ext update <ext_id> --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"

# 查看已安装的扩展
bash scripts/run_cli.sh ext list

# 移除扩展
bash scripts/run_cli.sh ext remove <ext_id>
```

URL 路由时会自动检测已安装扩展的 adapter，agent 无需手动判断。

若扩展仓库不可用，告知用户：「我可以先按通用模式读取；需要更干净的站点专用结果时，可以在扩展仓库可用后启用专用解析。」

---

## 风险控制（safe 策略）

以下平台在批量抓取时建议使用 safe 节奏：
- 小红书
- 知乎（尤其是带 Cookie 的专栏）
- B 站（带 Cookie 的视频字幕）
- 用户明确担心风控的站点

agent 先征得用户同意：「这个站点建议用更稳妥的抓取节奏（会更慢），以降低异常风险。是否按稳妥模式执行？」

safe 策略规则：
- 串行执行，一次只处理 1 个 URL
- 分批抓取，每批 5~10 条 URL
- URL 之间停顿 2~6 秒（随机抖动）
- 批次之间停顿 60~180 秒
- 优先 `--from-cache`，仅用户明确要求时才 `--refresh`
- 重试最多 1 次，失败后告知用户

用户明确要求"正常速度"时可切回 normal。

---

## Cookie 配置

需要配置 Cookie 时，引导用户按以下步骤操作：

1. 在浏览器中登录对应平台
2. 获取 Cookie（任选一种）：
   - F12 DevTools：Network → 任意请求 → Headers → 复制 `Cookie:` 的值
   - 浏览器插件：Cookie-Editor（导出选 Header String）
3. 复制 Cookie 后运行脚本（自动读取剪贴板）：
   ```bash
   bash scripts/setup_cookie.sh <域名>
   ```
   - 知乎专栏：`bash scripts/setup_cookie.sh zhihu.com`
   - 小红书评论：`bash scripts/setup_cookie.sh xiaohongshu.com`
   - B 站视频字幕：`bash scripts/setup_cookie.sh bilibili.com`
   - 其他网站：`bash scripts/setup_cookie.sh example.com`

配置后写入本地加密库 `.onefetch/secrets.db`，后续自动加载。
首次使用会自动创建主密钥文件 `.onefetch/master.key`（位于项目目录）。

读取优先级：
1. 本地加密库
2. 环境变量（仅兜底）

历史明文 cookie 一次性导入（指定文件）：
```bash
.venv/bin/python -m onefetch.secret_cli import-cookies --file /path/to/zhihu.com_cookie.txt
.venv/bin/python -m onefetch.secret_cli import-cookies --file /path/to/random_cookie.txt --domain zhihu.com
.venv/bin/python -m onefetch.secret_cli import-env --name ONEFETCH_COOKIE_ZHIHU_COM --domain zhihu.com
```

导入后规范化 key（去重并统一为标准域名，如 `zhihu.com`、`douyin.com`）：
```bash
.venv/bin/python -m onefetch.secret_cli normalize-cookies
```

查看/读取/删除加密库中的密钥：
```bash
.venv/bin/python -m onefetch.cli secret list --type cookie
.venv/bin/python -m onefetch.cli secret get cookie.zhihu.com
.venv/bin/python -m onefetch.cli secret get cookie.zhihu.com --no-masked
.venv/bin/python -m onefetch.cli secret delete cookie.zhihu.com
```

注意：Cookie 格式必须是 Header String（`key=value; key=value; ...`），不能是 Netscape/curl 格式。

---

## 错误处理

关注结果中的 `error_code`、`error_type`、`retryable`、`action_hint` 字段。

### 错误码速查

| 错误码 | 说明 | 处理 |
|---|---|---|
| `dep.playwright_missing` | 缺少浏览器组件 | 按 `action_hint` 安装 |
| `auth.cookie_required` | 页面需要登录 | 引导用户配置 Cookie |
| `risk.blocked` | 平台风控拦截 | 配置 Cookie 后重试 |
| `network.timeout` | 网络超时 | 重试；外网地址考虑代理 |
| `route.not_found` | URL 格式有误 | 检查 URL |

### 处理流程

1. `retryable=True` → 自动重试一次
2. `action_hint` 非空 → 包含可直接执行的修复命令，agent 尝试自动执行
3. 重试仍失败 → 告知用户错误原因和建议
4. 网络超时且为外网地址 → 提示用户是否需要代理

### 代理配置

用户提供代理地址后，通过环境变量传入：
```bash
HTTPS_PROXY=<代理地址> bash scripts/run_cli.sh ingest --present "URL"
```
支持 `HTTPS_PROXY`、`HTTP_PROXY`、`ALL_PROXY`，HTTP 请求和 Playwright 都会自动使用。

---

## 面向用户的提示模板

agent 在以下场景主动提示用户：

| 场景 | 建议提示 |
|---|---|
| 保存文件里暂无摘要/要点/标签 | 「正文已保存完成。需要我基于正文补充整理摘要和标签吗？」 |
| 需要刷新最新内容 | 「我可以先刷新网页再整理，拿到最新版本的正文。」 |
| 站点需要登录态 | 「这个页面需要登录后才能稳定读取。我可以引导你配置一次 Cookie。」 |
| 批量抓取建议 safe 模式 | 「这个站点建议用更稳妥的抓取节奏（会更慢）。是否按稳妥模式执行？」 |
| 保存前确认图片 | 「是否连图片一起保存？默认仅保存正文。」 |

---

## 插件体系

插件用于从页面中提取特定元素（图片 URL、下载链接、CSS 属性、JSONP 字段等），不需要读取完整文章内容。

### 核心概念

很多 SPA / JS 渲染页面的数据不需要浏览器就能获取：

```
HTML 页面 → 引用了 JS bundle URL
  → JS bundle → 包含 API 地址或硬编码数据
    → API（通常 JSONP）→ 包含目标值
```

插件沿这条数据链逐层追溯，用正则提取，不需要浏览器，速度快且稳定。

### 面对未知页面的推荐流程

```
用户说"帮我提取这个页面的 XXX"
  │
  ├─ HTML 里有目标内容（服务端渲染）？
  │    → extract_css_attr
  │
  ├─ 用户已给出 JSONP 接口地址？
  │    → extract_jsonp_field
  │
  ├─ SPA 页面 / 不确定？
  │    → extract_html_js_jsonp + auto_detect=true 自动探测
  │      → 成功：直接使用
  │      → 失败：plugin doctor 诊断，按 suggestion 调整
  ```

### 插件列表

#### `extract_css_attr`
- 从 HTML 中按 CSS 选择器提取属性或文本
- 参数：`selector`（CSS 选择器）、`attr`（默认 `src`，可用 `text`）、`index`（默认 `0`）
- 局限：对 SPA 页面无效

#### `extract_jsonp_field`
- 从 JSONP 响应提取字段值
- 参数：`jsonp_url`、`callback`（默认 `callback`）、`field`（默认 `img_url`）

#### `extract_html_js_jsonp`（最常用）
- 链路提取（HTML → JS → JSONP → 字段）
- 关键参数：
  - `preset`：内置预设（推荐优先使用）
  - `auto_detect`：`true` 时自动探测数据链路
  - `callback` / `field`：JSONP 回调名和字段名
  - `js_url_regexes` / `jsonp_base_regexes`：自定义正则

### 内置 preset

| preset | 用途 | 场景 |
|---|---|---|
| `chain_cdn_js_jsonp_img` | 提取图片 URL | 动态图片 |
| `chain_cdn_js_jsonp_download` | 提取下载链接 | 下载地址 |
| `chain_generic_js_jsonp_value` | 通用字段提取 | 未知站点先用此试探 |
| `chain_js_only_jsonp_value` | 已知 JS URL | 跳过 HTML 定位 |

### 插件选型速查

| 场景 | 插件 | 示例 |
|---|---|---|
| HTML 中有目标内容 | `extract_css_attr` | `--opt selector=.hero --opt attr=src` |
| 已知 JSONP 接口 | `extract_jsonp_field` | `--opt jsonp_url=URL --opt field=img_url` |
| SPA 提取图片 | `extract_html_js_jsonp` | `--opt preset=chain_cdn_js_jsonp_img` |
| SPA 提取下载链接 | `extract_html_js_jsonp` | `--opt preset=chain_cdn_js_jsonp_download` |
| 未知站点 | `extract_html_js_jsonp` | `--opt auto_detect=true --json` |
| 提取失败诊断 | `plugin doctor` | `--opt preset=chain_generic_js_jsonp_value --json` |

`--json` 用于获取结构化 JSON 输出，便于 agent 解析和后续处理。

---

## 命令速查

### 主流程

```bash
# 环境初始化
bash scripts/bootstrap.sh && bash scripts/doctor.sh

# 默认读取（优先缓存）
bash scripts/run_cli.sh ingest --present --from-cache "URL"

# 刷新内容（实时抓取）
bash scripts/run_cli.sh ingest --present --refresh "URL"

# 保存纯文本
bash scripts/run_cli.sh ingest --store --from-cache "URL"

# 保存文本 + 图片
bash scripts/run_cli.sh ingest --store --with-images --from-cache "URL"

# 图文联合分析
bash scripts/run_cli.sh ingest --present --with-images --from-cache "URL"

# 获取原始 HTML
bash scripts/run_cli.sh ingest --raw "URL"

# 查看可用适配器
bash scripts/run_cli.sh ingest --list-crawlers
```

### LLM 回填

```bash
bash scripts/run_cli.sh cache-backfill "URL" \
  --json-data '{"summary":"...","key_points":["..."],"tags":["..."]}'
```

### 图片

```bash
bash scripts/run_cli.sh images "URL"
bash scripts/run_cli.sh images --proxy "URL"
bash scripts/run_cli.sh images --download /path/to/dir "URL"
```

### 批量抓取

```bash
# 先看发现了哪些 URL
bash scripts/run_cli.sh discover "SEED_URL" --present

# 批量抓取 + 保存 + 图片（完整链路）
bash scripts/run_cli.sh discover "SEED_URL" \
  --ingest --ingest-store --ingest-with-images --ingest-from-cache
```

### 抖音视频

```bash
# 通过 ingest 自动获取（总结 + 文字版）
bash scripts/run_cli.sh ingest --present "https://www.douyin.com/video/xxx"
bash scripts/run_cli.sh ingest --present "https://v.douyin.com/xxx/"

# 独立脚本
.venv/bin/python scripts/douyin_ai.py <视频URL或ID> "总结视频内容"
.venv/bin/python scripts/douyin_ai.py --deep <视频URL或ID> "给我完整的视频文字版"
.venv/bin/python scripts/douyin_ai.py --full <视频URL或ID>

# 配置 cookie
bash scripts/setup_cookie.sh douyin.com
```

### 小红书评论

```bash
bash scripts/setup_cookie.sh xiaohongshu.com
ONEFETCH_XHS_COMMENT_MODE='state+api' \
  bash scripts/run_cli.sh ingest --present "URL"
```

### 豆包聊天（图片 OCR / 多模态）

```bash
# 纯文本聊天
.venv/bin/python scripts/doubao_chat.py "你好"

# 图片内容识别（传 URL）
.venv/bin/python scripts/doubao_chat.py "提取图片中的所有文字，保持排版结构：<图片URL>"

# 指定 cookie 文件
.venv/bin/python scripts/doubao_chat.py --cookie /path/to/cookie "message"

# 配置 cookie
bash scripts/setup_cookie.sh doubao.com
```

### 扩展管理

```bash
bash scripts/run_cli.sh ext list --remote --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"
bash scripts/run_cli.sh ext install <ext_id> --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"
bash scripts/run_cli.sh ext update <ext_id> --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"
bash scripts/run_cli.sh ext list
bash scripts/run_cli.sh ext remove <ext_id>
```

### 插件

```bash
# 插件列表
bash scripts/run_cli.sh plugin list --with-presets

# CSS 选择器提取
bash scripts/run_cli.sh plugin run extract_css_attr \
  --url "URL" --opt selector=.hero --opt attr=src

# JSONP 字段提取
bash scripts/run_cli.sh plugin run extract_jsonp_field \
  --opt jsonp_url="URL" --opt callback=img_url --opt field=img_url

# 链路提取（preset）
bash scripts/run_cli.sh plugin run extract_html_js_jsonp \
  --url "URL" --opt preset=chain_cdn_js_jsonp_img

# 自动探测
bash scripts/run_cli.sh plugin run extract_html_js_jsonp \
  --url "URL" --opt auto_detect=true --json

# 失败诊断
bash scripts/run_cli.sh plugin doctor extract_html_js_jsonp \
  --url "URL" --opt preset=chain_generic_js_jsonp_value --json
```

### Cookie 配置

```bash
bash scripts/setup_cookie.sh zhihu.com
bash scripts/setup_cookie.sh xiaohongshu.com
bash scripts/setup_cookie.sh bilibili.com
bash scripts/setup_cookie.sh <域名>
.venv/bin/python -m onefetch.secret_cli import-cookies --file /path/to/zhihu.com_cookie.txt
.venv/bin/python -m onefetch.secret_cli normalize-cookies
.venv/bin/python -m onefetch.cli secret list --type cookie
```

### 浏览器组件安装

```bash
.venv/bin/python -m pip install -e '.[browser]' && .venv/bin/python -m playwright install chromium
```

---

## 扩展联调（仅维护模式）

`bash scripts/smoke_extensions.sh` 仅用于开发/发布前联调，不用于日常用户请求。

---

## 参考文档

- 用户说明：`README.md`
- 文档索引：`references/INDEX.md`
- 架构：`references/ARCHITECTURE.md`
- 需求：`references/REQUIREMENTS.md`
- 工程：`references/ENGINEERING.md`
