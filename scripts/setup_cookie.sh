#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# --- Platform config ---
platform="${1:-}"

if [[ -z "$platform" ]]; then
  echo "Usage: bash scripts/setup_cookie.sh <platform|domain>"
  echo ""
  echo "内置平台: zhihu, xhs"
  echo "任意域名: bash scripts/setup_cookie.sh example.com"
  exit 1
fi

case "$platform" in
  zhihu)
    cookie_file="zhihu_cookie.txt"
    run_hint="bash scripts/run_cli.sh ingest --present --refresh '<zhihu-url>'"
    ;;
  xhs)
    cookie_file="xhs_cookie.txt"
    run_hint="ONEFETCH_XHS_COMMENT_MODE='state+api' bash scripts/run_cli.sh ingest '<xhs-url>'"
    ;;
  *)
    # 任意域名
    cookie_file="${platform}_cookie.txt"
    run_hint="bash scripts/run_cli.sh ingest --present '<${platform}-url>'"
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
  echo "Copy the cookie to clipboard, then press Enter to confirm."
  printf '[Enter] '
  IFS= read -r _
  cookie_content="$(pbpaste 2>/dev/null | tr -d '\r\n' | sed 's/^ *//; s/ *$//')"
elif command -v xclip &>/dev/null; then
  echo "Copy the cookie to clipboard, then press Enter to confirm."
  printf '[Enter] '
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
