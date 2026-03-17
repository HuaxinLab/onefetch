# OneFetch Plan

## Objective

Build a maintainable crawler foundation for two sources first:
- Xiaohongshu
- Generic HTML webpages

Then expand safely to more platforms without redesign.

## Phase plan

## Phase 0 - Foundation and setup

Deliverables:
- Python project skeleton
- Dependency baseline
- Config file structure
- CLI skeleton

Exit criteria:
- `onefetch --help` works
- `onefetch ingest --help` works

## Phase 1 - Core pipeline

Deliverables:
- URL router
- Unified models (`Capture`, `FeedEntry`)
- Storage service (`raw`, `feed`, `notes`)
- Error and retry strategy

Exit criteria:
- Core can receive URL and dispatch to adapter
- Standard files are written under `data/`

## Phase 2 - Generic HTML adapter

Deliverables:
- Static HTTP fetch via `httpx`
- HTML extraction via parser
- Markdown note generation

Exit criteria:
- Ingest 5 public article URLs successfully
- Output schema passes validation

## Phase 3 - Xiaohongshu adapter

Deliverables:
- URL matching rules
- Field extraction strategy
- Optional browser fallback (`playwright`)

Exit criteria:
- Ingest representative sample URLs
- Controlled failure behavior and clear errors

## Phase 4 - Skill integration

Deliverables:
- `skills/onefetch/SKILL.md`
- Skill command wrapper for CLI
- Trigger and usage examples

Exit criteria:
- Skill can call CLI reliably
- User can invoke OneFetch in natural language

## Phase 5 - Hardening

Deliverables:
- Unit tests for routing and schema
- Adapter regression test samples
- Basic observability (logs, counters)

Exit criteria:
- Stable runs over repeated ingest tasks
- Safe extension path for new platforms

## Non-goals for v0.1

- Distributed queue workers
- Full knowledge-base synthesis
- Multi-tenant deployment
- Large-scale crawling optimization

