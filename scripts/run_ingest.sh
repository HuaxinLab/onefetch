#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  echo "[run_ingest] missing virtual environment, running bootstrap"
  bash "$(dirname "${BASH_SOURCE[0]}")/bootstrap.sh"
fi

source "$PROJECT_ROOT/.venv/bin/activate"

if ! command -v onefetch >/dev/null 2>&1; then
  echo "[run_ingest] onefetch command missing, running bootstrap"
  bash "$(dirname "${BASH_SOURCE[0]}")/bootstrap.sh"
  source "$PROJECT_ROOT/.venv/bin/activate"
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: run_ingest.sh [onefetch ingest args]"
  echo "Examples:"
  echo "  run_ingest.sh \"https://example.com\""
  echo "  run_ingest.sh --store \"https://example.com\""
  exit 2
fi

onefetch ingest "$@"
