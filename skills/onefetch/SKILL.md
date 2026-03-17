---
name: onefetch
description: Focused cross-platform URL ingestion for Xiaohongshu and generic HTML pages. Use when users share links and want deterministic capture into local artifacts (raw/feed/note).
argument-hint: [url-or-free-text]
---

# OneFetch Skill

Use OneFetch when the user asks to:
- ingest/capture/archive web URLs
- fetch Xiaohongshu links
- save generic webpages as structured local records

## Workflow

1. Extract URLs from user message.
2. Run OneFetch CLI through wrapper script.
3. Report result status and artifact paths.

## Commands

List crawlers:

```bash
bash scripts/run_ingest.sh --list-crawlers
```

Ingest URLs:

```bash
bash scripts/run_ingest.sh "https://www.xiaohongshu.com/explore/xxxxx"
bash scripts/run_ingest.sh "https://example.com/article"
```

Force crawler (debug only):

```bash
bash scripts/run_ingest.sh --crawler xiaohongshu "URL"
```

## Notes

- Always run under project virtual environment (`.venv`).
- Keep outputs under project-local `data/` directories.
- If dependencies are missing, instruct user to follow `docs/INSTALLATION.md`.
