# 实现指南（Skill 外壳 + Python 内核）

## 结构

- `SKILL.md`: 触发与使用说明
- `scripts/`: bootstrap / doctor / run
- `onefetch/`: 核心代码（router, adapters, pipeline, storage）
- `references/`: 文档
- `tests/`: 回归测试

## 设计原则

- 用户入口始终是 Skill + scripts
- 核心业务逻辑不放 shell，保持在 Python 包内
- 默认 fetch-only，显式 `--store` 才持久化

## 开发验证

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
.venv/bin/python -m pytest -q
```
