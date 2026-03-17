# OneFetch Step-by-step Implementation Guide

## Step 0 - Create and use virtual environment (required)

```bash
cd ~/Projects/acusp/OneFetch
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
```

All implementation and test commands should run inside `.venv`.

## Step 1 - Bootstrap project packaging

- Add `pyproject.toml`
- Define package name `onefetch`
- Add entrypoint `onefetch=onefetch.cli:main`

## Step 2 - Define canonical models

Create `models.py` with:
- `Capture`
- `FeedEntry`
- `IngestResult`

Use `pydantic` validation to lock schema.

## Step 3 - Implement adapter interface

Create `adapters/base.py`:
- abstract class `BaseAdapter`
- method `supports(url: str) -> bool`
- method `crawl(url: str, ctx) -> FeedEntry`

## Step 4 - Implement generic HTML adapter

- Fetch via `httpx`
- Parse with HTML parser
- Extract title/body/author/date best-effort
- Fill metadata and return `FeedEntry`

## Step 5 - Implement Xiaohongshu adapter

- Add URL patterns for notes/profiles (as needed)
- Implement extraction strategy
- Add optional browser fallback for dynamic pages

## Step 6 - Implement router

- Register adapters
- Route URL by first matching adapter
- Fallback to `generic_html`

## Step 7 - Implement storage

- Write raw capture (`data/raw`)
- Write feed JSON (`data/feed`)
- Write markdown note (`data/notes`)
- Compute hash for deduplication

## Step 8 - Implement CLI ingest command

`onefetch ingest <url...> [--crawler <id>]`

Output should include:
- status (`stored`, `duplicate`, `failed`)
- adapter id
- saved file paths

## Step 9 - Add tests

- Router unit tests
- Schema validation tests
- Adapter smoke tests
- Deduplication tests

## Step 10 - Add Skill wrapper

- Create `skills/onefetch/SKILL.md`
- Add wrapper script that calls CLI
- Add usage examples and constraints

## Step 11 - Validation pass

- Install dependencies in virtual environment:
  - `pip install -e ".[dev]"`
- Verify command:
  - `onefetch --help`
  - `onefetch ingest --help`
- Run tests:
  - `PYTHONPATH=src python3 -m pytest -q`
