# OneFetch

OneFetch 是一个“Skill 外壳 + Python 内核”的网页读取工具，支持：
- 小红书
- 微信公众号
- 通用 HTML（含 JS 渲染）

默认是读取展示（fetch-only），只有显式 `--store` 才写入本地。

English: `references/README.en.md`

## 工具作用

- 给 agent 提供统一网页读取能力（而不是依赖不稳定的临时抓取）。
- 输出统一结构，便于大模型做总结、要点提炼、对比与归档决策。
- 默认不存储，先读后存，减少误存和无效数据。

## 适用场景

- 让 agent 读取并总结微信公众号文章。
- 让 agent 抓取小红书正文（可选评论）。
- 让 agent 统一处理通用网页内容并输出摘要/要点。
- 用户确认后再存储为本地结构化记录。

## 安装到 Agent（推荐）

普通用户不需要自己执行抓取脚本，主要是把 skill 安装给 agent。

示例（Codex）：

```bash
ln -s <project-root> ~/.codex/skills/onefetch
```

安装后直接对 agent 说：
- “读取这个网页：<URL>”
- “总结这条公众号内容”
- “抓这个小红书并输出要点”

## 让 Agent 自行安装运行环境

你可以让 agent 自行执行初始化：

```bash
bash scripts/bootstrap.sh
bash scripts/doctor.sh
```

后续 agent 默认应使用：
- `bash scripts/run_ingest.sh --present "URL"`
- 仅在你明确要求保存时才加 `--store`

## 目录结构（Skill 规范）

- `SKILL.md`
- `scripts/`
- `references/`
- `onefetch/`
- `tests/`

## 文档入口

- 使用说明（推荐先看）：`references/USER_GUIDE.md`
- 文档索引：`references/INDEX.md`

## 其他文档

- `references/ARCHITECTURE.md`
- `references/REQUIREMENTS.md`
- `references/ENGINEERING.md`
