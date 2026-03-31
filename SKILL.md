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

支持平台：小红书、抖音、微信公众号、知乎、B 站、扩展站点、通用网页。CLI 根据 URL 自动路由，无需手动选择适配器。各平台详情见 [references/SKILL_PLATFORMS.md](./references/SKILL_PLATFORMS.md)。

## 路由总览：拿到 URL 后先判断走哪条路

```
用户给出 URL + 需求
  │
  ├─ 用户关心"文章内容"（读取/总结/翻译/保存）
  │    → 主流程 ingest（见下方"读取网页"）
  │
  ├─ 用户关心"从目录页批量抓全部内容"
  │    → discover 批量流程（见下方"批量抓取"）
  │
  ├─ 用户关心"页面中的图片"
  │    → images 命令（见下方"提取图片"）
  │
  └─ 用户关心"某个具体的 URL / 值 / 属性"（下载链接、CSS、JSONP 字段）
       → 插件 plugin（见 references/SKILL_PLUGINS.md）
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

```bash
# 默认读取（优先缓存）
bash scripts/run_cli.sh ingest --present --from-cache "URL"

# 刷新内容（用户要求"最新/重新抓取/刷新"时）
bash scripts/run_cli.sh ingest --present --refresh "URL"

# 保存（仅用户明确要求时）
bash scripts/run_cli.sh ingest --store --from-cache "URL"

# 保存 + 图片
bash scripts/run_cli.sh ingest --store --with-images --from-cache "URL"
```

保存前 agent 主动确认：「是否连图片一起保存？默认仅保存正文。」

### 翻译网页内容

1. 先用 `ingest --present --from-cache "URL"` 获取全文
2. agent 基于返回的 `full_body` 进行翻译，直接呈现给用户
3. 如需总结/提取要点，再基于原文生成 summary/key_points/tags 并 backfill

### 获取原始 HTML

调试或分析页面结构时：
```bash
bash scripts/run_cli.sh ingest --raw "URL"
```

输出字段和格式详情见 [references/SKILL_FIELDS.md](./references/SKILL_FIELDS.md)。

---

## LLM 回填

agent 为用户生成了结构化的 summary / key_points / tags 后，立刻写入缓存：
```bash
bash scripts/run_cli.sh cache-backfill "URL" \
  --json-data '{"summary":"...","key_points":["...","..."],"tags":["..."]}'
```
仅口头回复、未生成结构化内容时不需要 backfill。回填时必须删除 `[IMG:N]` 等图片标记。

---

## 提取图片

```bash
bash scripts/run_cli.sh images "URL"              # 列出图片 URL
bash scripts/run_cli.sh images --proxy "URL"       # 输出 wsrv.nl 代理 URL
bash scripts/run_cli.sh images --download /dir "URL"  # 下载到本地
```

图文联合分析（多模态模型）：
```bash
bash scripts/run_cli.sh ingest --present --with-images --from-cache "URL"
```

---

## 批量抓取（discover）

```bash
# 第 1 步：先看会发现哪些 URL
bash scripts/run_cli.sh discover "SEED_URL" --present

# 第 2 步：确认后批量抓取 + 保存 + 图片
bash scripts/run_cli.sh discover "SEED_URL" \
  --ingest --ingest-store --ingest-with-images --ingest-from-cache
```

discover 需要已安装扩展的 expander。无对应扩展时告知用户：「该站点暂不支持自动发现，你可以手动提供 URL 列表。」

详细参数和输出结构见 [references/SKILL_FIELDS.md](./references/SKILL_FIELDS.md)。

---

## 平台特殊处理（仅与通用流程不同的部分）

- **小红书**：默认不抓评论。用户需要评论时加 `ONEFETCH_XHS_COMMENT_MODE='state+api'`（需 Cookie）。图片笔记正文为空时提示用户是否 OCR
- **抖音**：需要 Cookie。通过抖音 AI 助手获取视频总结 + 文字版，支持短链接
- **知乎**：问答无需 Cookie；专栏需要 Cookie。问答默认返回高赞 5 个回答
- **B 站**：视频字幕需要 Cookie；专栏无需 Cookie。无 Cookie 时仍可获取标题/作者/简介

各平台完整细节见 [references/SKILL_PLATFORMS.md](./references/SKILL_PLATFORMS.md)。

---

## 错误处理

关注结果中的 `error_code`、`error_type`、`retryable`、`action_hint` 字段。

| 错误码 | 说明 | 处理 |
|---|---|---|
| `dep.playwright_missing` | 缺少浏览器组件 | 按 `action_hint` 安装 |
| `auth.cookie_required` | 页面需要登录 | **必须按下方 Cookie 引导流程处理** |
| `risk.blocked` | 平台风控拦截 | **必须按下方 Cookie 引导流程处理** |
| `network.timeout` | 网络超时 | 重试；外网地址考虑代理 |
| `route.not_found` | URL 格式有误 | 检查 URL |

处理流程：
1. `retryable=True` → 自动重试一次
2. `action_hint` 非空 → 包含可直接执行的修复命令，agent 尝试自动执行
3. 重试仍失败 → 告知用户错误原因和建议
4. 网络超时且为外网地址 → 提示用户是否需要代理（`HTTPS_PROXY=<地址> bash scripts/run_cli.sh ...`）

### auth.cookie_required / risk.blocked → Cookie 引导流程

**必须**完整展示以下 4 种方式让用户选择，不要只说"需要配置 Cookie"：

> 这个页面需要登录态才能读取，我帮你配置 Cookie。请选一种方式：
>
> 1. **剪贴板导入**（推荐）：在浏览器中登录该网站，F12 打开开发者工具 → Network → 点击任意请求 → Headers → 复制 `Cookie:` 的值，复制好后告诉我，我执行 `bash scripts/setup_cookie.sh <域名>`（自动读取剪贴板）
> 2. **文件导入**：把 Cookie 保存为文件（Header String 或 Netscape cookies.txt 格式），告诉我文件路径
> 3. **环境变量**：如果你已经把 Cookie 存在环境变量里，告诉我变量名和对应域名
> 4. **网页导入**（不熟悉命令行时）：我启动一个本地网页，你在浏览器里粘贴提交

用户选择后执行对应命令（详见 [references/SKILL_COOKIES.md](./references/SKILL_COOKIES.md)）。配置成功后自动重试原请求。

---

## 风险控制

小红书、知乎专栏、B 站视频字幕等平台批量抓取时，建议 safe 节奏（串行、分批、随机停顿）。agent 先征得用户同意。详见 [references/SKILL_FIELDS.md](./references/SKILL_FIELDS.md)。

---

## 参考文档

| 文档 | 内容 |
|---|---|
| [references/SKILL_PLATFORMS.md](./references/SKILL_PLATFORMS.md) | 各平台特殊处理详情 |
| [references/SKILL_COOKIES.md](./references/SKILL_COOKIES.md) | Cookie 4 种导入方式完整命令 |
| [references/SKILL_PLUGINS.md](./references/SKILL_PLUGINS.md) | 插件体系（元素提取） |
| [references/SKILL_COMMANDS.md](./references/SKILL_COMMANDS.md) | 命令速查（全量） |
| [references/SKILL_FIELDS.md](./references/SKILL_FIELDS.md) | 输出字段、discover 参数、风险控制、提示模板 |
| `README.md` | 用户使用说明 |
| `references/INDEX.md` | 开发文档索引 |
