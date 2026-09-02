#!/usr/bin/env python3
"""Pre-tool guardrails for Opus-Fable.

Two layers:
- deny: a narrow set of destructive local commands and secret-file edits.
- advise: Fable 5.1 rules that never block but inject context (push gate,
  history rewrite, hook bypass, empty commit, evidence-before-state-change,
  test skip). Each advisory flag is injected once per user turn.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from of_hook_core import (
    ADVISORY_PUSH,
    advise_tool,
    append_event,
    classify_tool_risk,
    collect_state,
    emit_json,
    read_stdin_json,
)


def deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    input_data = read_stdin_json()
    blocked, flags, reason = classify_tool_risk(input_data)
    if flags:
        append_event(input_data, "risk", flags=flags, reason=reason)
    if blocked:
        emit_json(deny(reason))
        return 0

    state = collect_state(input_data)
    adv_flags, messages = advise_tool(input_data, state)
    if not adv_flags:
        emit_json({})
        return 0

    already = set(state.get("advisories") or [])
    append_event(input_data, "advisory", flags=adv_flags)
    # The push gate is re-issued every time; other advisories are issued once per turn.
    fresh = [msg for flag, msg in zip(adv_flags, messages) if flag == ADVISORY_PUSH or flag not in already]
    if not fresh:
        emit_json({})
        return 0
    emit_json(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "\n".join(fresh),
            }
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit_json({"systemMessage": f"opus-fable pre-tool hook failed open: {exc}"})
        raise SystemExit(0)
