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
    "hooks/claude-hooks.json",
    "hooks/codex/user_prompt_submit.py",
    "hooks/codex/pre_tool_use.py",
    "hooks/codex/post_tool_use.py",
    "hooks/codex/stop_gate.py",
    "hooks/router.sh",
    "hooks/finish-the-work.sh",
    "hooks/strict_stop.py",
    "hooks/session_resume.py",
    "hooks/opus-reminder.sh",
    "packs/investigation-protocol.ko.md",
    "packs/verification-grounding.ko.md",
    "packs/evidence-gate.ko.md",
    "packs/reviewer-gate.ko.md",
    "packs/capability-escalation.ko.md",
    "packs/delivery-contract.ko.md",
    "packs/final-report.ko.md",
    "packs/change-validation.ko.md",
    "packs/pr-drive-to-green.ko.md",
    "packs/untrusted-input.ko.md",
    "scripts/of_goals.py",
    "scripts/of_hook_core.py",
    "tests/test_codex_hooks.py",
    "tests/test_fable_harness.py",
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


def validate_claude_plugin_wiring() -> None:
    manifest = json.loads(require_file(".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    if manifest.get("hooks") != "./hooks/claude-hooks.json":
        fail(".claude-plugin/plugin.json must point hooks to ./hooks/claude-hooks.json (hooks/hooks.json is the Codex file)")
    hooks = json.loads(require_file("hooks/claude-hooks.json").read_text(encoding="utf-8")).get("hooks", {})
    for groups in hooks.values():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command", "")
                if "${CLAUDE_PLUGIN_ROOT}" not in command or "${PLUGIN_ROOT}" in command:
                    fail(f"claude-hooks.json command must use ${{CLAUDE_PLUGIN_ROOT}}: {command}")
    packs_dir = ROOT / "packs"
    router = require_file("hooks/router.sh").read_text(encoding="utf-8")
    for match in set(re.findall(r"([a-z-]+\.ko\.md)", router)):
        if not (packs_dir / match).is_file():
            fail(f"router.sh references missing pack: {match}")


def validate_skill_pack_sync() -> None:
    """Every pack must be reachable from both skills, and neither may point at a
    pack that does not exist. This is the gate that caught v0.4 skill drift."""
    packs = {path.name for path in (ROOT / "packs").glob("*.ko.md")}
    if not packs:
        fail("packs/ contains no .ko.md files")
    for skill in ("skills/opus-fable/SKILL.md", ".agents/skills/opus-fable/SKILL.md"):
        text = require_file(skill).read_text(encoding="utf-8")
        referenced = set(re.findall(r"([a-z-]+\.ko\.md)", text))
        missing = sorted(packs - referenced)
        if missing:
            fail(f"{skill} does not reference these packs: {', '.join(missing)}")
        unknown = sorted(referenced - packs)
        if unknown:
            fail(f"{skill} references missing packs: {', '.join(unknown)}")


def main() -> None:
    for path in REQUIRED_FILES:
        require_file(path)
    for path in [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", ".codex-plugin/plugin.json", "hooks/hooks.json", "hooks/claude-hooks.json"]:
        validate_json(path)
    for path in FRONTMATTER_FILES:
        validate_frontmatter(path)
    validate_jsonl("evals/tasks.jsonl")
    validate_claude_plugin_wiring()
    validate_skill_pack_sync()
    print("[OK] repository structure validated")


if __name__ == "__main__":
    main()
