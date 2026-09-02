#!/usr/bin/env python3
"""SessionStart hook for Claude Code: re-inject Opus-Fable state after
compaction, resume, or fork.

Fable 5.1 context rule: after a context summary, do not re-derive facts that
were already established or re-litigate decisions the user already made. This
hook makes the goal ledger and the current task mode survive compaction.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from of_hook_core import collect_state, emit_json, read_stdin_json  # noqa: E402


def ledger_summary(cwd: Path) -> str:
    goals_path = cwd / ".opus-fable" / "goals.json"
    if not goals_path.is_file():
        return ""
    try:
        plan = json.loads(goals_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    goals = plan.get("goals") or []
    if not goals:
        return ""
    done = sum(1 for g in goals if g.get("status") == "complete")
    lines = [f"Goal ledger ({done}/{len(goals)} complete): {plan.get('brief', '')}"]
    for goal in goals:
        status = goal.get("status", "pending")
        line = f"- {goal.get('id')} [{status}] {goal.get('title')}: {goal.get('objective')}"
        if status == "complete" and goal.get("evidence"):
            line += f" | evidence: {str(goal.get('evidence'))[:160]}"
        elif status in {"blocked", "failed"} and goal.get("evidence"):
            line += f" | reason: {str(goal.get('evidence'))[:160]}"
        lines.append(line)
    active = [g for g in goals if g.get("status") == "in_progress"]
    pending = [g for g in goals if g.get("status") == "pending"]
    if active:
        lines.append(f"Resume with {active[0].get('id')}; record evidence via `python scripts/of_goals.py checkpoint`.")
    elif pending:
        lines.append("Run `python scripts/of_goals.py next` to start the next goal.")
    else:
        lines.append("All goals are complete; produce the final report with `python scripts/of_goals.py report`.")
    return "\n".join(lines)


def main() -> int:
    input_data = read_stdin_json()
    source = str(input_data.get("source") or "")
    cwd = Path(str(input_data.get("cwd") or os.getcwd()))

    sections: list[str] = []
    summary = ledger_summary(cwd)
    if summary:
        sections.append(summary)

    state = collect_state(input_data)
    if state.get("mode") != "quick" or state.get("changed_paths"):
        parts = [f"Last task mode: {state.get('mode')}"]
        if state.get("risks"):
            parts.append("risks: " + ", ".join(state["risks"]))
        if state.get("changed_paths"):
            parts.append("changed: " + ", ".join(state["changed_paths"][:12]))
        parts.append("verified: " + ("yes" if any(v.get("success") for v in state.get("verification_results", [])) else "no"))
        sections.append("; ".join(parts) + ".")

    if not sections:
        emit_json({})
        return 0

    header = f"<opus-fable-resume source=\"{source or 'unknown'}\">"
    footer = "Do not re-derive facts already established above; continue from the recorded state.</opus-fable-resume>"
    emit_json(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "\n".join([header, *sections, footer]),
            }
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit_json({"systemMessage": f"opus-fable session resume hook failed open: {exc}"})
        raise SystemExit(0)
