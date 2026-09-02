#!/usr/bin/env python3
"""Opt-in strict Stop hook for Claude Code.

Enabled only when `.opus-fable/strict-stop` exists in the project root or in
the home directory. When enabled it enforces two Fable 5.1 rules:

1. Last-paragraph rule: the turn must not end on a plan, a promise, or a
   next-steps list for work not yet done, unless blocked on user input.
2. Open ledger rule: if `.opus-fable/goals.json` still has pending or active
   goals, the turn must either finish them or say what was left out and why.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from of_hook_core import BLOCKED_ON_USER_RE, ASKS_USER_RE, emit_json, read_stdin_json, unfinished_ending  # noqa: E402


def normalize_path(value: str) -> Path:
    path = Path(value)
    if path.exists():
        return path
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", str(value))
    if match:
        candidate = Path(f"/mnt/{match.group(1).lower()}/{match.group(2).replace(chr(92), '/')}")
        if candidate.exists():
            return candidate
    return path


def strict_enabled(cwd: Path) -> bool:
    return (cwd / ".opus-fable" / "strict-stop").exists() or (Path.home() / ".opus-fable" / "strict-stop").exists()


def last_text_from_transcript(tpath: Path) -> tuple[str, bool]:
    last_text = ""
    last_had_tool = False
    try:
        with open(tpath, encoding="utf-8") as handle:
            for line in handle:
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
                        last_text, last_had_tool = content.strip(), False
                    elif isinstance(content, list):
                        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                        tools = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
                        if texts or tools:
                            last_text, last_had_tool = "\n".join(texts).strip(), bool(tools)
    except Exception:
        return "", False
    return last_text, last_had_tool


def open_goals(cwd: Path) -> list[str]:
    goals_path = cwd / ".opus-fable" / "goals.json"
    if not goals_path.is_file():
        return []
    try:
        plan = json.loads(goals_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [f"{g.get('id')} {g.get('title')}" for g in plan.get("goals") or [] if g.get("status") in {"pending", "in_progress"}]


def main() -> dict:
    payload = read_stdin_json()
    if payload.get("stop_hook_active"):
        return {}
    cwd = normalize_path(str(payload.get("cwd") or os.getcwd()))
    if not strict_enabled(cwd):
        return {}

    text = payload.get("last_assistant_message")
    had_tool = False
    if not isinstance(text, str) or not text.strip():
        tpath = normalize_path(str(payload.get("transcript_path") or ""))
        if not str(tpath) or not tpath.is_file():
            return {}
        text, had_tool = last_text_from_transcript(tpath)
    if had_tool or not text:
        return {}

    unfinished, why = unfinished_ending(text)
    if unfinished:
        return {
            "decision": "block",
            "reason": f"Strict Opus-Fable completion is enabled: {why}. Continue now with tool calls, or stop only if blocked on user input.",
        }

    remaining = open_goals(cwd)
    tail = text[-600:]
    if remaining and not (ASKS_USER_RE.search(tail) or BLOCKED_ON_USER_RE.search(tail)):
        if not re.search(r"(?i)(left out|not done|remaining|skipped|blocked|남았|하지 못|미완|건너뛰|보류)", tail):
            return {
                "decision": "block",
                "reason": (
                    "Strict Opus-Fable completion is enabled: the goal ledger still has open goals ("
                    + ", ".join(remaining[:5])
                    + "). Finish them, mark them blocked with a reason, or say explicitly what was left out and why."
                ),
            }
    return {}


if __name__ == "__main__":
    try:
        emit_json(main())
    except Exception as exc:
        emit_json({"systemMessage": f"opus-fable strict stop hook failed open: {exc}"})
    raise SystemExit(0)
