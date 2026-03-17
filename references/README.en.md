# OneFetch

**语言 / Language**: [中文](../README.md) | [English](./README.en.md)

OneFetch is an agent-facing web reading skill.

Supported sources:
- Xiaohongshu
- WeChat Official Account pages
- Generic HTML pages (including JS-heavy pages)

Default use case is fast reading: fetch cleaned full text and let the LLM summarize.

## Clone

```bash
git clone https://github.com/HuaxinLab/onefetch.git
cd onefetch
```

## Purpose

- Provide a stable, unified web-reading capability for agents.
- Return cleaned body text for LLM summarization, translation, and deeper analysis.
- Prefer cache-first reading by default to avoid repeated crawling.

## Typical Use Cases

- Let an agent read and summarize a WeChat Official Account article.
- Let an agent fetch a Xiaohongshu post, with comments when needed.
- Let an agent handle generic webpages in the same unified flow.
- Store content only after the user explicitly confirms.

## Install Into Agent (Recommended)

Most users do not need to run crawler scripts directly. The common path is to install OneFetch as a skill for the agent.

Example for Codex:

```bash
ln -s <project-root> ~/.codex/skills/onefetch
```

After installation, tell the agent (this is all non-technical users need):
- "Read this webpage: <URL>"
- "Summarize this WeChat article"
- "Fetch this Xiaohongshu post and list key points"

## Directory Layout

- `SKILL.md`
- `scripts/`
- `references/`
- `onefetch/`
- `tests/`

## Documentation Entry

- This page is the user usage guide (agent-first scenarios).
- Docs index: [references/INDEX.md](./INDEX.md)
