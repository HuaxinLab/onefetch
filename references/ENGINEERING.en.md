> Sync status: This English document may lag behind the Chinese version (.md).

# Engineering Guide

This document merges the previous implementation guide and plan.

## 1. Current Status

Completed:
- single skill entry (`SKILL.md`)
- three adapters (`xiaohongshu` / `wechat` / `generic_html`)
- default fetch-only with explicit `--store`
- one-time cookie setup and auto-load
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

## 3. Directory Responsibilities

- `onefetch/`: core logic
- `scripts/`: runtime/ops utilities
- `references/`: product + engineering docs
- `tests/`: regression safety net

## 4. SOP for New Platform

1. add `onefetch/adapters/<platform>.py`
2. implement `supports/crawl`
3. register adapter in CLI initialization
4. add tests:
- routing hit
- adapter parsing
- optional minimal smoke

## 5. Quality Gate

Before merge:
- full test pass
- doc sync (`README` / `SKILL` / `USER_GUIDE`)
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
