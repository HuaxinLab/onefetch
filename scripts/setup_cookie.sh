#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# --- Platform config ---
platform="${1:-}"

case "$platform" in
  zhihu)
    cookie_file="zhihu_cookie.txt"
    example_format="z_c0=...; d_c0=...; _zap=...; ..."
    site_domain="zhihu.com"
    run_hint="bash scripts/run_ingest.sh --present --refresh '<zhihu-url>'"
    ;;
  xhs)
    cookie_file="xhs_cookie.txt"
    example_format="a1=...; web_session=...; ..."
    site_domain="xiaohongshu.com"
    run_hint="ONEFETCH_XHS_COMMENT_MODE='state+api' bash scripts/run_ingest.sh '<xhs-url>'"
    ;;
  *)
    echo "Usage: bash scripts/setup_cookie.sh <platform>"
    echo ""
    echo "Supported platforms: zhihu, xhs"
    exit 1
    ;;
esac

COOKIE_FILE="${PROJECT_ROOT}/.secrets/${cookie_file}"

mkdir -p "$(dirname "$COOKIE_FILE")"
chmod 700 "$(dirname "$COOKIE_FILE")" || true

cat <<HELP
=== ${platform} Cookie Setup ===

Required format: Header String (one line)
  ${example_format}

How to get it:
  Method 1: F12 DevTools
    1. Open ${site_domain} in browser, log in
    2. F12 → Network → refresh page
    3. Click any request → Headers → copy the "Cookie:" value

  Method 2: Browser extension
    - "Cookie-Editor": click Export → Header String
    - "Get cookies.txt": copy the header string format

Note: Must be "Header String" format (key=value; key=value; ...),
      NOT Netscape/curl format.

HELP

# --- Determine read method ---
has_clipboard=false
if command -v pbpaste &>/dev/null || command -v xclip &>/dev/null; then
  has_clipboard=true
fi

# If stdin is redirected (piped / file), read from it directly
if [[ ! -t 0 ]]; then
  cookie_content="$(cat | tr -d '\r\n' | sed 's/^ *//; s/ *$//')"
else
  if $has_clipboard; then
    echo "Step: Copy the cookie to your clipboard, then press Enter."
    printf '> '
    IFS= read -r _
    # Read clipboard
    if command -v pbpaste &>/dev/null; then
      cookie_content="$(pbpaste 2>/dev/null | tr -d '\r\n' | sed 's/^ *//; s/ *$//')"
    else
      cookie_content="$(xclip -selection clipboard -o 2>/dev/null | tr -d '\r\n' | sed 's/^ *//; s/ *$//')"
    fi
    echo "[setup_cookie:${platform}] read from clipboard (${#cookie_content} chars)"
  else
    echo "No clipboard tool found. Paste below and press Enter:"
    printf '> '
    IFS= read -r cookie_content
    cookie_content="$(printf '%s' "$cookie_content" | tr -d '\r' | sed 's/^ *//; s/ *$//')"
  fi
fi

if [[ -z "$cookie_content" ]]; then
  echo "[setup_cookie:${platform}] empty input, aborted"
  exit 1
fi

if [[ "$cookie_content" != *"="* || "$cookie_content" != *";"* ]]; then
  echo "[setup_cookie:${platform}] input does not look like a cookie header string"
  echo "  Got: $(printf '%.60s' "$cookie_content")..."
  exit 2
fi

printf '%s\n' "$cookie_content" > "$COOKIE_FILE"
chmod 600 "$COOKIE_FILE" || true

echo "[setup_cookie:${platform}] saved to: $COOKIE_FILE"
echo "[setup_cookie:${platform}] run with: ${run_hint}"
