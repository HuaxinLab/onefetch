# Architecture

## 1. Design Goals

OneFetch uses a “skill shell + Python core” architecture:
- User-facing: agents can read web content without requiring coding knowledge.
- Engineering-facing: platform logic is isolated and extensible.
- Data-facing: fetch-only by default, persist only when explicitly requested.

## 2. High-level Layout

```text
OneFetch/
  SKILL.md
  scripts/
    bootstrap.sh
    doctor.sh
    run_ingest.sh
    setup_xhs_cookie.sh
    clean.sh
    pack.sh
  onefetch/
    cli.py
    router.py
    pipeline.py
    storage.py
    models.py
    http.py
    adapters/
      xiaohongshu.py
      wechat.py
      generic_html.py
  references/
  tests/
```

## 3. Runtime Flow

1. User asks agent to read/fetch a URL.
2. Agent follows `SKILL.md` and invokes `scripts/run_ingest.sh`.
3. CLI extracts URLs and router selects an adapter.
4. Adapter crawls and maps content into a unified `FeedEntry`.
5. Pipeline classifies errors and aggregates results.
6. Results are presented by default; persistence only happens with `--store`.

## 4. Boundaries

### 4.1 scripts (shell layer)

Responsibilities:
- bootstrap, health checks, CLI invocation, packing, cleanup.

Non-responsibilities:
- platform parsing and schema mapping.

### 4.2 onefetch (core layer)

Responsibilities:
- routing, crawling, parsing, error classification, optional persistence.

Principle:
- keep business logic in Python, not shell.

### 4.3 adapters (platform isolation)

- one adapter per platform.
- platform-specific anti-bot/cleanup/field mapping stays inside the adapter.
- core pipeline remains platform-agnostic.

## 5. Data Strategy

### 5.1 Fetch-only mode (default)

- no writes to `data/`.
- optimized for read-first decisions.

### 5.2 Store mode (`--store`)

Writes:
- `data/raw/*.json`
- `data/feed/*.json`
- `data/notes/*.md`
- `data/catalog.jsonl`

### 5.3 Dedup

- based on `canonical_url + content_hash`.

## 6. Error Model

Pipeline classifies failures into:
- `route.*`
- `network.*`
- `risk.*`
- `parse.*`
- `unknown`

And returns:
- `error_code`
- `error_type`
- `retryable`

## 7. Extensibility

To add a platform:
1. add `adapters/<platform>.py`
2. implement `supports/crawl`
3. register adapter in CLI/router initialization
4. add route + adapter tests

## 8. Why this architecture

- More maintainable than single-shell crawlers.
- Clearer than multiple overlapping skills.
- Friendly for non-technical users via an agent-first workflow.
