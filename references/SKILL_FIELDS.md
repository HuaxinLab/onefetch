# 输出字段与格式参考

本文件是 SKILL.md 的补充参考，包含输出字段说明、图文格式和 discover 参数。

---

## `--present` 输出字段说明

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

---

## 图文联合分析输出格式

使用 `--with-images` 时，输出中 body 保留 `[IMG:N]` 标记表示图片原始位置，同时列出每张图片的 URL：
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

## 保存产物结构

保存产物写入 `data/<timestamp>-<hash>/`：
- `feed.json`：结构化数据（含 `llm_outputs`，暂无则为空结构）
- `note.md`：人可读归档（仅在已有 LLM 结果时写入摘要/要点/标签）
- `images/`：图片副本（仅 `--with-images` 时下载）

---

## LLM 回填注意事项

- agent 为用户生成了结构化的 summary / key_points / tags 时，就应该 backfill
- 仅口头回复用户、未生成结构化内容时，不需要 backfill
- 生成 summary / key_points / tags 时，必须忽略并删除图片标记（`[IMG:N]`、`[IMG_CAPTION:N]`），这些只用于图文位置映射，不是正文语义
- 回填后，后续任何操作（翻译、保存、再次查看）都能直接复用 LLM 结果

---

## discover 参数速查

| 参数 | 说明 |
|---|---|
| `--present` | 展示发现的 URL 列表 |
| `--ingest` | 发现后立即批量抓取 |
| `--ingest-store` | 抓取结果持久化到 data/ |
| `--ingest-with-images` | 下载图片 |
| `--ingest-from-cache` | 抓取时优先缓存 |
| `--ingest-refresh` | 强制实时抓取 |
| `--expander EXPANDER_ID` | 强制使用特定扩展器 |

### discover 输出结构

发现报告：`reports/discover/seed-<key>.json`（多 seed 时为 `batch-<key>.json`）

保存为合集时，结果整理到 `data/collections/<key>/`：
- `manifest.json`：用户可读索引（`seed_urls`、`discovered_urls`、`items`）
- `items/`：按顺序编号的文章目录（`001-...`、`002-...`，每个含 `feed.json` + `note.md`）

同一个 key 再次执行会覆盖更新为最新合集。`--ingest-store` 时 seed_url 对应的页面也会一起保存。

### discover 依赖扩展的 expander

`discover` 需要目标站点安装了提供 expander 的扩展才能工作。如果用户给出的 URL 没有对应扩展，agent 应：
1. 检查是否有可用扩展：`bash scripts/run_cli.sh ext list --remote --repo "${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"`
2. 有则安装后重试
3. 没有则告知用户：「该站点暂不支持自动发现内容页，你可以手动提供要抓取的 URL 列表。」

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

## 面向用户的提示模板

agent 在以下场景主动提示用户：

| 场景 | 建议提示 |
|---|---|
| 保存文件里暂无摘要/要点/标签 | 「正文已保存完成。需要我基于正文补充整理摘要和标签吗？」 |
| 需要刷新最新内容 | 「我可以先刷新网页再整理，拿到最新版本的正文。」 |
| 站点需要登录态 | 「这个页面需要登录后才能稳定读取。我可以引导你配置一次 Cookie。」 |
| 批量抓取建议 safe 模式 | 「这个站点建议用更稳妥的抓取节奏（会更慢）。是否按稳妥模式执行？」 |
| 保存前确认图片 | 「是否连图片一起保存？默认仅保存正文。」 |
