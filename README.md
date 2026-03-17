# OneFetch

OneFetch is a focused cross-platform content ingestion tool.

Current phase goal:
- Support `xiaohongshu` and `generic_html`
- Keep architecture simple and extensible
- Provide one CLI entrypoint and one Skill-facing workflow

## Project status

Scaffold and baseline docs are ready.
Core CLI, router, storage, and adapter skeletons are implemented.

## Documentation index

- `docs/PLAN.md`
- `docs/REQUIREMENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/INSTALLATION.md`
- `docs/IMPLEMENTATION_GUIDE.md`

## Scope of v0.1

- URL routing
- Two adapters (`xiaohongshu`, `generic_html`)
- Unified output schema
- Unified data storage (`data/raw`, `data/feed`, `data/notes`)
- CLI command: `onefetch ingest <url>`

## Module responsibilities

- `cli.py`: Command entrypoint. Parses args and prints ingest results.
- `router.py`: URL routing. Chooses adapter by URL pattern or forced crawler id.
- `pipeline.py`: End-to-end orchestration. Route -> crawl -> dedupe -> store -> report.
- `storage.py`: Artifact persistence and dedup catalog management.
- `adapters/xiaohongshu.py`: Xiaohongshu-specific extraction and mapping.
- `adapters/generic_html.py`: Fallback extractor for generic webpages.
- `tests/`: Regression protection for routing, storage, and pipeline behavior.

## Quick start

```bash
cd ~/Projects/acusp/OneFetch
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

Optional browser support:

```bash
pip install -e ".[browser]"
playwright install chromium
```

Verify:

```bash
onefetch --help
onefetch ingest --help
```
