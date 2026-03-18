# 工程指南（Engineering）

本文件合并了“实现指南 + 计划”，用于开发维护人员。

## 1. 当前状态

已完成：
- 单一 skill 入口（`SKILL.md`）
- 三平台 adapter（`xiaohongshu` / `wechat` / `generic_html`）
- adapter 自动注册与优先级路由（专用 adapter 优先，`generic_html` 兜底）
- 默认 cache-first 读取（`--present --from-cache`）
- 支持 `--refresh` 强制实时抓取（跳过缓存读取）
- 显式 `--store` 持久化
- 临时缓存上限控制（`--cache-max-items`）
- LLM 输出通过 `cache-backfill` 命令立刻回填到缓存
- `--store` 且结构化结果失效时，优先通过 `ONEFETCH_LLM_REGEN_CMD` 执行真实 LLM 重算，失败再规则兜底
- cookie 一次配置与自动加载
- cookie 一次配置脚本（`setup_cookie.sh`）
- 打包与清理脚本

## 2. 开发工作流

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
.venv/bin/python -m pytest -q
```

建议流程：
1. 先写/改测试
2. 再改 adapter 或 pipeline
3. 本地跑回归后提交

注意：
- 测试命令统一使用 `.venv/bin/python -m pytest ...`，不要依赖 `.venv/bin/pytest` 可执行脚本（项目路径迁移后 shebang 可能失效）。

## 3. 目录职责

- `onefetch/`: 核心代码
- `scripts/`: 运行与运维脚本
- `references/`: 产品/工程文档
- `tests/`: 回归保障

## 4. 扩展新平台 SOP

1. 新建 `onefetch/adapters/<platform>.py`
2. 实现 `supports/crawl`
3. 设置 `id` 与 `priority`（通过基类自动注册）
4. 增加测试：
- 路由命中测试
- adapter 解析测试
- 最小 smoke（可选）

## 4.1 插件扩展 SOP（独立于 ingest）

插件目录：`onefetch/plugins/`

新增插件步骤：
1. 新建 `onefetch/plugins/<plugin>.py`
2. 实现 `id/description/supports/run`
3. 在 `onefetch/plugins/registry.py` 注册
4. 增加测试（`tests/plugins/`）
5. 只更新 `SKILL.md` 和工程文档；`README` 保持面向普通用户的最小说明

Preset 约定：
- 内置 preset：`onefetch/plugin_presets/*.json`（应纳入 git，随打包发布）
- 本地私有 preset：`.secrets/plugin_presets/*.json`（不纳入 git，不随打包发布）
- 读取优先级：`ONEFETCH_PLUGIN_PRESET_DIR` > `.secrets/plugin_presets` > `onefetch/plugin_presets`

Plugin 运维命令：
- 查看插件：`.venv/bin/python -m onefetch.cli plugin list`
- 查看插件+预设：`.venv/bin/python -m onefetch.cli plugin list --with-presets`
- 查看 preset 列表：`.venv/bin/python -m onefetch.cli plugin presets --plugin-id <plugin_id>`
- 运行插件：`.venv/bin/python -m onefetch.cli plugin run <plugin_id> ...`
- 诊断插件：`.venv/bin/python -m onefetch.cli plugin doctor <plugin_id> ... --json`

`plugin doctor` 输出约定：
- `ok`: 是否通过
- `error`: 错误信息
- `error_code`: 标准错误码（如 `E_INPUT_MISSING` / `E_JSONP_PARSE`）
- `suggestion`: 下一步建议动作
- `steps`: 诊断链路步骤（便于定位哪一步失败）

## 5. 质量门槛

合并前至少满足：
- 全量测试通过
- 关键文档同步（README / SKILL / ENGINEERING）
- 无敏感信息入库（cookie/session）

## 6. 后续路线（滚动）

短期：
1. 微信正文清洗持续优化
2. `--present` 输出模板稳定化
3. 常见故障诊断提示标准化

中期：
1. 新平台 adapter（按需求）
2. 统一内容质量评分（可读性、噪音比）
3. 更细粒度的风险与重试策略

## 7. Cookie 一次配置（复制粘贴）

### 小红书评论 Cookie

```bash
bash scripts/setup_cookie.sh xiaohongshu.com
```

### 知乎 Cookie（专栏 `risk.blocked` 时）

```bash
bash scripts/setup_cookie.sh zhihu.com
```

说明：
- 两个脚本都会把 Cookie 保存到 `.secrets/` 目录（默认 600 权限）。
- `bash scripts/run_cli.sh ...` 会自动加载已保存 Cookie，无需每次手动设置环境变量。
