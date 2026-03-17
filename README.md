# OneFetch

OneFetch 是一个“Skill 外壳 + Python 内核”的网页读取工具，支持：
- 小红书
- 微信公众号
- 通用 HTML（含 JS 渲染）

默认是读取展示（fetch-only），只有显式 `--store` 才写入本地。

English: `references/README.en.md`

## 目录结构（Skill 规范）

- `SKILL.md`
- `scripts/`
- `references/`
- `onefetch/`
- `tests/`

## 给非开发用户的最短用法

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
bash scripts/run_ingest.sh --present "https://example.com"
```

需要保存时：

```bash
bash scripts/run_ingest.sh --store "https://example.com"
```

## 常用命令

```bash
bash scripts/run_ingest.sh --list-crawlers
bash scripts/run_ingest.sh --present "https://example.com"
bash scripts/setup_xhs_cookie.sh
bash scripts/run_ingest.sh "https://example.com" --report-md "./reports/latest-run.md"
bash scripts/clean.sh
bash scripts/pack.sh --clean-before
bash scripts/pack.sh --name onefetch.zip --output release
```

## 文档

- `references/INSTALLATION.md`
- `references/ARCHITECTURE.md`
- `references/IMPLEMENTATION_GUIDE.md`
- `references/REQUIREMENTS.md`
- `references/PLAN.md`
