#!/usr/bin/env bash
# Opus-Fable UserPromptSubmit router.
# Injects the smallest matching procedure pack for the current task signal.

set -uo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PACKS="$ROOT/packs"
input="$(cat)"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
printf '%s' "$input" > "$tmp"

python3 - "$PACKS" "$tmp" <<'PY'
import json
import re
import sys

packs = sys.argv[1]
input_path = sys.argv[2]
try:
    with open(input_path, encoding="utf-8") as f:
        payload = json.load(f)
except Exception:
    payload = {}

prompt = payload.get("prompt", "") or ""
low = prompt.lower()
out = []

def has(patterns):
    return any(re.search(p, low, re.I) for p in patterns)

debug = has([
    r"\bdebug\b", r"\bbug\b", r"\berror\b", r"traceback", r"stack trace",
    r"crash", r"failing", r"not working", r"root cause",
    r"버그", r"에러", r"오류", r"실패", r"장애", r"원인", r"안\s*돼", r"안됨",
])
render = has([
    r"html", r"svg", r"canvas", r"chart", r"render", r"website", r"webpage",
    r"\bui\b", r"game", r"browser", r"playwright",
    r"웹", r"화면", r"렌더", r"차트", r"게임", r"브라우저", r"스크린샷",
])
multi = has([
    r"see it through", r"split into goals", r"verify as you go", r"multi[- ]?step",
    r"끝까지", r"나눠서", r"검증하면서", r"완주", r"단계별", r"여러\s*단계",
])
review = has([
    r"\breview\b", r"final check", r"quality gate", r"risk", r"before deploy",
    r"리뷰", r"검토", r"최종\s*점검", r"위험", r"배포\s*전", r"품질\s*게이트",
])
risk = has([
    r"migration", r"delete", r"permission", r"security", r"privacy", r"payment",
    r"마이그레이션", r"삭제", r"권한", r"보안", r"개인정보", r"결제", r"데이터\s*손실",
])

if multi:
    out.append(f"[opus-fable:evidence-gate] Multi-step signal. Use {packs}/evidence-gate.ko.md and scripts/of_goals.py: create -> next -> checkpoint with evidence -> final verification gate.")
if debug:
    out.append(f"[opus-fable:investigation] Debugging signal. Follow {packs}/investigation-protocol.ko.md: reproduce first, form competing hypotheses, gather evidence, trace causal chain, verify before and after.")
if render:
    out.append(f"[opus-fable:grounding] Render/executable artifact signal. Follow {packs}/verification-grounding.ko.md: run it in the real environment, observe output, fix what observation reveals, re-run.")
if review or risk:
    out.append(f"[opus-fable:reviewer-gate] Review/risk signal. Follow {packs}/reviewer-gate.ko.md: inspect requirements, facts, unexplained clues, unsafe actions, verification gaps, and materially better alternatives.")

if out:
    print("\n".join(out))
PY

exit 0
