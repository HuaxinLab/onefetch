#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
COOKIE_FILE_DEFAULT="$PROJECT_ROOT/.secrets/xhs_cookie.txt"
COOKIE_FILE="${ONEFETCH_XHS_COOKIE_FILE:-$COOKIE_FILE_DEFAULT}"

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

if [[ -z "${ONEFETCH_XHS_COOKIE:-}" && -f "$COOKIE_FILE" ]]; then
  ONEFETCH_XHS_COOKIE="$(cat "$COOKIE_FILE")"
  export ONEFETCH_XHS_COOKIE
  echo "[run_ingest] loaded XHS cookie from $COOKIE_FILE"
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: run_ingest.sh [onefetch ingest args]"
  echo "Examples:"
  echo "  run_ingest.sh \"https://example.com\""
  echo "  run_ingest.sh --store \"https://example.com\""
  echo "  run_ingest.sh --present \"https://example.com\""
  echo "  setup_xhs_cookie.sh then run xiaohongshu comment mode"
  exit 2
fi

onefetch ingest "$@"
