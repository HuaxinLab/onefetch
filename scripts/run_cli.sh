#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export ONEFETCH_PROJECT_ROOT="$PROJECT_ROOT"
XHS_COOKIE_FILE="${ONEFETCH_XHS_COOKIE_FILE:-$PROJECT_ROOT/.secrets/xhs_cookie.txt}"
ZHIHU_COOKIE_FILE="${ONEFETCH_ZHIHU_COOKIE_FILE:-$PROJECT_ROOT/.secrets/zhihu_cookie.txt}"

if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  bash "$(dirname "${BASH_SOURCE[0]}")/bootstrap.sh"
fi

VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if ! "$VENV_PYTHON" -c "import onefetch" >/dev/null 2>&1; then
  bash "$(dirname "${BASH_SOURCE[0]}")/bootstrap.sh"
fi

if [[ -z "${ONEFETCH_XHS_COOKIE:-}" && -f "$XHS_COOKIE_FILE" ]]; then
  ONEFETCH_XHS_COOKIE="$(cat "$XHS_COOKIE_FILE")"
  export ONEFETCH_XHS_COOKIE
fi

if [[ -z "${ONEFETCH_ZHIHU_COOKIE:-}" && -f "$ZHIHU_COOKIE_FILE" ]]; then
  ONEFETCH_ZHIHU_COOKIE="$(cat "$ZHIHU_COOKIE_FILE")"
  export ONEFETCH_ZHIHU_COOKIE
fi

exec "$VENV_PYTHON" -m onefetch.cli "$@"
