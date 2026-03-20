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

## 备注

- 本文件只保留“未完成计划”。
- 任何新想法先写入此文件（`Draft`），讨论确认后升级为 `Pending`。
