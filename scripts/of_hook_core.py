#!/usr/bin/env python3
"""Codex hook helpers for Opus-Fable.

The hook state is an event journal instead of a single rewritten JSON ledger.
That keeps concurrent PostToolUse calls safe on Windows, where replacing the
same target file can fail with transient access-denied errors.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_STOP_BLOCKS = 2

# Advisory flags never deny a tool call; they inject context so the model can
# reconsider. Blocking flags (COMMAND_RULES / classify_patch) stay narrow.
ADVISORY_PUSH = "push-gate"
ADVISORY_HISTORY = "history-rewrite"
ADVISORY_BYPASS = "hook-bypass"
ADVISORY_EMPTY_COMMIT = "empty-commit"
ADVISORY_STATE_CHANGE = "state-change"
ADVISORY_TEST_SKIP = "test-skip"

CODE_EXTS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scss",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
}
DOC_EXTS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
CONFIG_EXTS = {".json", ".jsonc", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".lock"}
ASSET_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".pdf", ".mp3", ".mp4"}

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[^'\"\s]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{12,}"),
]

QUICK_RE = re.compile(
    r"(?i)\b(quick|brief|briefly|simple|simply|just explain|explain only|review only|"
    r"check only|read only|analysis only|no edits|do not edit)\b|"
    r"간단히|빠르게|설명만|검토만|리뷰만|분석만|읽어만|확인만|수정하지\s*말고|건드리지\s*말고"
)
DEEP_RE = re.compile(
    r"(?i)\b(deep|thorough|exhaustive|end-to-end|production-ready|deploy|deployment|"
    r"migration|database|auth|security|privacy|refactor|large|complex|opus|highest-quality|"
    r"maximum performance|implement the plan)\b|"
    r"깊게|철저|끝까지|전체|완성본|상용화|배포|마이그레이션|인증|보안|개인정보|리팩터|"
    r"최고\s*성능|효율보다\s*성능|성능이\s*가장\s*중요"
)
NORMAL_RE = re.compile(
    r"(?i)\b(implement|fix|debug|change|edit|create|build|test|lint|review|update|proceed)\b|"
    r"구현|수정|고쳐|디버그|작성|생성|테스트|검증|진행"
)
DESTRUCTIVE_REQUEST_RE = re.compile(
    r"(?i)(rm\s+-rf\s+/|delete\s+everything|drop\s+database|git\s+reset\s+--hard|"
    r"wipe\s+(the\s+)?repo|destroy\s+production)"
)
SAMPLE_RE = re.compile(r"(?i)\b(sample|example|test case|fixture|dry[- ]run)\b|검증|샘플|예시")

COMMAND_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "destructive-delete",
        re.compile(r"(?i)(^|[;&|]\s*)rm\s+-[A-Za-z]*r[A-Za-z]*f|rm\s+-[A-Za-z]*f[A-Za-z]*r"),
        "rm -rf is blocked.",
    ),
    ("destructive-delete", re.compile(r"(?i)\bfind\b.+\b-delete\b"), "Bulk find -delete is blocked."),
    ("destructive-delete", re.compile(r"(?i)\bxargs\b.+\brm\b"), "Bulk xargs rm is blocked."),
    (
        "destructive-delete",
        re.compile(r"(?i)\bRemove-Item\b.+\b-Recurse\b.+\b-Force\b"),
        "Recursive forced Remove-Item is blocked.",
    ),
    ("destructive-git", re.compile(r"(?i)\bgit\s+reset\s+--hard\b"), "git reset --hard is blocked."),
    ("destructive-git", re.compile(r"(?i)\bgit\s+clean\s+-[A-Za-z]*f"), "git clean -f is blocked."),
    ("infra-destroy", re.compile(r"(?i)\b(terraform\s+destroy|pulumi\s+destroy)\b"), "Infrastructure destruction is blocked."),
]

# Secret-bearing file names. Deliberately narrow: `tokenizer.py` or
# `password_validator.ts` are ordinary source files and must not be denied.
SECRET_FILE_PATH_RE = re.compile(
    r"(?i)(?:^|[\\/])(?:"
    r"\.env(?![\w.-]*(?:example|sample|template|dist))[\w.-]*|"
    r"id_(?:rsa|dsa|ecdsa|ed25519)[\w.-]*|"
    r"[\w.-]*\.(?:pem|key|p12|pfx|jks)|"
    r"(?:secrets?|credentials?|tokens?|passwords?|service[-_]account)(?:[.-][\w-]+)*\.(?:json|ya?ml|toml|txt|env|ini|cfg)|"
    r"\.netrc|\.pypirc|\.git-credentials"
    r")$"
)

# --- Fable 5.1 harness ports: advisory (non-blocking) tool rules -------------
GIT_PUSH_RE = re.compile(r"(?i)\bgit\s+push\b")
GIT_FORCE_PUSH_RE = re.compile(r"(?i)\bgit\s+push\b[^\n;&|]*(?:\s--force\b|\s-f\b|\s--force-with-lease\b)")
GIT_NO_VERIFY_RE = re.compile(r"(?i)\bgit\s+(?:commit|push)\b[^\n;&|]*\s--no-verify\b")
GIT_EMPTY_COMMIT_RE = re.compile(r"(?i)\bgit\s+commit\b[^\n;&|]*\s--allow-empty\b")
GIT_HISTORY_RE = re.compile(r"(?i)\bgit\s+(?:rebase\b|commit\b[^\n;&|]*\s--amend\b)")
STATE_CHANGE_RE = re.compile(
    r"(?i)\b("
    r"systemctl\s+(?:restart|stop|disable)|service\s+\S+\s+(?:restart|stop)|"
    r"docker\s+(?:restart|rm|kill|stop)|docker\s+compose\s+down|kubectl\s+(?:delete|rollout\s+restart|scale)|"
    r"pkill\b|killall\b|kill\s+-9|"
    r"git\s+checkout\s+(?:--\s+\S|\.(?:\s|$)|\S+\s+--\s+\S)|git\s+restore\s+(?!--staged)\S|"
    r"git\s+stash\s+(?:drop|clear)|git\s+branch\s+-D|"
    r"drop\s+table|truncate\s+table|"
    r"mv\s+(?:-[A-Za-z]+\s+)*\S+\s+\S+"
    r")"
)
TEST_SKIP_RE = re.compile(
    r"(?i)("
    r"@pytest\.mark\.(?:skip|xfail)|pytest\.skip\(|@unittest\.skip|self\.skipTest\(|"
    r"\b(?:it|test|describe|context)\.(?:skip|only)\(|\bx(?:it|test|describe)\(|\bfit\(|\bfdescribe\(|"
    r"#\[ignore\]|\bt\.Skip\(|@Ignore\b|@Disabled\b|\[Ignore\]|\[Skip\b|"
    r"testTimeout\s*[:=]\s*0|--no-verify|SKIP_TESTS|skip_ci|\[skip\s+ci\]|\[ci\s+skip\]"
    r")"
)
PROMISE_RE = re.compile(
    r"(?i)(\bI\s*(?:will|'ll)\b|\blet me\b|\bnow I\b|\bnext I\b|\bI am going to\b|\bI'm going to\b|"
    r"이제\s*(?:하겠|진행하겠|구현하겠|추가하겠|실행하겠|수정하겠|확인하겠)|"
    r"다음으로\s*(?:하겠|진행하겠|구현하겠|추가하겠|실행하겠|수정하겠|확인하겠)|"
    r"바로\s*(?:하겠|진행하겠|구현하겠|추가하겠|실행하겠|수정하겠|확인하겠)|"
    r"(?:하겠|진행하겠|구현하겠|추가하겠|실행하겠|수정하겠|확인하겠)습니다\s*\.?\s*$)"
)
PLAN_ENDING_RE = re.compile(
    r"(?im)^(?:#+\s*)?(?:\**)?(?:next\s+steps?|plan|remaining\s+(?:work|steps?)|to\s*do|"
    r"다음\s*단계|계획|남은\s*(?:작업|단계)|할\s*일)\s*(?:\**)?\s*:?\s*$"
)
ASKS_USER_RE = re.compile(
    r"(?i)(\?|shall i|would you like|do you want|let me know|which option|please confirm|"
    r"원하시면|할까요|하시겠습니까|어느 쪽|선택해|확인해\s*주|알려\s*주)"
)
BLOCKED_ON_USER_RE = re.compile(
    r"(?i)(blocked on|cannot proceed without|need(?:s)? (?:your|user) (?:input|decision|approval)|"
    r"waiting for (?:you|the user)|막혀|필요합니다\s*\.?\s*$|입력이 필요|결정이 필요|승인이 필요)"
)
ASSESS_RE = re.compile(
    r"(?i)^\s*(?:why|how|what|which|is|are|does|do|can|could|should|would|explain|describe|compare|analy[sz]e|"
    r"review|assess|evaluate|summari[sz]e|tell me)\b|"
    r"\?\s*$|왜|어떻게\s*(?:생각|보|되|동작)|설명해|분석해|비교해|검토해|리뷰해|평가해|요약해|알려\s*줘|무엇|뭐야|인가요|일까요|맞아\??"
)
# Imperative change requests win over question wording ("explain it, then fix it").
STRONG_CHANGE_RE = re.compile(
    r"(?i)\b(?:implement|fix|patch|refactor|migrate|deploy|push|commit|rename|install|configure|set up)\b|"
    r"\b(?:change|edit|create|add|remove|update|apply|write|make|build)\s+(?:it|this|that|the|a|an|me)\b|"
    r"구현해|고쳐|수정해|바꿔|추가해|삭제해|만들어|작성해|적용해|배포해|푸시해|커밋해|설치해|설정해|리팩터|반영해|올려"
)
CHANGE_RE = re.compile(
    r"(?i)\b(implement|fix|patch|change|edit|create|build|add|remove|refactor|migrate|deploy|write|update|apply|"
    r"push|commit|rename|delete|install|configure|make it|set up)\b|"
    r"구현|고쳐|수정해|바꿔|추가해|삭제해|만들어|작성해|적용해|배포해|푸시|커밋|설치해|설정해|리팩터|마이그레이션해|반영해"
)
PR_DRIVE_RE = re.compile(
    r"(?i)\b(pull request|\bpr\b|ci\b|pipeline|merge conflict|review comments?|checks? (?:failed|red)|"
    r"babysit|watch the pr|drive to green|mergeable)\b|"
    r"풀\s*리퀘|머지\s*충돌|리뷰\s*코멘트|체크\s*실패|파이프라인|머지\s*가능|PR\s*(?:봐|지켜|관리|올려|만들)"
)
PATCH_DELETE_RE = re.compile(r"(?im)^\*\*\* Delete File: ")
PATCH_PATH_RE = re.compile(r"(?im)^\*\*\* (?:Add|Update|Delete) File: (.+)$")

VERIFY_RE = re.compile(
    r"(?i)\b("
    r"pytest|unittest|go\s+test|cargo\s+test|npm\s+test|pnpm\s+test|yarn\s+test|bun\s+test|"
    r"mvn\s+test|gradle\s+test|rspec|vitest|jest|playwright|cypress|"
    r"lint|eslint|ruff|flake8|mypy|pyright|tsc|typecheck|"
    r"build|check|validate|verify|json\.tool|py_compile|curl"
    r")\b"
)
DIRECT_TEST_RE = re.compile(r"(?i)(pytest|unittest|vitest|jest|playwright|cypress|rspec|go\s+test|cargo\s+test)")
FAILURE_RE = re.compile(
    r"(?i)(command not found|no such file or directory|traceback|syntaxerror|failed|failure|"
    r"\berror:|\b[1-9][0-9]*\s+errors?\b|exit code\s*:?\s*[1-9]|exited with code\s*:?\s*[1-9]|"
    r"tests? failed|build failed|lint failed)"
)
EXIT_ZERO_RE = re.compile(r"(?i)\b(exit code|exited with code|process exited with code)\s*:?\s*0\b")
SUCCESS_RE = re.compile(
    r"(?i)\b(passed|success(?:fully)?|succeeded|0 failed|build completed|compiled successfully|"
    r"built successfully|build succeeded|done|valid)\b"
)
SUCCESS_STATUSES = {"success", "succeeded", "completed", "complete", "ok", "passed", "pass"}
FAILURE_STATUSES = {"failed", "failure", "error", "errored", "fatal", "timeout", "timed_out"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"_parse_error": "invalid stdin json"}
    return data if isinstance(data, dict) else {"_input": data}


def emit_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")


def redact(value: Any, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").replace("\n", " ").strip()
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def data_root() -> Path:
    env_data = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    base = Path(env_data).expanduser() if env_data else Path(tempfile.gettempdir()) / "opus-fable"
    return base.resolve()


def ledger_key(input_data: dict[str, Any]) -> str:
    cwd = input_data.get("cwd") or os.getcwd()
    session_id = input_data.get("session_id") or "no-session"
    raw = f"{session_id}|{cwd}"
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:24]


def event_dir(input_data: dict[str, Any]) -> Path:
    return data_root() / "events" / ledger_key(input_data)


def append_event(input_data: dict[str, Any], kind: str, **fields: Any) -> Path:
    directory = event_dir(input_data)
    directory.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": utc_now(),
        "time_ns": time.time_ns(),
        "pid": os.getpid(),
        "kind": kind,
        **fields,
    }
    name = f"{event['time_ns']}-{event['pid']}-{uuid.uuid4().hex}.json"
    tmp = directory / f".{name}.tmp"
    final = directory / name
    tmp.write_text(json.dumps(event, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, final)
    return final


def load_events(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    directory = event_dir(input_data)
    if not directory.exists():
        return []
    events: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"))[-500:]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            events.append(data)
    events.sort(key=lambda item: (int(item.get("time_ns") or 0), str(item.get("ts") or "")))
    return events


def active_events(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    events = load_events(input_data)
    last_prompt = -1
    for index, event in enumerate(events):
        if event.get("kind") == "prompt_start":
            last_prompt = index
    return events[last_prompt:] if last_prompt >= 0 else events


def classify_prompt(prompt: str) -> tuple[str, list[str], str]:
    text = prompt or ""
    lowered = text.lower()
    risks: list[str] = []
    if "production" in lowered or "배포" in text:
        risks.append("production")
    if re.search(r"(?i)\b(db|database|migration|migrate|schema)\b|데이터베이스|마이그레이션", text):
        risks.append("database")
    if re.search(r"(?i)\b(auth|secret|token|api[_ -]?key|password)\b|인증|비밀|토큰|권한", text):
        risks.append("secret-or-auth")
    if re.search(r"(?i)\b(release|publish|push)\b|릴리즈|공개|푸시", text):
        risks.append("remote-write")
    if re.search(r"(?i)\b(rm\s+-rf|delete|drop|destroy|wipe)\b|삭제|파괴", text):
        risks.append("destructive")

    if DESTRUCTIVE_REQUEST_RE.search(text) and not SAMPLE_RE.search(text):
        return "blocked", sorted(set(risks or ["blocked-risk"])), redact(text, 180)
    if DEEP_RE.search(text) or any(flag in risks for flag in ("production", "database", "remote-write", "secret-or-auth")):
        return "deep", sorted(set(risks)), redact(text, 180)
    if QUICK_RE.search(text) and not risks:
        return "quick", sorted(set(risks)), redact(text, 180)
    if NORMAL_RE.search(text):
        return "normal", sorted(set(risks)), redact(text, 180)
    return "quick", sorted(set(risks)), redact(text, 180)


def classify_intent(prompt: str) -> str:
    """Fable 5.1 delivery rule: a question or problem description wants an
    assessment, not a fix. Returns "assess", "change", or "unknown"."""
    text = (prompt or "").strip()
    if not text:
        return "unknown"
    if STRONG_CHANGE_RE.search(text):
        return "change"
    if ASSESS_RE.search(text):
        return "assess"
    if CHANGE_RE.search(text):
        return "change"
    return "unknown"


def context_for_mode(mode: str, risk_flags: list[str], intent: str = "unknown") -> str:
    lines = [f"opus-fable task mode: {mode}."]
    if risk_flags:
        lines.append("Risk flags: " + ", ".join(risk_flags) + ".")
    if intent == "assess":
        lines.append("Intent: assessment. Report findings and a recommendation; do not apply fixes unless asked.")
    if mode == "quick":
        lines.append("Keep this small; do not force a broad plan or unrelated verification.")
    elif mode == "normal":
        lines.append("If files change, run one relevant verifier or state why no verifier applies.")
    elif mode == "deep":
        lines.append("Define observable exit proof, compare serious risks, and verify before final.")
    elif mode == "blocked":
        lines.append("Do not proceed until the destructive or secret-bearing scope is narrowed.")
    if mode in {"normal", "deep"}:
        lines.append(
            "Deliver the requested scope as asked: do not narrow, widen, or transform it. "
            "If part is blocked, finish the rest and say what was left out and why."
        )
        lines.append("Do not end on a plan or a promise; do that work with tool calls, or stop only when blocked on user input.")
    lines.append("Never claim verification that was not actually observed.")
    return "\n".join(lines)


def tool_input_text(input_data: dict[str, Any]) -> str:
    tool_input = input_data.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("command", "description", "patch", "content"):
            if tool_input.get(key) is not None:
                return str(tool_input.get(key) or "")
    if isinstance(tool_input, str):
        return tool_input
    return ""


def classify_command(command: str) -> tuple[bool, list[str], str]:
    flags: list[str] = []
    reasons: list[str] = []
    for flag, pattern, reason in COMMAND_RULES:
        if pattern.search(command or ""):
            flags.append(flag)
            reasons.append(reason)
    if flags:
        return True, sorted(set(flags)), " ".join(reasons)
    return False, [], ""


def classify_patch(command: str) -> tuple[bool, list[str], str]:
    flags: list[str] = []
    reasons: list[str] = []
    if any(SECRET_FILE_PATH_RE.search(path.strip()) for path in PATCH_PATH_RE.findall(command or "")):
        flags.append("secret-file-edit")
        reasons.append("Edits to secret-bearing files are blocked.")
    if len(PATCH_DELETE_RE.findall(command or "")) > 5:
        flags.append("mass-delete")
        reasons.append("Patch deletes more than five files.")
    if flags:
        return True, flags, " ".join(reasons)
    return False, [], ""


EDIT_TOOLS = {"apply_patch", "functions.apply_patch", "edit", "write", "multiedit", "notebookedit"}
SHELL_TOOLS = {"bash", "shell", "shell_command", "functions.shell_command"}


def classify_tool_risk(input_data: dict[str, Any]) -> tuple[bool, list[str], str]:
    tool_name = str(input_data.get("tool_name") or "")
    name = tool_name.lower()
    command = tool_input_text(input_data)
    if name in EDIT_TOOLS:
        blocked, flags, reason = classify_patch(command)
        tool_input = input_data.get("tool_input")
        file_path = str(tool_input.get("file_path") or tool_input.get("path") or "") if isinstance(tool_input, dict) else ""
        if file_path and SECRET_FILE_PATH_RE.search(file_path) and "secret-file-edit" not in flags:
            flags.append("secret-file-edit")
            reason = (reason + " " if reason else "") + "Edits to secret-bearing files are blocked."
            blocked = True
        return blocked, flags, reason
    if name in SHELL_TOOLS:
        return classify_command(command)
    return False, [], ""


def edit_payload_text(input_data: dict[str, Any]) -> str:
    tool_input = input_data.get("tool_input")
    if isinstance(tool_input, dict):
        parts = [str(tool_input.get(key) or "") for key in ("content", "new_string", "patch", "command", "new_source")]
        edits = tool_input.get("edits")
        if isinstance(edits, list):
            parts.extend(str(item.get("new_string") or "") for item in edits if isinstance(item, dict))
        return "\n".join(part for part in parts if part)
    if isinstance(tool_input, str):
        return tool_input
    return ""


def advise_tool(input_data: dict[str, Any], state: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    """Non-blocking Fable 5.1 guardrails. Returns (flags, messages).

    - push-gate: pushing with changed files and no successful verification.
    - history-rewrite / hook-bypass / empty-commit: drive-to-green rules.
    - state-change: evidence must support the specific action, not a pattern match.
    - test-skip: never skip, disable, or quarantine a test to get green.
    """
    name = str(input_data.get("tool_name") or "").lower()
    flags: list[str] = []
    messages: list[str] = []

    if name in SHELL_TOOLS:
        command = tool_input_text(input_data)
        if GIT_PUSH_RE.search(command):
            current = state if state is not None else collect_state(input_data)
            if current.get("changed_files_seen") and not has_successful_verification(current):
                flags.append(ADVISORY_PUSH)
                messages.append(
                    "opus-fable push gate: files changed in this turn but no successful verification was observed. "
                    "Run the repo's fast checks (lint, typecheck, changed-package tests) before pushing, or state why none applies. "
                    "One validated push beats three speculative ones."
                )
            if GIT_FORCE_PUSH_RE.search(command):
                flags.append(ADVISORY_HISTORY)
                messages.append(
                    "opus-fable: force push rewrites history. Only do this on a branch you created; never on someone else's branch."
                )
        if GIT_NO_VERIFY_RE.search(command):
            flags.append(ADVISORY_BYPASS)
            messages.append("opus-fable: --no-verify bypasses repository hooks. Fix the failing check instead, or say why bypass is required.")
        if GIT_EMPTY_COMMIT_RE.search(command):
            flags.append(ADVISORY_EMPTY_COMMIT)
            messages.append("opus-fable: an empty commit to re-trigger CI is not a fix. Push a real change or re-run the job once.")
        if GIT_HISTORY_RE.search(command):
            flags.append(ADVISORY_HISTORY)
            messages.append("opus-fable: rebase/amend rewrites history. Confirm this branch is yours and unshared before continuing.")
        if STATE_CHANGE_RE.search(command):
            flags.append(ADVISORY_STATE_CHANGE)
            messages.append(
                "opus-fable evidence-before-action: this command changes system or workspace state. "
                "Check that the observed evidence supports this specific action; a signal that pattern-matches a known failure may have a different cause. "
                "Look at the target before overwriting or discarding it."
            )
    elif name in EDIT_TOOLS:
        payload = edit_payload_text(input_data)
        if payload and TEST_SKIP_RE.search(payload):
            flags.append(ADVISORY_TEST_SKIP)
            messages.append(
                "opus-fable: this edit skips, focuses, or disables a test or CI check. Never skip, disable, or quarantine a test to get green. "
                "If the user explicitly asked for it, say so in the final report; otherwise fix the root cause."
            )
    return sorted(set(flags)), messages


def unfinished_ending(text: str) -> tuple[bool, str]:
    """Fable 5.1 last-paragraph rule: a turn must not end on a plan, a promise,
    or a next-steps list for work not yet done, unless it is blocked on the user."""
    body = (text or "").strip()
    if not body:
        return False, ""
    tail = body[-600:]
    if ASKS_USER_RE.search(tail) or BLOCKED_ON_USER_RE.search(tail):
        return False, ""
    if PROMISE_RE.search(tail):
        return True, "the response ended with an intent to do work, but no tool action followed"
    paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    last = paragraphs[-1] if paragraphs else body
    if PLAN_ENDING_RE.search(last) or (len(paragraphs) > 1 and PLAN_ENDING_RE.search(paragraphs[-2]) and re.search(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", last)):
        return True, "the response ended with a plan or next-steps list for work that has not been done"
    return False, ""


def classify_path_kind(path_value: str) -> str:
    path = Path(path_value)
    name = path.name.lower()
    suffix = path.suffix.lower()
    parts = {part.lower() for part in path.parts}
    if suffix in DOC_EXTS or name in {"readme", "readme.md", "agents.md"} or "docs" in parts:
        return "docs"
    if suffix in CODE_EXTS:
        return "code"
    if suffix in CONFIG_EXTS or name.startswith(".env"):
        return "config"
    if suffix in ASSET_EXTS:
        return "assets"
    return "other"


def changed_paths(input_data: dict[str, Any]) -> list[str]:
    tool_name = str(input_data.get("tool_name") or "").lower()
    tool_input = input_data.get("tool_input")
    paths: list[str] = []
    if isinstance(tool_input, dict):
        for key in ("file_path", "path"):
            if tool_input.get(key):
                paths.append(str(tool_input.get(key)))
        paths.extend(PATCH_PATH_RE.findall(str(tool_input.get("command") or "")))
        paths.extend(PATCH_PATH_RE.findall(str(tool_input.get("patch") or "")))
    elif isinstance(tool_input, str):
        paths.extend(PATCH_PATH_RE.findall(tool_input))
    if tool_name in {"apply_patch", "functions.apply_patch"}:
        return paths or ["patch"]
    if tool_name in {"edit", "write"}:
        return paths or ["edit"]
    return [path.strip() for path in paths if path.strip()]


def changed_kinds(input_data: dict[str, Any]) -> list[str]:
    paths = changed_paths(input_data)
    if paths:
        return sorted({classify_path_kind(path) for path in paths})
    return []


def response_text(value: Any, limit: int = 4000) -> str:
    parts: list[str] = []

    def walk(item: Any) -> None:
        if len(" ".join(parts)) > limit:
            return
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            for key in ("stdout", "stderr", "output", "message", "text", "content", "error", "summary"):
                if key in item:
                    walk(item[key])
            if not parts:
                for child in item.values():
                    walk(child)
        elif isinstance(item, list):
            for child in item[:20]:
                walk(child)

    walk(value)
    return redact(" ".join(parts), limit)


def command_from_input(input_data: dict[str, Any]) -> str:
    return tool_input_text(input_data)


def exit_success(input_data: dict[str, Any], text: str) -> bool | None:
    for candidate in (input_data, input_data.get("tool_response")):
        if not isinstance(candidate, dict):
            continue
        for key in ("success", "ok"):
            if isinstance(candidate.get(key), bool):
                return bool(candidate[key])
        for key in ("exit_code", "exitCode", "returncode", "status"):
            value = candidate.get(key)
            if isinstance(value, int):
                return value == 0
            if isinstance(value, str) and value.isdigit():
                return int(value) == 0
            if isinstance(value, str):
                normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
                if normalized in SUCCESS_STATUSES:
                    return True
                if normalized in FAILURE_STATUSES:
                    return False
    if EXIT_ZERO_RE.search(text):
        return True
    if FAILURE_RE.search(text):
        return False
    if SUCCESS_RE.search(text):
        return True
    return None


def is_verification_command(command: str) -> bool:
    return bool(VERIFY_RE.search(command or ""))


def verification_coverage(command: str, changed: list[str]) -> str:
    if not command:
        return "none"
    clean_paths = [path.strip() for path in changed if path and path not in {"patch", "edit"}]
    if clean_paths and any(path in command for path in clean_paths):
        return "direct"
    if DIRECT_TEST_RE.search(command) and re.search(r"(?i)(test|spec|__tests__)", command):
        return "direct"
    if re.search(r"(?i)\b(test|lint|typecheck|tsc|build|check|validate|verify)\b", command):
        return "generic"
    return "uncertain"


def collect_state(input_data: dict[str, Any]) -> dict[str, Any]:
    events = active_events(input_data)
    prompt_events = [event for event in events if event.get("kind") == "prompt_start"]
    mode = str(prompt_events[-1].get("mode") if prompt_events else "quick")
    risks = list(prompt_events[-1].get("risks") if prompt_events else [])
    intent = str(prompt_events[-1].get("intent") or "unknown") if prompt_events else "unknown"
    advisories: list[str] = []
    changed: list[str] = []
    kinds: list[str] = []
    verifications: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    stop_blocks = 0

    for event in events:
        kind = event.get("kind")
        if kind == "risk":
            for flag in event.get("flags") or []:
                if flag not in risks:
                    risks.append(flag)
        elif kind == "advisory":
            for flag in event.get("flags") or []:
                if flag not in advisories:
                    advisories.append(flag)
        elif kind == "change":
            for path in event.get("paths") or []:
                if path not in changed:
                    changed.append(path)
            for value in event.get("kinds") or []:
                if value not in kinds:
                    kinds.append(value)
        elif kind == "verification":
            verifications.append(event)
        elif kind == "failure":
            failures.append(event)
        elif kind == "stop_block":
            stop_blocks += 1

    coverage_order = {"none": 0, "uncertain": 1, "generic": 2, "direct": 3}
    coverage = "none"
    for verification in verifications:
        observed = str(verification.get("coverage_relation") or "uncertain")
        if coverage_order.get(observed, 0) > coverage_order.get(coverage, 0):
            coverage = observed

    return {
        "mode": mode,
        "intent": intent,
        "risks": risks,
        "advisories": advisories,
        "changed_paths": changed,
        "change_kinds": kinds,
        "changed_files_seen": bool(changed or kinds),
        "verification_results": verifications,
        "failures": failures,
        "coverage_relation": coverage,
        "stop_blocks": stop_blocks,
    }


def has_successful_verification(state: dict[str, Any]) -> bool:
    return any(item.get("success") is True for item in state.get("verification_results", []))


def has_any_verification(state: dict[str, Any]) -> bool:
    return bool(state.get("verification_results"))


def docs_only(state: dict[str, Any]) -> bool:
    kinds = set(state.get("change_kinds", []))
    return bool(state.get("changed_files_seen")) and bool(kinds) and kinds <= {"docs"}


def stop_decision(state: dict[str, Any], last_message: str = "") -> tuple[bool, str]:
    mode = state.get("mode") or "quick"
    changed = bool(state.get("changed_files_seen"))
    verified = has_successful_verification(state)
    stop_blocks = int(state.get("stop_blocks") or 0)
    advisories = set(state.get("advisories") or [])

    if stop_blocks >= MAX_STOP_BLOCKS:
        return False, "opus-fable allowed stop after two verification reminders; report the remaining verification gap."
    if mode == "quick":
        return False, ""
    if mode == "blocked":
        return True, "opus-fable: narrow the blocked risk before final response."

    # Fable 5.1 last-paragraph rule applies to any normal/deep turn, docs-only included.
    unfinished, why = unfinished_ending(last_message)
    if unfinished:
        return True, f"opus-fable: {why}. Do that work now with tool calls, or stop only if blocked on user input."

    if docs_only(state):
        return False, ""
    skip_note = " A test-skip edit was observed; justify it or restore the test." if ADVISORY_TEST_SKIP in advisories else ""
    if mode == "deep" and not verified:
        if changed:
            return True, "opus-fable: run the strongest practical verification for the changed behavior before final response." + skip_note
        if not has_any_verification(state):
            return True, "opus-fable: record one observable exit proof, or state why this deep task has no runnable verifier."
    if mode == "normal" and changed and not verified:
        return True, "opus-fable: run one relevant verification command for the changed files, or state why no verifier applies." + skip_note
    return False, ""


def warning_after_max_blocks(state: dict[str, Any]) -> str:
    if int(state.get("stop_blocks") or 0) >= MAX_STOP_BLOCKS and not has_successful_verification(state):
        return "opus-fable: verification evidence is still missing; include that gap in the final report."
    return ""

