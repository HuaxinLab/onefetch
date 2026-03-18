#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# --- Platform config ---
platform="${1:-}"

case "$platform" in
  zhihu)
    cookie_file="zhihu_cookie.txt"
    run_hint="bash scripts/run_ingest.sh --present --refresh '<zhihu-url>'"
    ;;
  xhs)
    cookie_file="xhs_cookie.txt"
    run_hint="ONEFETCH_XHS_COMMENT_MODE='state+api' bash scripts/run_ingest.sh '<xhs-url>'"
    ;;
  *)
    echo "Usage: bash scripts/setup_cookie.sh <platform>"
    echo "Supported platforms: zhihu, xhs"
    exit 1
    ;;
esac

COOKIE_FILE="${PROJECT_ROOT}/.secrets/${cookie_file}"

mkdir -p "$(dirname "$COOKIE_FILE")"
chmod 700 "$(dirname "$COOKIE_FILE")" || true

# --- Read cookie ---
if [[ ! -t 0 ]]; then
  # stdin is redirected (pipe / file)
  cookie_content="$(cat | tr -d '\r\n' | sed 's/^ *//; s/ *$//')"
elif command -v pbpaste &>/dev/null; then
  echo "Copy the cookie to clipboard, then press Enter."
  printf '> '
  IFS= read -r _
  cookie_content="$(pbpaste 2>/dev/null | tr -d '\r\n' | sed 's/^ *//; s/ *$//')"
elif command -v xclip &>/dev/null; then
  echo "Copy the cookie to clipboard, then press Enter."
  printf '> '
  IFS= read -r _
  cookie_content="$(xclip -selection clipboard -o 2>/dev/null | tr -d '\r\n' | sed 's/^ *//; s/ *$//')"
else
  echo "No clipboard tool found. Paste cookie and press Enter:"
  printf '> '
  IFS= read -r cookie_content
  cookie_content="$(printf '%s' "$cookie_content" | tr -d '\r' | sed 's/^ *//; s/ *$//')"
fi

# --- Validate & save ---
if [[ -z "$cookie_content" ]]; then
  echo "[setup_cookie:${platform}] empty input, aborted"
  exit 1
fi

if [[ "$cookie_content" != *"="* || "$cookie_content" != *";"* ]]; then
  echo "[setup_cookie:${platform}] not a valid cookie header string"
  exit 2
fi

printf '%s\n' "$cookie_content" > "$COOKIE_FILE"
chmod 600 "$COOKIE_FILE" || true

echo "[setup_cookie:${platform}] saved (${#cookie_content} chars) → $COOKIE_FILE"
echo "[setup_cookie:${platform}] run with: ${run_hint}"
