#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
COOKIE_FILE="${ONEFETCH_ZHIHU_COOKIE_FILE:-$PROJECT_ROOT/.secrets/zhihu_cookie.txt}"

mkdir -p "$(dirname "$COOKIE_FILE")"
chmod 700 "$(dirname "$COOKIE_FILE")" || true

cat <<'HELP'
=== Zhihu Cookie Setup ===

Required format: Header String (one line)
  z_c0=...; d_c0=...; _zap=...; ...

How to get it:
  Method 1: F12 DevTools
    1. Open zhihu.com in browser, log in
    2. F12 → Network → refresh page
    3. Click any request → Headers → copy the "Cookie:" value

  Method 2: Browser extension
    - "Cookie-Editor": click Export → Header String
    - "Get cookies.txt": copy the header string format

Note: Must be "Header String" format (key=value; key=value; ...),
      NOT Netscape/curl format.

HELP

# Try clipboard first (macOS pbpaste / Linux xclip)
clipboard=""
if command -v pbpaste &>/dev/null; then
  clipboard="$(pbpaste 2>/dev/null || true)"
elif command -v xclip &>/dev/null; then
  clipboard="$(xclip -selection clipboard -o 2>/dev/null || true)"
fi

if [[ -n "$clipboard" && "$clipboard" == *"="* && "$clipboard" == *";"* ]]; then
  cookie_content="$(printf '%s' "$clipboard" | tr -d '\r\n' | sed 's/^ *//; s/ *$//')"
  echo "[setup_zhihu_cookie] detected cookie from clipboard (${#cookie_content} chars)"
  printf '  %.60s...\n' "$cookie_content"
  printf 'Use this? [Y/n] '
  IFS= read -r confirm
  if [[ -z "$confirm" || "$confirm" =~ ^[Yy] ]]; then
    printf '%s\n' "$cookie_content" > "$COOKIE_FILE"
    chmod 600 "$COOKIE_FILE" || true
    echo "[setup_zhihu_cookie] saved to: $COOKIE_FILE"
    echo "[setup_zhihu_cookie] run with: bash scripts/run_ingest.sh --present --refresh '<zhihu-url>'"
    exit 0
  fi
  echo "Skipped clipboard content."
fi

# Fallback
echo "Clipboard not available or content not recognized."
echo "Alternative: copy cookie to a file, then run:"
echo "  bash scripts/setup_zhihu_cookie.sh < /path/to/cookie.txt"
echo ""
echo "Or paste below and press Enter:"
printf '> '

IFS= read -r cookie_content
cookie_content="$(printf '%s' "$cookie_content" | tr -d '\r' | sed 's/^ *//; s/ *$//')"

if [[ -z "$cookie_content" ]]; then
  echo "[setup_zhihu_cookie] empty input, aborted"
  exit 1
fi

if [[ "$cookie_content" != *"="* || "$cookie_content" != *";"* ]]; then
  echo "[setup_zhihu_cookie] input does not look like a cookie header string"
  exit 2
fi

printf '%s\n' "$cookie_content" > "$COOKIE_FILE"
chmod 600 "$COOKIE_FILE" || true

echo "[setup_zhihu_cookie] saved to: $COOKIE_FILE"
echo "[setup_zhihu_cookie] run with: bash scripts/run_ingest.sh --present --refresh '<zhihu-url>'"
