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

## Preconditions

Before running ingest commands, ensure:

1. Project exists at `~/Projects/acusp/OneFetch` (or `ONEFETCH_PROJECT_ROOT` points to it)
2. Virtual environment exists at `PROJECT_ROOT/.venv`
3. CLI is installed in that environment (`pip install -e ".[dev]"`)

If not ready, follow `docs/INSTALLATION.md`.

## Workflow

1. Extract URLs from user message.
2. Run OneFetch CLI through wrapper script.
3. If Xiaohongshu comments are required, use configured comment mode and (optional) login cookie.
4. Report result status, artifact paths, and comment fetch status.

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

Generate run report files:

```bash
bash scripts/run_ingest.sh "URL" \
  --report-json "./reports/latest-run.json" \
  --report-md "./reports/latest-run.md"
```

## Xiaohongshu Comment Modes

Default mode:

```bash
ONEFETCH_XHS_COMMENT_MODE='state+api' bash scripts/run_ingest.sh "URL"
```

Include DOM fallback (higher cost):

```bash
ONEFETCH_XHS_COMMENT_MODE='state+api+dom' bash scripts/run_ingest.sh "URL"
```

Disable comments:

```bash
ONEFETCH_XHS_COMMENT_MODE='off' bash scripts/run_ingest.sh "URL"
```

Logged-in comment capture:

```bash
ONEFETCH_XHS_COOKIE='...' \
ONEFETCH_XHS_COMMENT_MODE='state+api' \
ONEFETCH_XHS_COMMENT_MAX_PAGES=3 \
ONEFETCH_XHS_COMMENT_MAX_ITEMS=50 \
bash scripts/run_ingest.sh "URL"
```

Risk-friendly controls:

```bash
ONEFETCH_XHS_API_MIN_INTERVAL_SEC=1.0 \
ONEFETCH_XHS_API_MAX_RETRIES=2 \
ONEFETCH_XHS_API_BACKOFF_SEC=1.0 \
ONEFETCH_XHS_API_RISK_COOLDOWN_SEC=900 \
bash scripts/run_ingest.sh "URL"
```

## Notes

- Always run under project virtual environment (`.venv`).
- Keep outputs under project-local `data/` directories.
- If dependencies are missing, instruct user to follow `docs/INSTALLATION.md`.
- For Xiaohongshu, comments may be empty without valid login cookie.
- `comment_fetch` status is stored in feed metadata and should be reported to users.

## Response Template

When ingest completes, report:

1. Processed URL count and status summary
2. Per-URL artifact paths (`raw`, `feed`, `note`)
3. For Xiaohongshu: `comment_fetch.source`, `api.status/code/msg`, and comment count
4. If report files were generated: output paths for JSON and Markdown reports
