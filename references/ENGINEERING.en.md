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
- LLM output backfill via `cache-backfill` command (immediate write to cache)
- in `--store` flow, invalid structured output is regenerated via real LLM through `ONEFETCH_LLM_REGEN_CMD` first, then heuristic fallback
- one-time cookie setup and auto-load
- plugin framework (`onefetch plugin list/run`)
- built-in + local preset loading for plugins
- packing and cleanup scripts
- external extension loader (`.onefetch/extensions/<id>`)
- extension management commands (`ext list/install/update/remove`)

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

Plugin operational commands:
- list plugins: `.venv/bin/python -m onefetch.cli plugin list`
- list plugins with presets: `.venv/bin/python -m onefetch.cli plugin list --with-presets`
- list presets: `.venv/bin/python -m onefetch.cli plugin presets --plugin-id <plugin_id>`
- run plugin: `.venv/bin/python -m onefetch.cli plugin run <plugin_id> ...`
- diagnose plugin: `.venv/bin/python -m onefetch.cli plugin doctor <plugin_id> ... --json`

`plugin doctor` output contract:
- `ok`: pass/fail status
- `error`: human-readable error message
- `error_code`: normalized error code (for example `E_INPUT_MISSING` / `E_JSONP_PARSE`)
- `suggestion`: actionable next step
- `steps`: diagnostic trace steps for pinpointing the failed stage

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

## 7. External Extensions (adapter + expander)

Goal: keep the core repository lightweight and install site-specific capabilities on demand.

### 7.1 Bootstrap an extension repository (template)

```bash
bash scripts/init_extensions_repo.sh ~/Projects/onefetch-extensions
```

Generated files:
- `index.json`
- `sites/example/{manifest.json,adapter.py,expander.py}`
- `README.md`

### 7.2 Extension commands (run in core repo)

```bash
# List installed
.venv/bin/python -m onefetch.cli ext list

# List remote catalog
.venv/bin/python -m onefetch.cli ext list --remote --repo <git_repo_url>

# Install one or multiple
.venv/bin/python -m onefetch.cli ext install geekbang --repo <git_repo_url>
.venv/bin/python -m onefetch.cli ext install geekbang weread --repo <git_repo_url>

# Install all
.venv/bin/python -m onefetch.cli ext install --all --repo <git_repo_url>

# Update
.venv/bin/python -m onefetch.cli ext update geekbang --repo <git_repo_url>
.venv/bin/python -m onefetch.cli ext update --all --repo <git_repo_url>

# Remove
.venv/bin/python -m onefetch.cli ext remove geekbang
.venv/bin/python -m onefetch.cli ext remove --all

# discover (seed page -> content URL list)
.venv/bin/python -m onefetch.cli discover "<seed_url>" --present

# discover + one-command batch ingest
.venv/bin/python -m onefetch.cli discover "<seed_url>" --ingest --ingest-from-cache
```

### 7.3 Manifest compatibility policy

- Supported fields: `min_core_version` / `max_core_version`
- If the core version is out of range, the extension is marked disabled and skipped.
- Main ingest flow continues and falls back to built-in adapters (for example `generic_html`).

### 7.4 Extension smoke check (recommended)

New script: `scripts/smoke_extensions.sh`

Purpose:
- Run `ext list --remote`, `ext install`, and `ext update` in one flow
- Then run a real `ingest --present --refresh` with the extension crawler

Default values:
- `ONEFETCH_EXT_REPO=https://github.com/HuaxinLab/onefetch-extensions`
- `ONEFETCH_EXT_SMOKE_ID=geekbang`
- `ONEFETCH_EXT_SMOKE_URL=https://b.geekbang.org/member/course/detail/942422`

Run:

```bash
bash scripts/smoke_extensions.sh
```

Override example:

```bash
ONEFETCH_EXT_SMOKE_ID=<ext_id> \
ONEFETCH_EXT_SMOKE_URL="<url>" \
bash scripts/smoke_extensions.sh
```

Minimal pre-release checks (recommended):
1. `bash scripts/smoke_extensions.sh` succeeds
2. `.venv/bin/python -m pytest -q` passes
3. extension repo `index.json` and `README.md` are in sync
