# 用户手册（OneFetch）

本手册分两部分：
- A 部分：普通用户（通过 agent 使用）
- B 部分：开发者/有经验用户（直接脚本运行）

## A. 普通用户（推荐）

你不需要直接运行脚本，只需要让 agent 使用 OneFetch skill。

### A1. 安装到 agent

1. 将 OneFetch 放到 agent 的 skills 目录（或创建软链接）。
2. 确认 skill 可见（`SKILL.md` 存在）。
3. 首次让 agent 执行环境初始化（`bootstrap + doctor`）。

Codex 示例：

```bash
ln -s <project-root> ~/.codex/skills/onefetch
```

### A2. 日常使用方式

直接对 agent 说：
- “读取这个网页：<URL>”
- “抓取这条公众号内容并总结”
- “抓取这个小红书链接，给我要点”

默认行为：
- 读取并展示（不存储）

当你明确说“保存/归档”时：
- agent 会用 `--store` 写入本地数据。

### A3. 小红书评论（可选）

如果你需要评论内容，先做一次 Cookie 配置：

1. 在浏览器登录小红书。
2. 用 Cookie-Editor 导出 Header String（`a1=...; web_session=...; ...`）。
3. 让 agent 执行：

```bash
bash scripts/setup_xhs_cookie.sh
```

4. 粘贴 Cookie，按 `Ctrl-D` 结束。

之后你只需要告诉 agent：
- “抓这条小红书并带评论”。

说明：
- 没有 Cookie 也可抓正文。
- 没有 Cookie 时评论可能为空。

### A4. 典型使用案例

- 案例 1：只读内容不保存
: “读取这个公众号并总结 3 点：<URL>”

- 案例 2：采集并保存
: “抓这个网页并归档到本地：<URL>”

- 案例 3：小红书正文+评论
: “抓这个小红书，输出正文和评论要点：<URL>”

## B. 开发者/有经验用户（直接运行）

### B1. 初始化

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
```

### B2. 抓取（默认不存储）

```bash
bash scripts/run_ingest.sh --present "https://example.com/article"
```

### B3. 存储

```bash
bash scripts/run_ingest.sh --store "https://example.com/article"
```

存储目录：
- `data/raw/`
- `data/feed/`
- `data/notes/`
- `data/catalog.jsonl`

### B4. 常用命令

```bash
bash scripts/run_ingest.sh --list-crawlers
ONEFETCH_GENERIC_RENDER_MODE=browser bash scripts/run_ingest.sh "URL"
bash scripts/clean.sh
bash scripts/pack.sh --clean-before
bash scripts/pack.sh --name onefetch.zip --output release
```

### B5. 常见问题

Q1: 抓取失败怎么办？
: 先重试一次；仍失败可切浏览器渲染模式。

Q2: 微信公众号内容不完整？
: 可能命中验证页，稍后重试或启用浏览器渲染。

Q3: 如何彻底重置本地环境？
: `bash scripts/clean.sh --all`（会删除 `.venv`）。
