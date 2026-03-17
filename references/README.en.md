# OneFetch

**语言 / Language**: [中文](../README.md) | [English](./README.en.md)

OneFetch is a skill-first web reading tool with a maintainable Python core.

Supported sources:
- Xiaohongshu
- WeChat Official Account pages
- Generic HTML pages (including JS-heavy pages)

Default mode is fetch-only. Use `--store` only when users explicitly ask for persistence.

## Clone

```bash
git clone https://github.com/HuaxinLab/onefetch.git
cd onefetch
```

## Purpose

- Provide a stable, unified web-reading capability for agents.
- Return structured outputs for LLM summarization and decision-making.
- Keep default behavior non-persistent (read first, store later).

## Typical Use Cases

- Let an agent read and summarize a WeChat Official Account article.
- Let an agent fetch a Xiaohongshu post, with comments when needed.
- Let an agent handle generic webpages in the same unified flow.
- Store structured local records only after the user confirms.

## Install Into Agent (Recommended)

Most users do not need to run crawler scripts directly. The common path is to install OneFetch as a skill for the agent.

Example for Codex:

```bash
ln -s <project-root> ~/.codex/skills/onefetch
```

After installation, tell the agent:
- "Read this webpage: <URL>"
- "Summarize this WeChat article"
- "Fetch this Xiaohongshu post and list key points"

For the first run, let the agent initialize the environment:

```bash
bash scripts/bootstrap.sh
bash scripts/doctor.sh
```

After that, the agent should normally use:
- `bash scripts/run_ingest.sh --present "URL"`
- Add `--store` only when you explicitly ask to save

## Directory Layout

- `SKILL.md`
- `scripts/`
- `references/`
- `onefetch/`
- `tests/`

## Documentation Entry

- User Guide (start here): [references/USER_GUIDE.en.md](./USER_GUIDE.en.md)
- Docs index: [references/INDEX.md](./INDEX.md)
