> Sync status: This English document may lag behind the Chinese version (.md).

# User Guide (OneFetch)

This guide has two parts:
- Part A: Non-technical users (use via agent)
- Part B: Advanced users (run scripts directly)

## A. Non-technical users (recommended)

You do not need to run scripts manually. Ask your agent to use the OneFetch skill.

### A1. Install into agent

1. Put OneFetch into the agent skills directory (or create a symlink).
2. Ensure `SKILL.md` is visible.

### A2. Daily usage

Ask agent in natural language:
- "Read this webpage: <URL>"
- "Fetch this WeChat article and summarize it"
- "Fetch this Xiaohongshu link and list key points"

Default behavior:
- Fetch and present (no persistence)

When you explicitly ask to save/archive:
- Agent will use `--store`.

### A3. Xiaohongshu comments (optional)

If you need comments, configure cookie once:

```bash
bash scripts/setup_xhs_cookie.sh
```

Then ask agent to fetch Xiaohongshu with comments.

## B. Advanced users (direct scripts)

### B1. Setup

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
```

### B2. Fetch

```bash
bash scripts/run_ingest.sh --present "https://example.com/article"
```

### B3. Store

```bash
bash scripts/run_ingest.sh --store "https://example.com/article"
```

### B4. Useful commands

```bash
bash scripts/run_ingest.sh --list-crawlers
ONEFETCH_GENERIC_RENDER_MODE=browser bash scripts/run_ingest.sh "URL"
bash scripts/clean.sh
bash scripts/pack.sh --clean-before
```
