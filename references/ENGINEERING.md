# 工程指南（Engineering）

本文件合并了“实现指南 + 计划”，用于开发维护人员。

## 1. 当前状态

已完成：
- 单一 skill 入口（`SKILL.md`）
- 三平台 adapter（`xiaohongshu` / `wechat` / `generic_html`）
- 默认 fetch-only + 显式 `--store`
- cookie 一次配置与自动加载
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

## 3. 目录职责

- `onefetch/`: 核心代码
- `scripts/`: 运行与运维脚本
- `references/`: 产品/工程文档
- `tests/`: 回归保障

## 4. 扩展新平台 SOP

1. 新建 `onefetch/adapters/<platform>.py`
2. 实现 `supports/crawl`
3. 注册到 CLI adapter 列表
4. 增加测试：
- 路由命中测试
- adapter 解析测试
- 最小 smoke（可选）

## 5. 质量门槛

合并前至少满足：
- 全量测试通过
- 关键文档同步（README / SKILL / USER_GUIDE）
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
