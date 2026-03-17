> Sync status: This English document may lag behind the Chinese version (.md).

# Implementation Guide (Skill shell + Python core)

## Structure

- `SKILL.md`: trigger and usage instructions
- `scripts/`: bootstrap / doctor / run
- `onefetch/`: core code (router, adapters, pipeline, storage)
- `references/`: documentation
- `tests/`: regression tests

## Design principles

- User entrypoint is always Skill + scripts
- Keep business logic in Python (not in shell)
- Default to fetch-only; persist only with explicit `--store`

## Validation

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
.venv/bin/python -m pytest -q
```
