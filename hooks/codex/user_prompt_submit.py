#!/usr/bin/env python3
"""Classify incoming prompts for Opus-Fable (Codex and Claude Code)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from of_hook_core import (
    append_event,
    classify_intent,
    classify_prompt,
    collect_state,
    context_for_mode,
    emit_json,
    read_stdin_json,
)


CONTINUATION_PREFIXES = (
    "opus-fable:",
    "[opus-fable",
)


def main() -> int:
    input_data = read_stdin_json()
    prompt = str(input_data.get("prompt") or input_data.get("user_prompt") or "")
    normalized = prompt.lstrip().lower()

    if normalized.startswith(CONTINUATION_PREFIXES):
        state = collect_state(input_data)
        emit_json(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context_for_mode(
                        str(state["mode"]), list(state["risks"]), str(state.get("intent") or "unknown")
                    ),
                }
            }
        )
        return 0

    mode, risks, goal = classify_prompt(prompt)
    intent = classify_intent(prompt)
    append_event(input_data, "prompt_start", mode=mode, risks=risks, goal=goal, intent=intent)

    if mode == "blocked":
        emit_json(
            {
                "decision": "block",
                "reason": "opus-fable blocked this prompt because it appears destructive or secret-bearing. Narrow the scope or provide an explicit safe boundary.",
            }
        )
        return 0

    emit_json(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context_for_mode(mode, risks, intent),
            }
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit_json({"systemMessage": f"opus-fable prompt hook failed open: {exc}"})
        raise SystemExit(0)
