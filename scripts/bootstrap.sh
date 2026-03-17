#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${ONEFETCH_PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Missing Python executable: $PYTHON_BIN"
  exit 1
fi

cd "$PROJECT_ROOT"

if [[ ! -d ".venv" ]]; then
  echo "[bootstrap] creating virtualenv at $PROJECT_ROOT/.venv"
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate

echo "[bootstrap] upgrading pip"
pip install -U pip

echo "[bootstrap] installing core dependencies"
pip install -e ".[dev]"

if [[ "${ONEFETCH_INSTALL_BROWSER:-0}" == "1" ]]; then
  echo "[bootstrap] installing browser dependencies"
  pip install -e ".[browser]"
  if command -v playwright >/dev/null 2>&1; then
    playwright install chromium
  else
    python -m playwright install chromium
  fi
fi

echo "[bootstrap] done"
