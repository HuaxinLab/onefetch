# Engineering Guide

This document merges the previous implementation guide and plan.

## 1. Current Status

Completed:
- single skill entry (`SKILL.md`)
- three adapters (`xiaohongshu` / `wechat` / `generic_html`)
- adapter auto-registration with priority routing (specialized adapters first, `generic_html` as fallback)
- default cache-first read flow (`--present --from-cache`)
- `--refresh` support for forced live crawl (bypass cache read)
- explicit `--store` persistence
- temp cache size control (`--cache-max-items`)
- default LLM output backfill (`reports/llm_output.json`, overridable via `--llm-output-file`)
- in `--store` flow, invalid structured output is regenerated via real LLM through `ONEFETCH_LLM_REGEN_CMD` first, then heuristic fallback
- one-time cookie setup and auto-load
- plugin framework (`onefetch plugin list/run`)
- built-in + local preset loading for plugins
- packing and cleanup scripts

## 2. Development Workflow

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
.venv/bin/python -m pytest -q
```

Recommended flow:
1. tests first
2. modify adapter/pipeline
3. run regressions before commit

Note:
- Use `.venv/bin/python -m pytest ...` instead of relying on `.venv/bin/pytest` shebang wrappers.

## 3. Directory Responsibilities

- `onefetch/`: core logic
- `scripts/`: runtime/ops utilities
- `references/`: product + engineering docs
- `tests/`: regression safety net

## 4. SOP for New Platform

1. add `onefetch/adapters/<platform>.py`
2. implement `supports/crawl`
3. set `id` and `priority` (auto-registered by base adapter)
4. add tests:
- routing hit
- adapter parsing
- optional minimal smoke

## 4.1 SOP for New Plugin (Independent from ingest)

Plugin location: `onefetch/plugins/`

Steps:
1. add `onefetch/plugins/<plugin>.py`
2. implement `id/description/supports/run`
3. register it in `onefetch/plugins/registry.py`
4. add tests under `tests/plugins/`
5. sync docs in `SKILL.md` and engineering docs

Preset conventions:
- built-in presets: `onefetch/plugin_presets/*.json` (tracked in git, included in package)
- local private presets: `.secrets/plugin_presets/*.json` (not tracked, not packaged)
- loading priority: `ONEFETCH_PLUGIN_PRESET_DIR` > `.secrets/plugin_presets` > `onefetch/plugin_presets`

## 5. Quality Gate

Before merge:
- full test pass
- doc sync (`README` / `SKILL` / `ENGINEERING`)
- no sensitive data committed (cookie/session)

## 6. Rolling Roadmap

Short-term:
1. improve WeChat body cleanup
2. stabilize `--present` template
3. standardize troubleshooting hints

Mid-term:
1. add adapters as needed
2. content quality scoring (readability/noise)
3. finer risk/retry strategy
