> Sync status: This English document may lag behind the Chinese version (.md).

# OneFetch

OneFetch is a skill-first web reading tool with a maintainable Python core.

Supported sources:
- Xiaohongshu
- WeChat Official Account pages
- Generic HTML pages (including JS-heavy pages)

Default mode is fetch-only. Use `--store` only when users explicitly ask for persistence.

## Skill-style layout

- `SKILL.md`
- `scripts/`
- `references/`
- `onefetch/`
- `tests/`

## Quick start

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
bash scripts/run_ingest.sh "https://example.com"
```

Store artifacts only when needed:

```bash
bash scripts/run_ingest.sh --store "https://example.com"
```
