> Sync status: This English document may lag behind the Chinese version (.md).

# Installation and Usage

## Path placeholder

- `<project-root>`: OneFetch project root directory

## First-time setup (recommended)

```bash
cd <project-root>
bash scripts/bootstrap.sh
bash scripts/doctor.sh
```

## Daily usage

Default mode (no persistence):

```bash
bash scripts/run_ingest.sh "https://example.com"
```

Store only when needed:

```bash
bash scripts/run_ingest.sh --store "https://example.com"
```

## Optional features

Force browser rendering:

```bash
ONEFETCH_GENERIC_RENDER_MODE=browser bash scripts/run_ingest.sh "URL"
```

Xiaohongshu comments:

```bash
bash scripts/setup_xhs_cookie.sh
ONEFETCH_XHS_COMMENT_MODE='state+api' \
  bash scripts/run_ingest.sh "https://www.xiaohongshu.com/explore/..."
```
