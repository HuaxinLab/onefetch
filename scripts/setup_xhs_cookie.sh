#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${ONEFETCH_PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
COOKIE_FILE="${ONEFETCH_XHS_COOKIE_FILE:-$PROJECT_ROOT/.secrets/xhs_cookie.txt}"

mkdir -p "$(dirname "$COOKIE_FILE")"
chmod 700 "$(dirname "$COOKIE_FILE")" || true

cat <<'TIPS'
Paste your Xiaohongshu Cookie Header String below.
Format example: a1=...; web_session=...; ...
Press Enter, then Ctrl-D to finish.
TIPS

cookie_content="$(cat)"
cookie_content="$(echo "$cookie_content" | tr -d '\r' | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g' | sed 's/^ *//; s/ *$//')"

if [[ -z "$cookie_content" ]]; then
  echo "[setup_xhs_cookie] empty input, aborted"
  exit 1
fi

if [[ "$cookie_content" != *"="* || "$cookie_content" != *";"* ]]; then
  echo "[setup_xhs_cookie] input does not look like a cookie header string"
  exit 2
fi

printf '%s\n' "$cookie_content" > "$COOKIE_FILE"
chmod 600 "$COOKIE_FILE" || true

echo "[setup_xhs_cookie] saved to: $COOKIE_FILE"
echo "[setup_xhs_cookie] run with: ONEFETCH_XHS_COMMENT_MODE='state+api' bash scripts/run_ingest.sh '<xhs-url>'"
