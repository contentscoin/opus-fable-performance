#!/bin/bash
# Opus-Fable long-session reminder.
# Runs silently unless the transcript is long and Opus-Fable appears active.

THRESHOLD=500000

input=$(cat)
tp=$(printf '%s' "$input" | sed -n 's/.*"transcript_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$tp" ] && exit 0
[ -f "$tp" ] || exit 0

size=$(wc -c < "$tp" 2>/dev/null | tr -d ' ')
[ "${size:-0}" -lt "$THRESHOLD" ] && exit 0

style_on=0
cwd=$(printf '%s' "$input" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
for f in "$HOME/.claude/settings.json" "$cwd/.claude/settings.local.json" "$cwd/.claude/settings.json"; do
  [ -f "$f" ] && grep -qsiE '"outputStyle"[[:space:]]*:[[:space:]]*"(opus-fable-performance:)?opus-fable"' "$f" && style_on=1 && break
done

if [ "$style_on" -eq 0 ]; then
  on=$(grep -nF -e 'OPUS-FABLE ACTIVE' "$tp" 2>/dev/null | tail -1 | cut -d: -f1)
  [ -z "$on" ] && exit 0
fi

printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"<opus-fable-reminder>Maintain Opus-Fable: optimize for correctness and decisive verification, explain the clues, compare serious alternatives when they affect the decision, and state residual risk.</opus-fable-reminder>"}}'
exit 0
