#!/usr/bin/env python3
"""Stop-time completion gate for Opus-Fable (Codex and Claude Code).

Checks, in order:
1. blocked mode -> keep going until the risk is narrowed.
2. Fable 5.1 last-paragraph rule -> a normal/deep turn must not end on a plan,
   a promise, or a next-steps list for work not yet done.
3. verification gate -> normal/deep changes need observed verification.

At most MAX_STOP_BLOCKS continuations are issued per user turn; after that the
gate only asks for the verification gap to be reported.
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from of_hook_core import (
    append_event,
    collect_state,
    emit_json,
    read_stdin_json,
    stop_decision,
    warning_after_max_blocks,
)


FAIL_OPEN_PREFIX = (
    "opus-fable plugin bookkeeping/output issue; failed open. "
    "This is not evidence that verification passed:"
)


def failure_payload(exc: Exception) -> dict[str, object]:
    return {"systemMessage": f"{FAIL_OPEN_PREFIX} {exc}"}


def last_message(input_data: dict) -> str:
    value = input_data.get("last_assistant_message")
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in value)
    return ""


def main() -> dict[str, object]:
    input_data = read_stdin_json()
    if input_data.get("stop_hook_active") is True:
        return {
            "systemMessage": "opus-fable stop hook is already active; allowing stop to avoid a continuation loop.",
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": "opus-fable: stop hook was already active, so no additional block was issued.",
            },
        }

    state = collect_state(input_data)
    block, reason = stop_decision(state, last_message(input_data))
    if block:
        append_event(input_data, "stop_block", reason=reason, mode=state.get("mode"))
        return {"decision": "block", "reason": reason}

    warning = warning_after_max_blocks(state)
    if warning:
        return {
            "systemMessage": warning,
            "hookSpecificOutput": {
                "hookEventName": "Stop",
                "additionalContext": warning,
            },
        }
    return {}


def run() -> int:
    captured_stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_stdout):
            payload = main()
    except Exception as exc:
        payload = failure_payload(exc)
    emit_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
