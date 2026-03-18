#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

domain="${1:-}"

if [[ -z "$domain" ]]; then
  echo "Usage: bash scripts/setup_cookie.sh <域名>"
  echo ""
  echo "示例:"
  echo "  bash scripts/setup_cookie.sh zhihu.com"
  echo "  bash scripts/setup_cookie.sh xiaohongshu.com"
  echo "  bash scripts/setup_cookie.sh www.bilibili.com"
  echo "  bash scripts/setup_cookie.sh example.com"
  exit 1
fi

COOKIE_FILE="${PROJECT_ROOT}/.secrets/${domain}_cookie.txt"

mkdir -p "$(dirname "$COOKIE_FILE")"
chmod 700 "$(dirname "$COOKIE_FILE")" || true

# --- Read cookie ---
if [[ ! -t 0 ]]; then
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
  echo "[setup_cookie:${domain}] empty input, aborted"
  exit 1
fi

if [[ "$cookie_content" != *"="* || "$cookie_content" != *";"* ]]; then
  echo "[setup_cookie:${domain}] not a valid cookie header string"
  exit 2
fi

printf '%s\n' "$cookie_content" > "$COOKIE_FILE"
chmod 600 "$COOKIE_FILE" || true

echo "[setup_cookie:${domain}] saved (${#cookie_content} chars) → $COOKIE_FILE"
