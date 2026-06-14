#!/usr/bin/env python3
"""Opus-Fable goal ledger with evidence and final verification gates."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE = Path(".opus-fable")
GOALS = STATE / "goals.json"
LEDGER = STATE / "ledger.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(event: str, **data: object) -> None:
    STATE.mkdir(exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now(), "event": event, **data}, ensure_ascii=False) + "\n")


def load() -> dict:
    if not GOALS.exists():
        sys.exit("opus-fable: no goal plan. Run `create` from the repo root first.")
    return json.loads(GOALS.read_text(encoding="utf-8"))


def save(plan: dict) -> None:
    STATE.mkdir(exist_ok=True)
    GOALS.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


def create(args: argparse.Namespace) -> None:
    if GOALS.exists() and not args.force:
        sys.exit("opus-fable: plan already exists. Use `status` or replace it with --force.")
    goals = []
    for i, raw in enumerate(args.goal, start=1):
        if "::" not in raw:
            sys.exit(f"opus-fable: invalid --goal format, expected 'title::objective': {raw}")
        title, objective = raw.split("::", 1)
        goals.append({
            "id": f"G{i:03d}",
            "title": title.strip(),
            "objective": objective.strip(),
            "status": "pending",
            "evidence": None,
            "verify_cmd": None,
            "verify_evidence": None,
        })
    if not goals:
        sys.exit("opus-fable: at least one --goal is required.")
    plan = {"brief": args.brief, "created": now(), "goals": goals}
    save(plan)
    log("plan_created", brief=args.brief, count=len(goals))
    print(f"opus-fable: plan created ({len(goals)} goals)")
    for goal in goals:
        print(f"  {goal['id']} {goal['title']}: {goal['objective']}")


def next_goal(_: argparse.Namespace) -> None:
    plan = load()
    active = [g for g in plan["goals"] if g["status"] == "in_progress"]
    if active:
        goal = active[0]
    else:
        pending = [g for g in plan["goals"] if g["status"] == "pending"]
        if not pending:
            print("opus-fable: all goals complete")
            return
        goal = pending[0]
        goal["status"] = "in_progress"
        save(plan)
        log("goal_started", id=goal["id"], title=goal["title"])
    is_final = goal["id"] == plan["goals"][-1]["id"]
    print(f"=== opus-fable handoff: {goal['id']} {goal['title']}")
    print(f"Objective: {goal['objective']}")
    print("Rule: work this goal only and record concrete evidence.")
    command = f"python scripts/of_goals.py checkpoint --id {goal['id']} --status complete --evidence \"<evidence>\""
    if is_final:
        print("Final goal: completion requires --verify-cmd and --verify-evidence.")
        command += " --verify-cmd \"<command>\" --verify-evidence \"<result>\""
    print(f"On completion: {command}")


def checkpoint(args: argparse.Namespace) -> None:
    plan = load()
    goal = next((g for g in plan["goals"] if g["id"] == args.id), None)
    if not goal:
        sys.exit(f"opus-fable: unknown goal id {args.id}")
    if goal["status"] != "in_progress":
        sys.exit(f"opus-fable: {args.id} is not active ({goal['status']}). Run `next` first.")
    if args.status == "complete":
        if not args.evidence.strip():
            sys.exit("opus-fable: complete requires non-empty --evidence.")
        if goal["id"] == plan["goals"][-1]["id"]:
            if not args.verify_cmd.strip() or not args.verify_evidence.strip():
                sys.exit("opus-fable: final goal requires --verify-cmd and --verify-evidence.")
    goal["status"] = args.status
    goal["evidence"] = args.evidence
    goal["verify_cmd"] = args.verify_cmd or None
    goal["verify_evidence"] = args.verify_evidence or None
    save(plan)
    log("checkpoint", id=goal["id"], status=args.status, evidence=args.evidence,
        verify_cmd=args.verify_cmd, verify_evidence=args.verify_evidence)
    remaining = [g for g in plan["goals"] if g["status"] in ("pending", "in_progress")]
    print(f"opus-fable: {goal['id']} -> {args.status}")
    print("opus-fable: all goals complete" if not remaining else f"opus-fable: {len(remaining)} goals remain")


def status(_: argparse.Namespace) -> None:
    plan = load()
    done = sum(1 for g in plan["goals"] if g["status"] == "complete")
    print(f"opus-fable: {done}/{len(plan['goals'])} complete - {plan['brief']}")
    marks = {"complete": "ok", "in_progress": "active", "pending": "pending", "failed": "failed", "blocked": "blocked"}
    for goal in plan["goals"]:
        print(f"  {goal['id']} [{marks.get(goal['status'], goal['status'])}] {goal['title']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="of_goals.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--brief", required=True)
    c.add_argument("--goal", action="append", default=[])
    c.add_argument("--force", action="store_true")

    sub.add_parser("next")

    k = sub.add_parser("checkpoint")
    k.add_argument("--id", required=True)
    k.add_argument("--status", required=True, choices=["complete", "failed", "blocked"])
    k.add_argument("--evidence", default="")
    k.add_argument("--verify-cmd", default="")
    k.add_argument("--verify-evidence", default="")

    sub.add_parser("status")

    args = parser.parse_args()
    {"create": create, "next": next_goal, "checkpoint": checkpoint, "status": status}[args.cmd](args)


if __name__ == "__main__":
    main()

