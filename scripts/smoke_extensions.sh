#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"

EXT_REPO="${ONEFETCH_EXT_REPO:-https://github.com/HuaxinLab/onefetch-extensions}"
EXT_ID="${ONEFETCH_EXT_SMOKE_ID:-geekbang}"
SMOKE_URL="${ONEFETCH_EXT_SMOKE_URL:-https://b.geekbang.org/member/course/detail/942422}"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "[smoke-ext] missing venv python: $VENV_PYTHON"
  exit 1
fi

cd "$PROJECT_ROOT"

echo "[smoke-ext] project_root=$PROJECT_ROOT"
echo "[smoke-ext] repo=$EXT_REPO"
echo "[smoke-ext] ext_id=$EXT_ID"
echo "[smoke-ext] url=$SMOKE_URL"

echo "[smoke-ext] list remote extensions"
"$VENV_PYTHON" -m onefetch.cli ext list --remote --repo "$EXT_REPO"

echo "[smoke-ext] install extension"
"$VENV_PYTHON" -m onefetch.cli ext install "$EXT_ID" --repo "$EXT_REPO"

echo "[smoke-ext] update extension"
"$VENV_PYTHON" -m onefetch.cli ext update "$EXT_ID" --repo "$EXT_REPO"

echo "[smoke-ext] ingest smoke url with forced crawler"
"$VENV_PYTHON" -m onefetch.cli ingest --present --refresh --crawler "$EXT_ID" "$SMOKE_URL"

echo "[smoke-ext] done"
