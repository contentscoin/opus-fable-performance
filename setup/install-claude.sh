#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-local}"

if [ "$TARGET" = "global" ]; then
  BASE="$HOME/.claude"
else
  BASE="$(pwd)/.claude"
fi

mkdir -p "$BASE/skills/opus-fable" "$BASE/agents" "$BASE/output-styles" "$BASE/hooks"
cp "$ROOT/skills/opus-fable/SKILL.md" "$BASE/skills/opus-fable/SKILL.md"
cp "$ROOT/agents/opus-reviewer.md" "$BASE/agents/opus-reviewer.md"
cp "$ROOT/output-styles/opus-fable.md" "$BASE/output-styles/opus-fable.md"
cp "$ROOT/hooks/opus-reminder.sh" "$BASE/hooks/opus-reminder.sh"
cp "$ROOT/hooks/router.sh" "$BASE/hooks/router.sh"
cp "$ROOT/hooks/finish-the-work.sh" "$BASE/hooks/finish-the-work.sh"
chmod +x "$BASE/hooks/opus-reminder.sh" "$BASE/hooks/router.sh" "$BASE/hooks/finish-the-work.sh"

echo "Installed Opus-Fable Claude assets into $BASE"

