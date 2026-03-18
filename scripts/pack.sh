#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
OUTPUT_DIR="${ONEFETCH_PACK_OUTPUT_DIR:-release}"
ARCHIVE_NAME=""

usage() {
  cat <<USAGE
Usage: scripts/pack.sh [--name <zip-name>] [--output <dir>]

Options:
  --name <zip-name>     Archive name (e.g., onefetch.zip)
  --output <dir>        Output directory (default: release)
  -h, --help            Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      ARCHIVE_NAME="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[pack] unknown option: $1"
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$ARCHIVE_NAME" ]]; then
  STAMP="$(date +%Y%m%d-%H%M%S)"
  ARCHIVE_NAME="onefetch-skill-${STAMP}.zip"
fi

cd "$PROJECT_ROOT"

mkdir -p "$OUTPUT_DIR"

if ! command -v zip >/dev/null 2>&1; then
  echo "[pack] zip command not found"
  exit 1
fi

ARCHIVE_PATH="$OUTPUT_DIR/$ARCHIVE_NAME"

# Keep skill/runtime sources only; exclude local artifacts and caches.
zip -rq "$ARCHIVE_PATH" . \
  -x ".git/*" \
  -x ".venv/*" \
  -x "data/*" \
  -x "reports/*" \
  -x "release/*" \
  -x "tests/*" \
  -x ".pytest_cache/*" \
  -x "dist/*" \
  -x "*/__pycache__/*" \
  -x "__pycache__/*" \
  -x "*.pyc" \
  -x "*.pyo" \
  -x "*.egg-info/*" \
  -x "*.DS_Store"

echo "[pack] created: $ARCHIVE_PATH"
