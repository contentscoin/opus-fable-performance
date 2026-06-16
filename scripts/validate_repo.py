#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "NOTICE.md",
    "LICENSE",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json",
    "output-styles/opus-fable.md",
    "skills/opus-fable/SKILL.md",
    "agents/opus-reviewer.md",
    "hooks/hooks.json",
    "hooks/codex/user_prompt_submit.py",
    "hooks/codex/pre_tool_use.py",
    "hooks/codex/post_tool_use.py",
    "hooks/codex/stop_gate.py",
    "hooks/router.sh",
    "hooks/finish-the-work.sh",
    "hooks/opus-reminder.sh",
    "packs/investigation-protocol.ko.md",
    "packs/verification-grounding.ko.md",
    "packs/evidence-gate.ko.md",
    "packs/reviewer-gate.ko.md",
    "packs/capability-escalation.ko.md",
    "scripts/of_goals.py",
    "scripts/of_hook_core.py",
    "tests/test_codex_hooks.py",
    "setup/install-codex.ps1",
    "setup/install-claude.sh",
    "setup/enable-strict-stop.sh",
    "setup/disable-strict-stop.sh",
    "codex/AGENTS.opus-fable.md",
    ".agents/skills/opus-fable/SKILL.md",
    ".agents/skills/opus-fable/agents/openai.yaml",
    "docs/research.md",
    "docs/routing.md",
    "docs/evaluation.md",
    "evals/rubric.md",
    "evals/tasks.jsonl",
]

FRONTMATTER_FILES = [
    "output-styles/opus-fable.md",
    "skills/opus-fable/SKILL.md",
    "agents/opus-reviewer.md",
    ".agents/skills/opus-fable/SKILL.md",
]


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def require_file(path: str) -> pathlib.Path:
    full = ROOT / path
    if not full.is_file():
        fail(f"missing file: {path}")
    return full


def validate_json(path: str) -> None:
    full = require_file(path)
    try:
        json.loads(full.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid JSON in {path}: {exc}")


def validate_frontmatter(path: str) -> None:
    text = require_file(path).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"missing frontmatter: {path}")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        fail(f"malformed frontmatter: {path}")
    block = match.group(1)
    for field in ("name:", "description:"):
        if field not in block:
            fail(f"{path} frontmatter missing {field}")


def validate_jsonl(path: str) -> None:
    full = require_file(path)
    for i, line in enumerate(full.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            json.loads(line)
        except Exception as exc:
            fail(f"invalid JSONL in {path}:{i}: {exc}")


def main() -> None:
    for path in REQUIRED_FILES:
        require_file(path)
    for path in [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", ".codex-plugin/plugin.json", "hooks/hooks.json"]:
        validate_json(path)
    for path in FRONTMATTER_FILES:
        validate_frontmatter(path)
    validate_jsonl("evals/tasks.jsonl")
    print("[OK] repository structure validated")


if __name__ == "__main__":
    main()
