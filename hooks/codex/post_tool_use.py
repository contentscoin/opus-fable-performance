#!/usr/bin/env python3
"""Record Opus-Fable tool evidence after supported tool calls."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from of_hook_core import (
    append_event,
    changed_kinds,
    changed_paths,
    command_from_input,
    emit_json,
    exit_success,
    is_verification_command,
    read_stdin_json,
    redact,
    response_text,
    verification_coverage,
    FAILURE_RE,
)


def main() -> int:
    input_data = read_stdin_json()
    paths = changed_paths(input_data)
    kinds = changed_kinds(input_data)
    command = command_from_input(input_data)
    text = response_text(input_data.get("tool_response", input_data), 1000)
    success = exit_success(input_data, text)
    failure = success is False or (success is None and bool(FAILURE_RE.search(text)))

    if paths or kinds:
        append_event(input_data, "change", paths=paths, kinds=kinds)

    if command and is_verification_command(command):
        coverage = verification_coverage(command, paths)
        append_event(
            input_data,
            "verification",
            command=redact(command, 220),
            success=success,
            summary=redact(text, 220),
            coverage_relation=coverage,
        )

    if failure:
        append_event(input_data, "failure", summary=redact(text or command, 240), baseline="uncertain")
        emit_json(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "opus-fable: tool failure was observed; verify before final.",
                }
            }
        )
    else:
        emit_json({})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit_json({"systemMessage": f"opus-fable post-tool hook failed open: {exc}"})
        raise SystemExit(0)

