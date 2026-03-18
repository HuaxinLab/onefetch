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
    setup_cookie.sh
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

### 6.1 Classification

Pipeline classifies failures via `_classify_error`:

| error_code prefix | error_type | Meaning | retryable |
|---|---|---|---|
| `route.*` | route | No matching adapter | No |
| `network.timeout` | network | Request timed out | Yes |
| `network.http_429` | network | Rate-limited | Yes |
| `network.http_5xx` | network | Server error | Yes |
| `network.http_xxx` | network | Other HTTP errors | No |
| `risk.*` | risk | Anti-bot / captcha / restrictions | Yes |
| `dep.playwright_missing` | dependency | Browser rendering needed but Playwright not installed | No |
| `parse.*` | parse | Parse failure | No |
| `unknown` | unknown | Unclassified | No |

### 6.2 Structured Output

Each failed `IngestResult` carries these error fields:

| Field | Purpose |
|---|---|
| `error` | Human-readable error description |
| `error_code` | Machine-readable code (e.g. `dep.playwright_missing`) |
| `error_type` | Error category (e.g. `dependency`) |
| `retryable` | Whether the agent should retry |
| `action_hint` | A command the agent can execute to fix the issue (e.g. install command) |

### 6.3 Error Flow

```text
Adapter layer
  Detects failure → raise RuntimeError("short description")
      ↓
Pipeline layer (_classify_error)
  Exception message → (error_code, error_type, retryable, action_hint)
      ↓
Result layer (IngestResult)
  Structured fields written to result object and persisted to cache
      ↓
CLI layer
  error_code / error_type / retryable / action_hint printed line by line
```

Key principles:
- Adapters raise concise exceptions — no verbose install instructions.
- `_classify_error` is the single source of truth for classification and hints.
- `action_hint` provides an executable fix command so agents can auto-resolve dependency issues.

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
