#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CLEAN_VENV=0

if [[ "${1:-}" == "--all" ]]; then
  CLEAN_VENV=1
fi

cd "$PROJECT_ROOT"

echo "[clean] removing runtime artifacts"
rm -rf data reports .pytest_cache
rm -rf onefetch.egg-info
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name ".DS_Store" \) -delete

if [[ "$CLEAN_VENV" == "1" ]]; then
  echo "[clean] removing .venv"
  rm -rf .venv
fi

echo "[clean] done"
