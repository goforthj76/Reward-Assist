#!/usr/bin/env bash
# Direct Linux runner for local development and direct executions
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$ROOT/platform-tools:$HOME/.local/bin:$PATH"
exec python3 "$ROOT/local_app.py" "$@"
