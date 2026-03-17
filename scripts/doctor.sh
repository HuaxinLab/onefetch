#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

cd "$PROJECT_ROOT"

echo "[doctor] project_root=$PROJECT_ROOT"

if [[ ! -d ".venv" ]]; then
  echo "[doctor] .venv missing"
  exit 1
fi

source .venv/bin/activate

python - <<'PY'
import importlib
import sys

print(f"[doctor] python={sys.version.split()[0]}")
for mod in ["httpx", "pydantic", "lxml", "truststore"]:
    try:
        importlib.import_module(mod)
        print(f"[doctor] ok: {mod}")
    except Exception as exc:
        print(f"[doctor] missing: {mod} ({exc})")
        raise
PY

if command -v onefetch >/dev/null 2>&1; then
  echo "[doctor] onefetch CLI available"
else
  echo "[doctor] onefetch CLI missing"
  exit 1
fi

echo "[doctor] done"
