#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"

if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  echo "Missing virtual environment: $PROJECT_ROOT/.venv"
  echo "Run docs/INSTALLATION.md setup first."
  exit 1
fi

source "$PROJECT_ROOT/.venv/bin/activate"

if [[ $# -eq 0 ]]; then
  echo "Usage: run_ingest.sh [onefetch ingest args]"
  echo "Example: run_ingest.sh \"https://example.com\""
  exit 2
fi

onefetch ingest "$@"
