# TODO: Expanders 独立仓库方案（临时计划）

> 目的：记录“批量遍历（collection/discover）能力”的设计方向，避免讨论中遗忘。
> 状态：`Draft / Pending`
> 备注：方案落地并稳定后可删除本文件。

## 1. 目标

- 主仓 `onefetch` 保持轻量，继续聚焦单 URL 抓取与处理。
- 将“目录扩展/批量遍历”做成可选扩展（expander）。
- 用户可按需安装一个、多个或全部 expander。

## 2. 仓库模型（已确认）

- 主仓：`onefetch`（核心）
- 扩展仓：`onefetch-extensions`（单仓统一管理）
- 一个站点一个扩展包，`adapter + expander` 放在同一目录（同域名共版本）

建议扩展仓结构：

```text
index.json
sites/
  geekbang/
    manifest.json
    adapter.py
    expander.py
  weread/
    manifest.json
    adapter.py
    expander.py
```

## 3. 本地安装目录（建议）

建议统一安装到：

```text
.onefetch/extensions/<site_id>/
```

## 4. 用户安装方式（已确认方向）

统一命令组建议用 `ext`（extension）：

1. 安装单个站点包
   - `onefetch ext install geekbang`
2. 安装多个站点包
   - `onefetch ext install geekbang weread`
3. 安装全部
   - `onefetch ext install --all`
4. 升级
   - `onefetch ext update [id|--all]`
5. 卸载
   - `onefetch ext remove <id>`

可选细粒度（后续再做）：
- `--only adapter`
- `--only expander`

## 5. 协议草案（MVP）

### 5.1 `index.json`（仓库级）

- 字段建议：
  - `id`（站点包 ID，如 `geekbang`）
  - `name`
  - `version`
  - `path`（相对路径，如 `sites/geekbang`）
  - `description`
  - `domains`

### 5.2 `manifest.json`（站点包级）

- 字段建议：
  - `id`
  - `version`
  - `name`
  - `description`
  - `domains`
  - `provides`（`["adapter","expander"]` 或子集）
  - `entry.adapter`（可选）
  - `entry.expander`（可选）
  - `min_core_version`
  - `max_core_version`（可选）

## 6. 运行模型（职责边界）

- `ingest`：只处理给定 URL，不内置站点遍历逻辑。
- `discover/expand`：由 expander 输出 URL 列表，再交给 `ingest` 批量处理。
- 核心程序负责：
  - 加载已安装 extension（adapter + expander）
  - 调度 `supports/discover` 与 adapter 路由
  - 统一输出 `DiscoverResult`

`DiscoverResult` 建议字段：
- `seed_url`
- `expander_id`
- `discovered_urls`（有序）
- `stats`
- `warnings`
- `next_cursor`（可选）

## 7. 兼容与安全策略（已确认）

- 安全白名单/签名：暂不做（用户自行安装、自行开发）。
- 兼容控制：做轻量版本门槛检查（建议保留）。
  - 若不满足 `min_core_version/max_core_version`，扩展跳过加载并提示。
  - 不阻断主流程，自动回退内置能力（如 `generic_html`）。

## 8. 实现优先级建议（建议从这里开始）

1. **先做加载器和安装命令（最小可用）**
   - `ext install/remove/list`
   - 本地目录加载 `manifest.json`
2. **再做 Geekbang 站点包 MVP**
   - `adapter.py`：去噪课程页/章节页
   - `expander.py`：`intro` -> `detail` URL 列表
3. **最后补 weread 等动态场景**
   - 需要浏览器翻页采集 URL 的 expander

## 9. 风险与约束

- 平台风控与登录态（Cookie）要求要在 expander 输出中显式提示。
- 需要去重与断点续跑（避免重复抓取和中断损失）。
- 对动态页面需限制翻页上限、超时与失败重试，防止死循环。

## 10. 完成定义（DoD）

- 支持从扩展仓按 `id` 安装/升级/卸载。
- 至少一个 expander 可稳定产出 URL 列表并批量 ingest 成功。
- 文档说明安装与使用闭环完成。

---

删除条件：
- 方案正式实现并在 README/ENGINEERING 中有稳定文档后，删除本 TODO 文件。
