# PLAN / TODO（滚动记录）

> 目的：记录尚未实现、但已讨论过的计划与细节。  
> 状态：`Draft / Pending`（按条目更新）  
> 规则：完成即删除对应条目，避免历史堆积。

## Pending

### 1) weread 扩展（expander + adapter）落地

- 状态：`Pending`
- 目标：在扩展仓提供稳定的 weread 站点包，支持目录发现和章节抓取。
- 范围：
  - `sites/weread/manifest.json`
  - `sites/weread/expander.py`（目录/翻页 URL 采集）
  - `sites/weread/adapter.py`（正文抽取与去噪）
- 关键点：
  - 处理登录态与页面翻页机制
  - 对动态页面设置翻页上限/超时/失败重试，避免死循环

### 2) discover 批处理断点续跑能力

- 状态：`Pending`
- 目标：批量 discover/ingest 中断后可恢复，避免从头重跑。
- 范围：
  - 设计最小恢复状态文件（run-level）
  - 恢复时跳过已完成 URL，仅处理未完成部分
- 关键点：
  - 与现有 `reports/discover/*.json`、`reports/cache/*.json` 的关系
  - 失败重试与恢复后的统计一致性

### 3) safe 策略是否代码化（当前先走 SKILL 约束）

- 状态：`Draft`
- 当前结论：先不改核心代码，先通过 `SKILL.md` 约束 agent 执行节奏。
- 触发代码化条件：
  - 多次出现 agent 未按 safe 节奏执行
  - 多人/多 agent 协作下策略一致性不足
- 若启动实现：
  - 增加 `--mode safe|normal`
  - 固化串行/分批/抖动间隔/温和重试

### 4) 常用 adapter 的正文语义结构统一（按需推进）

- 状态：`Draft`
- 目标：将常用站点 adapter 的正文输出统一为“Markdown 友好结构”，提升 LLM 阅读质量与可复用性。
- 最小语义集（优先实现）：
  - 标题层级（动态归一化，正文最浅标题映射到 `###`）
  - 列表结构（`ul/ol -> - / 1.`）
  - 链接语义（`[text](url)`）
- 进阶语义（按站点出现频率启用）：
  - 表格（`table -> markdown table`）
  - 代码块（`pre/code -> fenced block`）
  - 图片占位 + 元数据（`[IMG:n]` 与 `images[{index,src,alt,href}]`）
- 优先级建议：
  - `wechat` / `zhihu`：`Pending` 候选（高频使用）
  - `xiaohongshu`：`Pending` 候选（轻量语义保留）
  - `bilibili`：`Draft`（字幕场景为主，优先级较低）
- 验证要求（每个 adapter 落地时）：
  - 单元测试覆盖结构转换
  - 至少 1 条真实页面抽查（避免回归）

## 备注

- 本文件只保留“未完成计划”。
- 任何新想法先写入此文件（`Draft`），讨论确认后升级为 `Pending`。
