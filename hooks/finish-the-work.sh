#!/usr/bin/env bash
# Optional Stop hook. Blocks only when strict-stop is explicitly enabled.
# Enable by creating ./.opus-fable/strict-stop in the project root or ~/.opus-fable/strict-stop.

set -uo pipefail

input="$(cat)"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
printf '%s' "$input" > "$tmp"

python3 - "$tmp" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

input_path = sys.argv[1]
try:
    with open(input_path, encoding="utf-8") as f:
        payload = json.load(f)
except Exception:
    sys.exit(0)

def normalize_path(value):
    path = Path(value)
    if path.exists():
        return path
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", str(value))
    if match:
        drive = match.group(1).lower()
        rest = match.group(2).replace("\\", "/")
        candidate = Path(f"/mnt/{drive}/{rest}")
        if candidate.exists():
            return candidate
    return path

if payload.get("stop_hook_active"):
    sys.exit(0)

cwd = normalize_path(payload.get("cwd") or os.getcwd())
home = Path.home()
if not ((cwd / ".opus-fable" / "strict-stop").exists() or (home / ".opus-fable" / "strict-stop").exists()):
    sys.exit(0)

tpath = normalize_path(payload.get("transcript_path") or "")
if not str(tpath) or not tpath.is_file():
    sys.exit(0)

last_text = ""
last_had_tool = False
try:
    with open(tpath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            msg = obj.get("message", obj)
            if obj.get("type") == "assistant" or msg.get("role") == "assistant":
                content = msg.get("content", [])
                if isinstance(content, str):
                    last_text = content.strip()
                    last_had_tool = False
                elif isinstance(content, list):
                    texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    tools = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
                    if texts or tools:
                        last_text = "\n".join(texts).strip()
                        last_had_tool = bool(tools)
except Exception:
    sys.exit(0)

if last_had_tool or not last_text:
    sys.exit(0)

tail = last_text[-500:]

promise = re.search(
    r"(\bI\s*(?:will|'ll)\b|\blet me\b|\bnow I\b|\bnext I\b|"
    r"이제\s*(?:하겠|진행하겠|구현하겠|추가하겠|실행하겠)|"
    r"다음으로\s*(?:하겠|진행하겠|구현하겠|추가하겠|실행하겠)|"
    r"바로\s*(?:하겠|진행하겠|구현하겠|추가하겠|실행하겠))",
    tail,
    re.I,
)
asks_user = re.search(
    r"(\?|shall i|would you like|do you want|let me know|which option|"
    r"원하시면|할까요|하시겠습니까|어느 쪽|선택)",
    tail,
    re.I,
)

if promise and not asks_user:
    print(json.dumps({
        "decision": "block",
        "reason": "Strict Opus-Fable completion is enabled. The previous response ended with an intent to do work, but no tool action followed. Continue now with tool calls, or stop only if blocked on user input."
    }, ensure_ascii=False))
PY

exit 0
