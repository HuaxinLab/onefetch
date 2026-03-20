#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-./onefetch-extensions}"

if [[ -e "$TARGET_DIR" ]]; then
  echo "[init-ext] target already exists: $TARGET_DIR"
  exit 1
fi

mkdir -p "$TARGET_DIR/sites/example"

cat > "$TARGET_DIR/index.json" <<'JSON'
{
  "items": [
    {
      "id": "example",
      "name": "Example Site Bundle",
      "version": "0.1.0",
      "description": "Template bundle with adapter + expander",
      "domains": ["example.com"],
      "path": "sites/example"
    }
  ]
}
JSON

cat > "$TARGET_DIR/sites/example/manifest.json" <<'JSON'
{
  "id": "example",
  "name": "Example Site Bundle",
  "version": "0.1.0",
  "description": "Template bundle with adapter + expander",
  "domains": ["example.com"],
  "provides": ["adapter", "expander"],
  "entry": {
    "adapter": "adapter.py:register",
    "expander": "expander.py:discover"
  },
  "min_core_version": "0.2.0"
}
JSON

cat > "$TARGET_DIR/sites/example/adapter.py" <<'PY'
from __future__ import annotations

from onefetch.adapters.base import BaseAdapter
from onefetch.http import create_async_client
from onefetch.models import NormalizedFeed


class ExampleAdapter(BaseAdapter):
    id = "example"
    priority = 280

    def supports(self, url: str) -> bool:
        return "example.com" in (url or "")

    async def crawl(self, url: str) -> NormalizedFeed:
        async with create_async_client(timeout=30, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        body = response.text.strip()
        return self._build_feed(
            source_url=url,
            canonical_url=url,
            title="Example",
            body=body,
            raw_body=response.text,
        )


def register() -> None:
    # Import side effect is enough for adapter auto-registration.
    return None
PY

cat > "$TARGET_DIR/sites/example/expander.py" <<'PY'
from __future__ import annotations


def discover(seed_url: str) -> list[str]:
    # Template expander: return only seed URL.
    return [seed_url]
PY

cat > "$TARGET_DIR/README.md" <<'MD'
# onefetch-extensions (template)

This repository hosts optional OneFetch site bundles (`adapter + expander`).

## Structure

```text
index.json
sites/
  <site_id>/
    manifest.json
    adapter.py
    expander.py
```

## Use from OneFetch

```bash
.venv/bin/python -m onefetch.cli ext list --remote --repo <your_git_repo_url>
.venv/bin/python -m onefetch.cli ext install <site_id> --repo <your_git_repo_url>
.venv/bin/python -m onefetch.cli ext update <site_id> --repo <your_git_repo_url>
.venv/bin/python -m onefetch.cli ext remove <site_id>
```
MD

echo "[init-ext] created: $TARGET_DIR"
echo "[init-ext] next:"
echo "  cd $TARGET_DIR"
echo "  git init && git add . && git commit -m 'chore: init onefetch extensions repo'"
