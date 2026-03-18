#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export ONEFETCH_PROJECT_ROOT="$PROJECT_ROOT"

if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  bash "$(dirname "${BASH_SOURCE[0]}")/bootstrap.sh"
fi

VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if ! "$VENV_PYTHON" -c "import onefetch" >/dev/null 2>&1; then
  bash "$(dirname "${BASH_SOURCE[0]}")/bootstrap.sh"
fi

exec "$VENV_PYTHON" -m onefetch.cli "$@"
