# Requirements

## Functional

1. Single skill entry: root `SKILL.md`.
2. Unified command: `bash scripts/run_ingest.sh ...`.
3. Default fetch-only behavior.
4. Optional persistence via `--store`.
5. Router-based platform dispatch (`xiaohongshu`, `wechat`, `generic_html`).

## Non-functional

1. Maintainable Python core (`onefetch/`).
2. Non-developer friendly shell wrapper (`scripts/`).
3. Deterministic outputs and explicit errors.
