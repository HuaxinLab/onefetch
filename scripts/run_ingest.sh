#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
XHS_COOKIE_FILE_DEFAULT="$PROJECT_ROOT/.secrets/xhs_cookie.txt"
XHS_COOKIE_FILE="${ONEFETCH_XHS_COOKIE_FILE:-$XHS_COOKIE_FILE_DEFAULT}"
ZHIHU_COOKIE_FILE_DEFAULT="$PROJECT_ROOT/.secrets/zhihu_cookie.txt"
ZHIHU_COOKIE_FILE="${ONEFETCH_ZHIHU_COOKIE_FILE:-$ZHIHU_COOKIE_FILE_DEFAULT}"

if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  echo "[run_ingest] missing virtual environment, running bootstrap"
  bash "$(dirname "${BASH_SOURCE[0]}")/bootstrap.sh"
fi

VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if ! "$VENV_PYTHON" -c "import onefetch" >/dev/null 2>&1; then
  echo "[run_ingest] onefetch not installed in venv, running bootstrap"
  bash "$(dirname "${BASH_SOURCE[0]}")/bootstrap.sh"
fi

if [[ -z "${ONEFETCH_XHS_COOKIE:-}" && -f "$XHS_COOKIE_FILE" ]]; then
  ONEFETCH_XHS_COOKIE="$(cat "$XHS_COOKIE_FILE")"
  export ONEFETCH_XHS_COOKIE
  echo "[run_ingest] loaded XHS cookie from $XHS_COOKIE_FILE"
fi

if [[ -z "${ONEFETCH_ZHIHU_COOKIE:-}" && -f "$ZHIHU_COOKIE_FILE" ]]; then
  ONEFETCH_ZHIHU_COOKIE="$(cat "$ZHIHU_COOKIE_FILE")"
  export ONEFETCH_ZHIHU_COOKIE
  echo "[run_ingest] loaded Zhihu cookie from $ZHIHU_COOKIE_FILE"
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: run_ingest.sh [onefetch ingest args]"
  echo "Examples:"
  echo "  run_ingest.sh \"https://example.com\""
  echo "  run_ingest.sh --store \"https://example.com\""
  echo "  run_ingest.sh --present \"https://example.com\""
  echo "  setup_xhs_cookie.sh then run xiaohongshu comment mode"
  echo "  setup_zhihu_cookie.sh then run zhihu zhuanlan url"
  exit 2
fi

"$VENV_PYTHON" -m onefetch.cli ingest "$@"
