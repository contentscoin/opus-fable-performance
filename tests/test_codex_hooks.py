#!/usr/bin/env python3
"""Contract tests for the Opus-Fable Codex hook layer."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CodexHookTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="opus-fable-hook-test-")
        self.env = os.environ.copy()
        self.env["PLUGIN_ROOT"] = str(ROOT)
        self.env["PLUGIN_DATA"] = self.tmpdir.name
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.base = {"session_id": self.id(), "cwd": str(ROOT)}

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def run_hook(self, script: str, payload: dict) -> dict:
        proc = subprocess.run(
            [sys.executable, str(ROOT / script)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stdout = proc.stdout.strip() or "{}"
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"{script} returned invalid JSON: {stdout!r}")
            raise exc

    def event_dir(self) -> Path:
        raw = f"{self.base['session_id']}|{self.base['cwd']}"
        key = hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:24]
        return Path(self.tmpdir.name) / "events" / key

    def test_korean_review_only_is_quick(self) -> None:
        out = self.run_hook(
            "hooks/codex/user_prompt_submit.py",
            {**self.base, "hook_event_name": "UserPromptSubmit", "prompt": "수정하지 말고 리뷰만 해줘"},
        )
        self.assertIn("quick", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.run_hook("hooks/codex/stop_gate.py", {**self.base, "hook_event_name": "Stop"}), {})

    def test_normal_change_requires_then_accepts_verification(self) -> None:
        self.run_hook(
            "hooks/codex/user_prompt_submit.py",
            {**self.base, "hook_event_name": "UserPromptSubmit", "prompt": "Implement a small code fix"},
        )
        self.run_hook(
            "hooks/codex/post_tool_use.py",
            {
                **self.base,
                "hook_event_name": "PostToolUse",
                "tool_name": "functions.apply_patch",
                "tool_input": "*** Begin Patch\n*** Update File: app.py\n+x\n*** End Patch\n",
                "tool_response": {"success": True},
            },
        )
        blocked = self.run_hook("hooks/codex/stop_gate.py", {**self.base, "hook_event_name": "Stop"})
        self.assertEqual(blocked.get("decision"), "block")

        self.run_hook(
            "hooks/codex/post_tool_use.py",
            {
                **self.base,
                "hook_event_name": "PostToolUse",
                "tool_name": "functions.shell_command",
                "tool_input": {"command": "python -m py_compile app.py"},
                "tool_response": {"success": True, "stdout": "success"},
            },
        )
        self.assertEqual(self.run_hook("hooks/codex/stop_gate.py", {**self.base, "hook_event_name": "Stop"}), {})

    def test_deep_stop_blocks_at_most_twice(self) -> None:
        self.run_hook(
            "hooks/codex/user_prompt_submit.py",
            {**self.base, "hook_event_name": "UserPromptSubmit", "prompt": "최고 성능으로 깊게 배포 전 검증해줘"},
        )
        first = self.run_hook("hooks/codex/stop_gate.py", {**self.base, "hook_event_name": "Stop"})
        self.assertEqual(first.get("decision"), "block")
        self.run_hook(
            "hooks/codex/user_prompt_submit.py",
            {**self.base, "hook_event_name": "UserPromptSubmit", "prompt": first["reason"]},
        )

        second = self.run_hook("hooks/codex/stop_gate.py", {**self.base, "hook_event_name": "Stop"})
        self.assertEqual(second.get("decision"), "block")
        self.run_hook(
            "hooks/codex/user_prompt_submit.py",
            {**self.base, "hook_event_name": "UserPromptSubmit", "prompt": second["reason"]},
        )

        third = self.run_hook("hooks/codex/stop_gate.py", {**self.base, "hook_event_name": "Stop"})
        self.assertNotEqual(third.get("decision"), "block")
        self.assertIn("verification", third.get("systemMessage", ""))

    def test_pre_tool_blocks_narrow_destructive_commands_only(self) -> None:
        denied = self.run_hook(
            "hooks/codex/pre_tool_use.py",
            {
                **self.base,
                "hook_event_name": "PreToolUse",
                "tool_name": "functions.shell_command",
                "tool_input": {"command": "rm -rf build"},
            },
        )
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

        for command in (
            "git push origin master",
            "vercel --prod",
            "supabase db push",
            "npm publish",
            "terraform apply -auto-approve",
        ):
            with self.subTest(command=command):
                allowed = self.run_hook(
                    "hooks/codex/pre_tool_use.py",
                    {
                        **self.base,
                        "hook_event_name": "PreToolUse",
                        "tool_name": "functions.shell_command",
                        "tool_input": {"command": command},
                    },
                )
                self.assertEqual(allowed, {})

    def test_concurrent_post_hooks_use_event_journal_without_shared_replace(self) -> None:
        payloads = [
            {
                **self.base,
                "hook_event_name": "PostToolUse",
                "tool_name": "functions.apply_patch",
                "tool_input": f"*** Begin Patch\n*** Update File: app_{idx}.py\n+x\n*** End Patch\n",
                "tool_response": {"success": True},
            }
            for idx in range(32)
        ]

        def run(payload: dict) -> dict:
            return self.run_hook("hooks/codex/post_tool_use.py", payload)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outputs = list(pool.map(run, payloads))

        self.assertTrue(all(output == {} for output in outputs))
        self.assertEqual(len(list(self.event_dir().glob("*.json"))), 32)

    def test_codex_hooks_json_uses_portable_python_commands(self) -> None:
        data = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        commands: list[str] = []
        for groups in data["hooks"].values():
            for group in groups:
                for hook in group["hooks"]:
                    commands.append(hook["command"])

        self.assertTrue(commands)
        self.assertTrue(all(command.startswith('python "${PLUGIN_ROOT}/hooks/codex/') for command in commands))
        self.assertTrue(all("CLAUDE_PLUGIN_ROOT" not in command for command in commands))
        self.assertTrue(all(":-" not in command for command in commands))
        self.assertTrue(all(not command.startswith("bash ") for command in commands))


if __name__ == "__main__":
    unittest.main()
