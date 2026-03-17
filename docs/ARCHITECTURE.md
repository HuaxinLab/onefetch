# OneFetch Architecture

## Design principles

- Keep core stable
- Keep adapters isolated
- Keep outputs uniform
- Prefer explicit boundaries

## Proposed directory structure

```text
OneFetch/
  src/onefetch/
    cli.py
    config.py
    models.py
    router.py
    pipeline.py
    storage.py
    adapters/
      base.py
      generic_html.py
      xiaohongshu.py
  skills/onefetch/
    SKILL.md
    scripts/run_ingest.sh
  data/
    raw/
    feed/
    notes/
  tests/
```

## Core components

0. CLI (`cli.py`)
- Role: user/program entrypoint.
- Responsibility: parse `onefetch ingest` arguments, invoke pipeline, and print concise status.

1. Router
- Input: URL
- Output: adapter id
- Responsibility: platform dispatch only. No crawling or storage logic.

2. Adapter interface
- Contract: `crawl(url, ctx) -> FeedEntry`
- Each platform owns its extraction logic

3. Pipeline orchestrator
- Route URL
- Execute adapter
- Validate schema
- Persist outputs
- Responsibility: enforce deterministic ingest flow and batch error isolation.

4. Storage service
- Save raw body
- Save structured JSON
- Save note markdown
- Deduplicate by URL + content hash
- Responsibility: file layout and dedup catalog. No platform parsing logic.

5. Platform adapters
- `xiaohongshu`: site-specific URL matching and field extraction.
- `generic_html`: default fallback for non-platform-specific pages.

6. Tests
- Router tests: dispatch correctness.
- Storage tests: write and dedup behavior.
- Pipeline tests: stored/duplicate flow.

## Data flow

1. User calls `onefetch ingest URL`
2. CLI sends URL list to pipeline
3. Router picks adapter
4. Adapter returns normalized result
5. Storage writes artifacts
6. CLI prints result paths and status

## Extension strategy

To add a new platform:
1. Create new adapter file
2. Implement adapter interface
3. Register URL patterns in router
4. Add tests and sample URLs

No changes to core data model unless truly required.
