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

VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
venv_pip() {
  "$VENV_PYTHON" -m pip "$@"
}

if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
  echo "[bootstrap] pip missing in .venv, running ensurepip"
  "$VENV_PYTHON" -m ensurepip --upgrade
fi

echo "[bootstrap] upgrading pip"
venv_pip install -U pip

echo "[bootstrap] installing core dependencies"
venv_pip install -e ".[dev]"

if [[ "${ONEFETCH_INSTALL_BROWSER:-0}" == "1" ]]; then
  echo "[bootstrap] installing browser dependencies"
  venv_pip install -e ".[browser]"
  "$VENV_PYTHON" -m playwright install chromium
fi

echo "[bootstrap] done"
