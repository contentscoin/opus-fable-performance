#!/usr/bin/env python3
"""Stop-time completion gate for Opus-Fable."""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from of_hook_core import append_event, collect_state, emit_json, read_stdin_json, stop_decision, warning_after_max_blocks


FAIL_OPEN_PREFIX = (
    "opus-fable plugin bookkeeping/output issue; failed open. "
    "This is not evidence that verification passed:"
)


def failure_payload(exc: Exception) -> dict[str, object]:
    return {"systemMessage": f"{FAIL_OPEN_PREFIX} {exc}"}


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
    block, reason = stop_decision(state)
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

