# OneFetch Requirements

## Functional requirements

1. CLI interface
- Provide `onefetch ingest <url...>`
- Allow optional forced adapter: `--crawler <id>`

2. Routing
- Match `xiaohongshu.com` URLs to `xiaohongshu` adapter
- Fallback all other URLs to `generic_html` adapter

3. Unified output model
- Every ingestion result must include:
  - `source_url`
  - `canonical_url`
  - `title`
  - `author` (nullable)
  - `published_at` (nullable)
  - `body`
  - `comments` (optional list)
  - `metadata`

4. Storage layout
- Save raw capture to `data/raw/`
- Save structured feed to `data/feed/`
- Save note markdown to `data/notes/`

5. Deduplication
- Use `canonical_url + content_hash` to detect duplicates

6. Error handling
- Must return explicit, actionable error messages
- Must continue batch processing on per-URL failures

## Non-functional requirements

1. Maintainability
- Core and adapters are separated
- New adapter should not require core redesign

2. Extensibility
- New platform can be added via adapter registration

3. Reliability
- Deterministic outputs for same input when source is unchanged

4. Performance baseline
- Single URL ingest should complete in reasonable time under normal network conditions

5. Compliance and safety
- Respect target site terms and robots/legal constraints as applicable
- Avoid aggressive request patterns

## Acceptance criteria (v0.1)

- 5/5 generic HTML sample URLs ingested successfully
- Xiaohongshu adapter handles representative URLs with clear success/failure states
- Data schema validated for all successful outputs
- CLI and Skill handoff documented end-to-end

