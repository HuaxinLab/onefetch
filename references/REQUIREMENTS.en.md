# Requirements

## 1. Product Positioning

OneFetch is not a large-scale crawler platform. It is a stable, controllable, and extensible web-reading capability for agents.

Core positioning:
- single skill entry
- cross-platform reading (Xiaohongshu / WeChat / generic HTML)
- read first, then decide whether to persist

## 2. Functional Requirements

### 2.1 Skill and Entry

1. Root `SKILL.md` must exist.
2. `scripts/run_cli.sh` must be the unified runtime entry.
3. Agent should complete setup and fetch flows for non-technical users.

### 2.2 Crawling Capability

1. Supported adapters:
- `xiaohongshu`
- `wechat`
- `generic_html`
2. URL extraction from direct URLs and free text.
3. Readable presentation output (`--present`).

### 2.3 Persistence Strategy

1. Default fetch-only mode (no writes to `data/`).
2. Persist artifacts only with explicit `--store`.
3. Predictable artifact layout (`data/feed|notes`).

### 2.4 Xiaohongshu Comments

1. Body extraction should still work without cookie.
2. Comment extraction should support cookie-driven mode.
3. One-time setup script must exist (`setup_cookie.sh`).

### 2.5 Reporting and Observability

1. Support run reports (JSON/MD).
2. Return structured errors (`error_code/error_type/retryable`).
3. Allow agents to provide retry/next-step suggestions from error class.

## 3. Non-functional Requirements

### 3.1 Usability

- Non-technical users operate through agent prompts.
- Advanced users can run scripts directly.

### 3.2 Maintainability

- Platform logic isolated in adapters.
- Core pipeline complexity should not grow linearly with platform count.

### 3.3 Stability

- Outputs should be reasonably stable for unchanged source pages.
- Tests should cover core paths and major regression risks.

### 3.4 Safety

- Sensitive data (cookies) must not be committed.
- Cleanup script should include confirmations to prevent accidental data loss.

## 4. Acceptance Criteria

Minimum acceptance:
1. Agent can fetch one URL per source type (xhs/wechat/html).
2. Default fetch-only flow works.
3. `--store` flow writes expected artifacts.
4. One-time cookie setup is reusable.
5. Packed zip can be deployed on target machine.
