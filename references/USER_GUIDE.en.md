# User Guide (OneFetch)

This guide has two parts:
- Part A: Non-technical users (use via agent)
- Part B: Developers / advanced users (run scripts directly)

## A. Non-technical users (recommended)

You do not need to run scripts manually. Ask your agent to use the OneFetch skill.

### A1. Install into agent

1. Put OneFetch into the agent skills directory (or create a symlink).
2. Ensure `SKILL.md` is visible.
3. For the first run, let the agent initialize the environment with `bootstrap + doctor`.

Example for Codex:

```bash
ln -s <project-root> ~/.codex/skills/onefetch
```

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

If you need comments, configure the cookie once:

1. Log in to Xiaohongshu in your browser.
2. Export the header string with Cookie-Editor (`a1=...; web_session=...; ...`).
3. Let the agent run:

```bash
bash scripts/setup_xhs_cookie.sh
```

4. Paste the cookie and press `Ctrl-D` to finish.

After that, you only need to tell the agent:
- "Fetch this Xiaohongshu post with comments"

Notes:
- The post body can still be fetched without cookies.
- Comments may be empty when cookies are not configured.

### A4. Typical examples

- Example 1: Read only, do not save
: "Read this WeChat article and summarize it in 3 points: <URL>"

- Example 2: Fetch and store
: "Fetch this webpage and archive it locally: <URL>"

- Example 3: Xiaohongshu body + comments
: "Fetch this Xiaohongshu post and summarize the post plus comments: <URL>"

## B. Developers / advanced users (direct scripts)

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

Stored artifacts:
- `data/raw/`
- `data/feed/`
- `data/notes/`
- `data/catalog.jsonl`

### B4. Useful commands

```bash
bash scripts/run_ingest.sh --list-crawlers
ONEFETCH_GENERIC_RENDER_MODE=browser bash scripts/run_ingest.sh "URL"
bash scripts/clean.sh
bash scripts/pack.sh
bash scripts/pack.sh --name onefetch.zip --output release
```

### B5. FAQ

Q1: What if fetching fails?
: Retry once first. If it still fails, try browser render mode.

Q2: Why is a WeChat article incomplete?
: It may have hit a verification page. Retry later or enable browser rendering.

Q3: How do I fully reset the local environment?
: `bash scripts/clean.sh --all` removes `.venv` too.

Q4: Will `clean.sh` delete my saved content?
: It asks before deleting `data/` and `reports/`. You can skip deletion, or use `--keep-data` to keep them explicitly.
