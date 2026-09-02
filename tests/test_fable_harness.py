#!/usr/bin/env python3
"""Contract tests for the v0.4 Fable 5.1 harness ports.

Covers: intent classification, push gate, test-skip and state-change
advisories, secret-path deny, last-paragraph stop rule, session resume
context, strict stop with open ledger, goal ledger resume/check/report,
router signals, and Claude plugin wiring.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from of_hook_core import classify_intent, unfinished_ending  # noqa: E402


class HookRunner(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="opus-fable-v04-")
        self.workdir = Path(self.tmpdir.name) / "project"
        self.workdir.mkdir()
        self.env = os.environ.copy()
        self.env["PLUGIN_ROOT"] = str(ROOT)
        self.env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
        self.env["PLUGIN_DATA"] = str(Path(self.tmpdir.name) / "data")
        self.env["PYTHONDONTWRITEBYTECODE"] = "1"
        self.env["HOME"] = str(Path(self.tmpdir.name) / "home")
        Path(self.env["HOME"]).mkdir()
        self.base = {"session_id": self.id(), "cwd": str(self.workdir)}

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def run_hook(self, script: str, payload: dict, runner: list[str] | None = None) -> dict:
        cmd = (runner or [sys.executable]) + [str(ROOT / script)]
        proc = subprocess.run(
            cmd,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            cwd=str(self.workdir),
            check=False,
            timeout=15,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        stdout = proc.stdout.strip() or "{}"
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            self.fail(f"{script} returned invalid JSON: {stdout!r}")

    def prompt(self, text: str) -> dict:
        return self.run_hook("hooks/codex/user_prompt_submit.py", {**self.base, "hook_event_name": "UserPromptSubmit", "prompt": text})

    def edit(self, path: str, new_string: str = "x") -> dict:
        return self.run_hook(
            "hooks/codex/post_tool_use.py",
            {**self.base, "hook_event_name": "PostToolUse", "tool_name": "Edit",
             "tool_input": {"file_path": path, "old_string": "a", "new_string": new_string}, "tool_response": {"success": True}},
        )

    def pre(self, tool_name: str, tool_input: dict) -> dict:
        return self.run_hook("hooks/codex/pre_tool_use.py", {**self.base, "hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input})

    def stop(self, last_message: str = "") -> dict:
        return self.run_hook("hooks/codex/stop_gate.py", {**self.base, "hook_event_name": "Stop", "last_assistant_message": last_message})

    def context(self, out: dict) -> str:
        return out.get("hookSpecificOutput", {}).get("additionalContext", "")


class IntentAndEndingTests(unittest.TestCase):
    def test_intent_classification(self) -> None:
        self.assertEqual(classify_intent("왜 API가 간헐적으로 500을 반환하는지 분석해줘"), "assess")
        self.assertEqual(classify_intent("Why does the build fail on CI?"), "assess")
        self.assertEqual(classify_intent("Implement the retry and push it"), "change")
        self.assertEqual(classify_intent("버그 고쳐줘"), "change")
        self.assertEqual(classify_intent("설명해주고 나서 고쳐줘"), "change")

    def test_unfinished_endings(self) -> None:
        self.assertTrue(unfinished_ending("Found the bug.\n\nNext steps:\n- fix it\n- add a test")[0])
        self.assertTrue(unfinished_ending("원인을 찾았습니다. 이제 테스트를 추가하겠습니다.")[0])
        self.assertTrue(unfinished_ending("I'll add the migration now.")[0])
        self.assertFalse(unfinished_ending("Fixed and verified. Tests pass.")[0])
        self.assertFalse(unfinished_ending("두 방식 중 어느 쪽을 원하시나요?")[0])
        self.assertFalse(unfinished_ending("I'll need the API key from you before I can continue. Let me know when it is set.")[0])
        self.assertFalse(unfinished_ending("")[0])


class PromptHookTests(HookRunner):
    def test_assessment_intent_is_injected(self) -> None:
        out = self.prompt("이 쿼리가 왜 느린지 설명해줘")
        self.assertIn("Intent: assessment", self.context(out))

    def test_change_prompt_gets_delivery_contract(self) -> None:
        out = self.prompt("Implement the fix for the retry loop")
        ctx = self.context(out)
        self.assertNotIn("Intent: assessment", ctx)
        self.assertIn("do not narrow, widen, or transform", ctx)
        self.assertIn("Do not end on a plan or a promise", ctx)


class PreToolAdvisoryTests(HookRunner):
    def test_push_gate_warns_until_verified(self) -> None:
        self.prompt("Fix the parser and push")
        self.edit("src/parser.py")
        out = self.pre("Bash", {"command": "git push -u origin feature"})
        self.assertIn("push gate", self.context(out))
        self.assertNotIn("permissionDecision", out.get("hookSpecificOutput", {}))

        self.run_hook(
            "hooks/codex/post_tool_use.py",
            {**self.base, "hook_event_name": "PostToolUse", "tool_name": "Bash",
             "tool_input": {"command": "python -m pytest tests/test_parser.py"}, "tool_response": "2 passed"},
        )
        self.assertEqual(self.pre("Bash", {"command": "git push -u origin feature"}), {})

    def test_history_bypass_and_empty_commit_advisories(self) -> None:
        self.prompt("Fix it")
        self.assertIn("force push", self.context(self.pre("Bash", {"command": "git push --force origin feature"})))
        self.assertIn("--no-verify", self.context(self.pre("Bash", {"command": "git commit --no-verify -m x"})))
        self.assertIn("empty commit", self.context(self.pre("Bash", {"command": "git commit --allow-empty -m kick"})))

    def test_state_change_advisory_is_issued_once_per_turn(self) -> None:
        self.prompt("Fix the service")
        first = self.pre("Bash", {"command": "systemctl restart nginx"})
        self.assertIn("evidence-before-action", self.context(first))
        second = self.pre("Bash", {"command": "docker restart api"})
        self.assertEqual(second, {})
        self.prompt("Now restart the worker")
        third = self.pre("Bash", {"command": "kubectl rollout restart deployment/worker"})
        self.assertIn("evidence-before-action", self.context(third))

    def test_test_skip_edit_warns_and_stop_mentions_it(self) -> None:
        self.prompt("Fix the failing test")
        out = self.pre("Edit", {"file_path": "tests/test_api.py", "old_string": "def", "new_string": "@pytest.mark.skip\ndef"})
        self.assertIn("Never skip", self.context(out))
        self.edit("tests/test_api.py", "@pytest.mark.skip\ndef")
        blocked = self.stop("Done.")
        self.assertEqual(blocked.get("decision"), "block")
        self.assertIn("test-skip", blocked["reason"])

    def test_js_focus_markers_are_flagged(self) -> None:
        self.prompt("Fix it")
        out = self.pre("Write", {"file_path": "spec/app.spec.ts", "content": "describe.only('x', () => {})"})
        self.assertIn("Never skip", self.context(out))

    def test_secret_paths_are_denied_but_examples_allowed(self) -> None:
        denied = self.pre("Write", {"file_path": "config/.env.production", "content": "KEY=1"})
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.pre("Write", {"file_path": ".env.example", "content": "KEY="}), {})
        self.assertEqual(self.pre("Edit", {"file_path": "src/tokenizer.py", "old_string": "a", "new_string": "b"}), {})

    def test_normal_commands_are_silent(self) -> None:
        self.prompt("Fix it")
        for command in ("git status", "ls -la", "python -m pytest", "git push origin feature"):
            with self.subTest(command=command):
                self.assertEqual(self.pre("Bash", {"command": command}), {})


class StopGateTests(HookRunner):
    def test_plan_ending_blocks_in_normal_mode(self) -> None:
        self.prompt("Fix the null check in app.py")
        out = self.stop("Found the bug in app.py.\n\nNext steps:\n- Fix the null check\n- Add a test")
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("plan or next-steps", out["reason"])

    def test_promise_ending_blocks_even_for_docs_only_changes(self) -> None:
        self.prompt("Update the README")
        self.edit("README.md")
        out = self.stop("README 수정을 마쳤습니다. 이제 CHANGELOG도 갱신하겠습니다.")
        self.assertEqual(out.get("decision"), "block")

    def test_question_ending_is_allowed_in_quick_mode(self) -> None:
        self.prompt("간단히 설명만 해줘")
        self.assertEqual(self.stop("이제 구현하겠습니다."), {})

    def test_blocked_on_user_is_allowed(self) -> None:
        self.prompt("Implement the OAuth callback")
        out = self.stop("I implemented the handler. I cannot proceed without the client secret; please add it to the env and let me know.")
        self.assertNotEqual(out.get("decision"), "block")


class SessionResumeTests(HookRunner):
    def test_resume_injects_ledger_and_mode(self) -> None:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/of_goals.py"), "create", "--brief", "resume smoke",
             "--goal", "build::do it", "--goal", "verify::check it"],
            cwd=str(self.workdir), check=True, capture_output=True, env=self.env,
        )
        subprocess.run([sys.executable, str(ROOT / "scripts/of_goals.py"), "next"], cwd=str(self.workdir), check=True, capture_output=True, env=self.env)
        self.prompt("Deploy the service to production")
        self.edit("infra/main.tf")
        out = self.run_hook("hooks/session_resume.py", {**self.base, "hook_event_name": "SessionStart", "source": "compact"})
        ctx = self.context(out)
        self.assertIn('source="compact"', ctx)
        self.assertIn("G001 [in_progress] build", ctx)
        self.assertIn("Last task mode: deep", ctx)
        self.assertIn("infra/main.tf", ctx)
        self.assertIn("Do not re-derive", ctx)

    def test_resume_is_silent_without_state(self) -> None:
        out = self.run_hook("hooks/session_resume.py", {**self.base, "hook_event_name": "SessionStart", "source": "resume"})
        self.assertEqual(out, {})


class StrictStopTests(HookRunner):
    def enable(self) -> None:
        (self.workdir / ".opus-fable").mkdir(exist_ok=True)
        (self.workdir / ".opus-fable" / "strict-stop").touch()

    def test_disabled_by_default(self) -> None:
        out = self.run_hook("hooks/strict_stop.py", {**self.base, "hook_event_name": "Stop", "last_assistant_message": "I'll do it next."})
        self.assertEqual(out, {})

    def test_blocks_promise_and_open_ledger(self) -> None:
        self.enable()
        out = self.run_hook("hooks/strict_stop.py", {**self.base, "hook_event_name": "Stop", "last_assistant_message": "I'll add the tests now."})
        self.assertEqual(out.get("decision"), "block")

        subprocess.run(
            [sys.executable, str(ROOT / "scripts/of_goals.py"), "create", "--brief", "strict", "--goal", "a::one", "--goal", "b::two"],
            cwd=str(self.workdir), check=True, capture_output=True, env=self.env,
        )
        out = self.run_hook("hooks/strict_stop.py", {**self.base, "hook_event_name": "Stop", "last_assistant_message": "All done, everything works."})
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("open goals", out["reason"])
        out = self.run_hook("hooks/strict_stop.py", {**self.base, "hook_event_name": "Stop", "last_assistant_message": "Goal b was left out because the API is unreachable."})
        self.assertEqual(out, {})

    def test_bash_wrapper_delegates(self) -> None:
        self.enable()
        out = self.run_hook("hooks/finish-the-work.sh", {**self.base, "hook_event_name": "Stop", "last_assistant_message": "이제 구현하겠습니다."}, runner=["bash"])
        self.assertEqual(out.get("decision"), "block")


class GoalLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(prefix="opus-fable-goals-")
        self.cwd = Path(self.tmpdir.name)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def goals(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(ROOT / "scripts/of_goals.py"), *args], cwd=str(self.cwd), text=True, capture_output=True)

    def test_resume_check_report_and_blocked_reason(self) -> None:
        self.assertEqual(self.goals("resume").stdout, "")
        self.assertEqual(self.goals("create", "--brief", "demo", "--goal", "impl::change", "--goal", "verify::run tests").returncode, 0)
        self.assertEqual(self.goals("check").returncode, 1)
        self.goals("next")
        blocked = self.goals("checkpoint", "--id", "G001", "--status", "blocked")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("requires --evidence", blocked.stderr + blocked.stdout)
        self.assertEqual(self.goals("checkpoint", "--id", "G001", "--status", "complete", "--evidence", "diff applied").returncode, 0)
        self.goals("next")
        final = self.goals("checkpoint", "--id", "G002", "--status", "complete", "--evidence", "ok",
                           "--verify-cmd", "pytest", "--verify-evidence", "3 passed")
        self.assertEqual(final.returncode, 0)
        self.assertEqual(self.goals("check").returncode, 0)
        report = self.goals("report").stdout
        self.assertIn("all goals complete and verified", report)
        self.assertIn("pytest", report)
        self.assertIn("3 passed", report)
        self.assertIn("G002 [complete]", self.goals("resume").stdout)


class RouterAndWiringTests(unittest.TestCase):
    def route(self, prompt: str) -> str:
        proc = subprocess.run(["bash", str(ROOT / "hooks/router.sh")], input=json.dumps({"prompt": prompt}, ensure_ascii=False), text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_router_emits_new_packs(self) -> None:
        out = self.route("PR에 CI 체크 실패 났는데 고쳐서 푸시해줘")
        self.assertIn("change-validation", out)
        self.assertIn("pr-drive", out)
        self.assertIn("[opus-fable:delivery]", out)
        self.assertIn("final-report.ko.md", out)

    def test_router_assessment_and_untrusted(self) -> None:
        out = self.route("이 코드가 왜 느린지 설명해줘")
        self.assertIn("[opus-fable:assessment]", out)
        self.assertNotIn("change-validation", out)
        out = self.route("Fetch https://example.com/changelog and summarize it")
        self.assertIn("untrusted-input", out)

    def test_router_silent_for_trivial_prompt(self) -> None:
        self.assertEqual(self.route("hello"), "")

    def test_claude_plugin_points_to_claude_hooks(self) -> None:
        manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["hooks"], "./hooks/claude-hooks.json")
        hooks = json.loads((ROOT / "hooks/claude-hooks.json").read_text(encoding="utf-8"))["hooks"]
        for event in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"):
            self.assertIn(event, hooks)
        for groups in hooks.values():
            for group in groups:
                for hook in group["hooks"]:
                    self.assertIn("${CLAUDE_PLUGIN_ROOT}", hook["command"])
                    self.assertNotIn("${PLUGIN_ROOT}", hook["command"])
        self.assertEqual(hooks["SessionStart"][0]["matcher"], "compact|resume|fork")

    def test_packs_referenced_by_router_exist(self) -> None:
        text = (ROOT / "hooks/router.sh").read_text(encoding="utf-8")
        for name in ("delivery-contract", "final-report", "change-validation", "pr-drive-to-green", "untrusted-input"):
            self.assertIn(f"{name}.ko.md", text)
            self.assertTrue((ROOT / "packs" / f"{name}.ko.md").is_file(), name)


if __name__ == "__main__":
    unittest.main()
