#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CLEAN_VENV=0
ASSUME_YES=0
DELETE_DATA=""

usage() {
  cat <<USAGE
Usage: scripts/clean.sh [--all] [--yes] [--with-data]

Options:
  --all        Also remove .venv (will ask confirmation unless --yes)
  --yes        Skip confirmations
  --with-data  Also delete data/ (saved articles, normally kept)
  -h, --help   Show help

Default behavior: clear cache and runtime artifacts, keep data/
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
    --with-data)
      DELETE_DATA=1
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

# Always clean: cache + runtime artifacts
echo "[clean] removing cache and runtime artifacts"
rm -rf reports
rm -rf .pytest_cache
rm -rf onefetch.egg-info
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name ".DS_Store" \) -delete

# data/ requires explicit opt-in or confirmation
if [[ "$DELETE_DATA" == "1" ]]; then
  echo "[clean] removing data/ (--with-data)"
  rm -rf data
elif [[ -z "$DELETE_DATA" && -d "data" ]]; then
  if [[ "$ASSUME_YES" == "1" ]]; then
    echo "[clean] kept data/ (use --with-data to delete)"
  elif [[ -t 0 ]]; then
    read -r -p "[clean] also delete data/ (saved articles)? [y/N] " answer
    case "$answer" in
      y|Y|yes|YES)
        echo "[clean] removing data/"
        rm -rf data
        ;;
      *)
        echo "[clean] kept data/"
        ;;
    esac
  else
    echo "[clean] kept data/"
  fi
fi

# .venv only with --all
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
