#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CLEAN_VENV=0
ASSUME_YES=0
DELETE_DATA=""

usage() {
  cat <<USAGE
Usage: scripts/clean.sh [--all] [--yes] [--keep-data]

Options:
  --all        Also remove .venv (will ask confirmation unless --yes)
  --yes        Skip confirmations
  --keep-data  Keep data/ and reports/ even after confirmation phase
  -h, --help   Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      CLEAN_VENV=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    --keep-data)
      DELETE_DATA=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[clean] unknown option: $1"
      usage
      exit 2
      ;;
  esac
done

cd "$PROJECT_ROOT"

if [[ -z "$DELETE_DATA" ]]; then
  if [[ "$ASSUME_YES" == "1" ]]; then
    DELETE_DATA=1
  elif [[ -t 0 ]]; then
    echo "[clean] data/: saved content outputs; reports/: run summary files."
    read -r -p "[clean] delete data/ and reports/? [y/N] " answer
    case "$answer" in
      y|Y|yes|YES)
        DELETE_DATA=1
        ;;
      *)
        DELETE_DATA=0
        ;;
    esac
  else
    DELETE_DATA=0
    echo "[clean] non-interactive mode without --yes; keeping data/ and reports/"
  fi
fi

echo "[clean] removing runtime caches/artifacts"
if [[ "$DELETE_DATA" == "1" ]]; then
  rm -rf data reports
else
  echo "[clean] skipped data/ and reports/"
fi
rm -rf .pytest_cache
rm -rf onefetch.egg-info
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name ".DS_Store" \) -delete

if [[ "$CLEAN_VENV" == "1" ]]; then
  if [[ "$ASSUME_YES" == "1" ]]; then
    echo "[clean] removing .venv"
    rm -rf .venv
  elif [[ -t 0 ]]; then
    read -r -p "[clean] also delete .venv? [y/N] " answer
    case "$answer" in
      y|Y|yes|YES)
        echo "[clean] removing .venv"
        rm -rf .venv
        ;;
      *)
        echo "[clean] skipped .venv"
        ;;
    esac
  else
    echo "[clean] non-interactive mode without --yes; skipped .venv"
  fi
fi

echo "[clean] done"
