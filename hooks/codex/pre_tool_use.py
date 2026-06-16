#!/usr/bin/env python3
"""Pre-tool guardrails for Opus-Fable."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from of_hook_core import append_event, classify_tool_risk, emit_json, read_stdin_json


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
    emit_json(deny(reason) if blocked else {})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit_json({"systemMessage": f"opus-fable pre-tool hook failed open: {exc}"})
        raise SystemExit(0)

