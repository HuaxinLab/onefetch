#!/usr/bin/env bash
# Wrapper — delegates to unified setup_cookie.sh
exec bash "$(dirname "${BASH_SOURCE[0]}")/setup_cookie.sh" zhihu "$@"
