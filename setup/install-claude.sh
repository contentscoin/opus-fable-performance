#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-local}"

if [ "$TARGET" = "global" ]; then
  BASE="$HOME/.claude"
else
  BASE="$(pwd)/.claude"
fi

# Skills, agents, and output styles are picked up from the standard locations.
mkdir -p "$BASE/skills/opus-fable" "$BASE/agents" "$BASE/output-styles"
cp "$ROOT/skills/opus-fable/SKILL.md" "$BASE/skills/opus-fable/SKILL.md"
cp "$ROOT/agents/opus-reviewer.md" "$BASE/agents/opus-reviewer.md"
cp "$ROOT/output-styles/opus-fable.md" "$BASE/output-styles/opus-fable.md"

# Hooks resolve packs/ and scripts/ relative to their own location, so the
# whole tree is copied together under one root.
PLUGIN="$BASE/opus-fable"
rm -rf "$PLUGIN"
mkdir -p "$PLUGIN"
cp -R "$ROOT/hooks" "$ROOT/scripts" "$ROOT/packs" "$PLUGIN/"
chmod +x "$PLUGIN"/hooks/*.sh

cat <<EOF
Installed Opus-Fable Claude assets into $BASE
Hooks, scripts, and packs were copied to $PLUGIN

Add this to your settings.json (or install the repo as a plugin, which wires hooks/claude-hooks.json automatically):

  "hooks": $(CLAUDE_PLUGIN_ROOT="$PLUGIN" python3 - "$ROOT/hooks/claude-hooks.json" "$PLUGIN" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))["hooks"]
text = json.dumps(data, indent=2, ensure_ascii=False).replace("${CLAUDE_PLUGIN_ROOT}", sys.argv[2])
print("\n  ".join(text.splitlines()))
PY
)
EOF
