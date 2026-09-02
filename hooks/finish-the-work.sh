#!/usr/bin/env bash
# Optional strict Stop hook for Claude Code. Blocks only when strict-stop is explicitly enabled.
# Enable by creating ./.opus-fable/strict-stop in the project root or ~/.opus-fable/strict-stop.
#
# Logic lives in hooks/strict_stop.py (shared Fable 5.1 last-paragraph and open-ledger rules).

set -uo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

"$PY" "$ROOT/hooks/strict_stop.py"
exit 0
