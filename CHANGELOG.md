# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-03-17

### Added
- Cache-first workflow with temporary cache persistence and reuse (`--from-cache`).
- Temp cache capacity control with automatic pruning (`--cache-max-items`, default 200).
- `full_body`-centric present output path for downstream LLM processing.
- Standardized `llm_outputs` schema (`summary`, `key_points`, `tags`, `extras`).
- LLM output parser with validation, repair attempts, and safe fallback handling.
- Explicit `llm_outputs_state` in ingest results (`missing`, `ok`, `fallback`).
- Cache roundtrip for LLM outputs and states to support second-step operations.
- Adapter auto-registration + priority routing, removing hardcoded adapter list in CLI.
- New test coverage for adapter registry, LLM output parsing, and temp cache behavior.

### Changed
- Default agent strategy documented as cache-first read (`--present --from-cache`).
- LLM output backfill via `cache-backfill` command (replaces `reports/llm_output.json`).
- Documentation structure simplified: user entry consolidated in README; script details moved to engineering docs.

### Removed
- `references/USER_GUIDE.md` and `references/USER_GUIDE.en.md` in favor of README-first user guidance.

## [0.1.0] - 2026-03-17

### Added
- Skill-first repository layout with root `SKILL.md`, `scripts/`, `references/`, and `onefetch/` core package.
- New `wechat` adapter for WeChat Official Account pages.
- `--present` output mode for normalized LLM-friendly summaries.
- Structured error metadata (`error_code`, `error_type`, `retryable`) in pipeline output.
- One-time Xiaohongshu cookie setup script: `scripts/setup_xhs_cookie.sh`.
- Auto cookie loading in `scripts/run_ingest.sh` from local secret file.
- Packaging and cleanup utilities: `scripts/pack.sh`, `scripts/clean.sh`.
- Bilingual documentation set (Chinese-first with English mirrors).
- Live smoke test (env-gated) for xiaohongshu/wechat/generic_html.

### Changed
- Default ingest behavior is fetch-only; persistence requires explicit `--store`.
- Generic HTML adapter now supports browser fallback and better body extraction.
- WeChat extraction quality improved with stronger cleanup and fallback logic.
- `pack.sh` now defaults output to `release/`.
- `pack.sh` is packaging-only; cleanup behavior is separated into `clean.sh`.
- `clean.sh` now includes safety confirmations and `--keep-data` option.
- Documentation consolidated around `references/USER_GUIDE.md` as the main install/use entry.
- Engineering docs consolidated into `references/ENGINEERING.md`.

### Removed
- Legacy `read-webpage` skill paths and overlapping skill variants.
- Redundant docs (`INSTALLATION`, `PLAN`, `IMPLEMENTATION_GUIDE`) after consolidation.

### Notes
- English docs may lag behind Chinese docs and include sync-status headers where applicable.
- Use `bash scripts/pack.sh --name onefetch.zip` for shareable artifacts.
