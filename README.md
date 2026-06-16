# Opus Fable Performance

`opus-fable-performance`는 Opus를 **가성비 모델처럼 아껴 쓰기 위한 레이어가 아니라**, Opus가 가진 추론력과 검증 능력을 최대한 끌어내기 위한 **최고 성능 운영 레이어**입니다.

이 저장소는 `itsinseong/value-for-fable`의 문제의식에서 출발했지만 목표가 다릅니다. 원래 VFF(Value-for-Fable)는 “Sonnet을 Fable처럼 운용해서 비용 대비 품질을 높일 수 있는가?”에 답하려는 프로젝트입니다. 반면 이 저장소는 “이미 강력한 Opus가 얕게 멈추거나, 그럴듯한 답에서 조기 종료하거나, 검증 없이 결론을 내리는 것을 막고 최고 품질로 운용할 수 있는가?”에 답하기 위해 만들었습니다.

## 핵심 결론

Opus에는 VFF를 그대로 붙이면 안 됩니다. VFF의 비용 절약, 출력 압축, 간결성 우선 규칙은 Sonnet에는 유용하지만 Opus의 장점인 깊은 탐색과 대안 비교를 제한할 수 있습니다. 그래서 이 저장소는 VFF의 뼈대 중 좋은 부분만 가져오고, 목적함수를 완전히 바꿉니다.

```text
Sonnet-VFF: 낮은 비용으로 Fable식 행동 패턴을 흉내낸다.
Opus-Fable: 비용보다 정확도, 깊이, 검증, 의사결정 품질을 우선한다.
```

v0.2부터는 여기에 `fablize`에서 배운 절차형 harness 관점을 더했습니다. 즉, 좋은 말을 더 많이 넣는 프롬프트가 아니라 **작업별 router, evidence gate, 실행/렌더 검증, 조기 종료 방지**를 갖춘 운영 장치로 확장했습니다.

## 무엇을 해결하나

대형 모델도 실제 작업에서는 자주 얕게 끝납니다. 예를 들어 간헐적 500 오류를 보고도 “DB 연결 문제, 메모리 부족, 코드 버그”처럼 후보를 동급으로 나열하거나, 아키텍처 결정에서 진짜 tradeoff를 비교하지 않고 한 방향을 추천하거나, 코드 수정 후 테스트 없이 “완료”라고 말할 수 있습니다.

Opus-Fable은 이런 실패를 막는 운영 규칙을 주입합니다.

- 첫 문장에서 결론, 발견, 추천 행동을 말합니다.
- 흔한 원인보다 **관찰된 단서를 모두 설명하는 가설**을 우선합니다.
- 고치기 전에 원인 후보를 갈라낼 **결정적 측정 지점**을 먼저 잡습니다.
- 아키텍처·전략 문제에서는 진짜 후보군을 비교하고, 추천을 가르는 tradeoff를 밝힙니다.
- 코드 작업에서는 읽고, 좁게 고치고, 가능한 가장 강한 검증을 실행합니다.
- 현재성이 중요한 사실은 공식 문서나 1차 출처로 확인합니다.
- 최종 답변에는 결론, 근거, caveat, 검증 결과를 포함합니다.

## 저장소 구성

```text
opus-fable-performance/
├── .claude-plugin/
│   ├── plugin.json              # Claude Code 플러그인 메타데이터
│   └── marketplace.json         # Claude Code 로컬 마켓플레이스 예시
├── .codex-plugin/
│   └── plugin.json              # Codex 플러그인 메타데이터
├── skills/opus-fable/
│   └── SKILL.md                 # Claude Code용 Opus-Fable 스킬
├── agents/
│   └── opus-reviewer.md         # Opus 리뷰어 서브에이전트
├── output-styles/
│   └── opus-fable.md            # Claude Code 상시 Output Style
├── hooks/
│   ├── hooks.json               # Claude Code 훅 연결
│   ├── router.sh                # 작업 신호별 절차 pack 자동 주입
│   ├── finish-the-work.sh       # opt-in 조기 종료 방지 Stop hook
│   └── opus-reminder.sh         # 긴 세션에서 운영 규칙을 다시 상기
├── packs/
│   ├── investigation-protocol.ko.md
│   ├── verification-grounding.ko.md
│   ├── evidence-gate.ko.md
│   ├── reviewer-gate.ko.md
│   └── capability-escalation.ko.md
├── scripts/
│   ├── of_goals.py              # evidence gate용 goal ledger
│   └── validate_repo.py
├── setup/
│   ├── install-codex.ps1
│   ├── install-claude.sh
│   ├── enable-strict-stop.sh
│   └── disable-strict-stop.sh
├── .agents/skills/opus-fable/
│   └── SKILL.md                 # Codex용 standalone skill
├── codex/
│   └── AGENTS.opus-fable.md     # Codex AGENTS.md에 넣을 운영 규칙
├── docs/
│   ├── research.md              # 원본 분석과 설계 판단
│   ├── routing.md               # Sonnet/Codex/Opus 라우팅 기준
│   └── evaluation.md            # 성능 평가 방법
├── evals/
│   ├── tasks.jsonl              # 벤치마크 seed task
│   └── rubric.md                # 평가 루브릭
```

## v0.2에서 추가된 절차형 harness

### 1. 작업별 Router

`hooks/router.sh`는 Claude Code의 `UserPromptSubmit` 시점에서 사용자의 요청을 보고 필요한 절차만 주입합니다. 예를 들어 “버그”, “오류”, “failing”이 있으면 조사 프로토콜을, “HTML”, “SVG”, “UI”, “화면”이 있으면 렌더/실행 검증 pack을 넣습니다.

핵심은 모든 규칙을 항상 넣지 않는 것입니다. 작은 작업에는 baseline만 두고, 신호가 있는 작업에만 가장 작은 matching discipline을 적용합니다.

### 2. Evidence Gate

`scripts/of_goals.py`는 멀티스텝 작업을 `.opus-fable/`에 기록합니다. 각 단계는 evidence 없이는 `complete`가 될 수 없고, 마지막 단계는 `--verify-cmd`와 `--verify-evidence` 없이는 완료할 수 없습니다.

예시:

```bash
python scripts/of_goals.py create --brief "Opus-Fable v0.2 업그레이드" \
  --goal "설계::fablize에서 이식할 절차를 정한다" \
  --goal "구현::router와 evidence gate를 추가한다" \
  --goal "검증::validator와 smoke test를 실행한다"

python scripts/of_goals.py next
python scripts/of_goals.py checkpoint --id G001 --status complete --evidence "라우팅/게이트/훅 범위 확정"
```

### 3. Render/Executable Verification

`packs/verification-grounding.ko.md`는 화면, SVG, UI, 게임, 차트, 실행 스크립트처럼 실제 결과를 봐야 맞는 산출물에 적용합니다. 정적 문법 검사만으로는 “보인다/동작한다”를 증명할 수 없으므로, 실제 renderer나 실행 환경에서 관찰해야 합니다.

### 4. Optional Strict Stop

`hooks/finish-the-work.sh`는 조기 종료 방지용 Stop hook입니다. 다만 false positive 가능성이 있어 기본값은 opt-in입니다. 프로젝트에서 사용하려면 다음을 실행합니다.

```bash
bash setup/enable-strict-stop.sh
```

끄려면:

```bash
bash setup/disable-strict-stop.sh
```

## v0.3에서 추가된 Codex-native evidence hook

v0.3은 `Pandoll-AI/fable-ish-codex`를 참고해 Codex 플러그인 생명주기 훅을 보강한 버전입니다. 핵심 아이디어는 “좋은 지침을 적어두는 것”에서 한 걸음 더 나아가, Codex가 실제 작업 중 남긴 변경, 실패, 검증 명령을 hook이 관찰하고 Stop 시점에 완료 조건을 다시 확인하게 만드는 것입니다.

다만 `fable-ish-codex`를 그대로 복사하지 않았습니다. 참고 레포의 단일 JSON ledger 방식은 Windows 동시 `PostToolUse` 상황에서 파일 교체 충돌이 날 수 있음을 확인했기 때문에, Opus-Fable v0.3은 **event journal 방식**을 사용합니다. 각 hook 실행이 고유한 JSON 이벤트 파일을 만들고, Stop hook은 마지막 사용자 프롬프트 이후의 이벤트만 모아 상태를 계산합니다. 이 방식은 여러 tool 결과가 거의 동시에 기록되어도 같은 파일을 덮어쓰지 않습니다.

새로 추가된 구성은 다음과 같습니다.

```text
hooks/codex/user_prompt_submit.py  # 요청을 quick/normal/deep/blocked로 분류
hooks/codex/pre_tool_use.py        # 좁은 범위의 파괴적 로컬 명령만 차단
hooks/codex/post_tool_use.py       # 변경 파일, 검증 명령, 실패 신호를 이벤트로 기록
hooks/codex/stop_gate.py           # normal/deep 작업의 검증 누락을 Stop 시점에 확인
scripts/of_hook_core.py            # 분류, redaction, event journal, Stop 판정 공통 로직
tests/test_codex_hooks.py          # hook wire shape, 한국어 분류, Windows 동시 기록 테스트
```

차단 정책은 의도적으로 좁습니다. `git push`, Vercel/Netlify/Firebase 배포, DB push, package publish, migration deploy, infra apply/up은 사용자가 명시적으로 요청하는 정상 실행 경로일 수 있으므로 자동 차단하지 않습니다. 대신 `rm -rf`, `git reset --hard`, `git clean -f`, `terraform destroy`, `pulumi destroy`, secret 파일 patch, 대량 delete patch처럼 되돌리기 어렵거나 범위가 위험한 작업만 막습니다.

Stop hook은 다음 기준으로 동작합니다.

- `quick`: 검증을 강제하지 않습니다.
- `normal`: 파일 변경이 있으면 관련 검증 1개가 필요합니다.
- `deep`: 배포, 인증, 보안, DB, 마이그레이션, 최고 성능 작업처럼 위험도가 높으면 관찰 가능한 exit proof가 필요합니다.
- `blocked`: 위험 범위를 좁히기 전에는 진행하지 않습니다.

무한 continuation을 막기 위해 Stop block은 최대 2회만 발생합니다. 그 이후에도 검증이 부족하면 최종 보고에 검증 공백을 밝히도록 경고만 남깁니다.

## 옮길 수 있는 것과 없는 것

`fablize`에서 특히 중요한 통찰은 “하네스는 모델의 천장을 올리지 못한다”는 점입니다. Opus-Fable도 이 경계를 지킵니다.

| 구분 | Opus-Fable에서 다루는 방식 |
|---|---|
| 검증 절차 | 실행, 렌더, 테스트, 로그 확인을 완료 조건으로 묶는다 |
| 멀티스텝 완주 | goal ledger와 evidence gate로 완료를 증거에 연결한다 |
| 체계적 조사 | 재현, 경쟁 가설, 증거 수집, 인과사슬 추적을 강제한다 |
| 조기 종료 | opt-in Stop hook으로 “하겠다”만 하고 멈추는 것을 막는다 |
| 모델 고유 발견력 | 절차로 흉내내지 않고 에스컬레이션 기준으로 다룬다 |
| 열린 창작 디테일 | 모델 선택 또는 사람 검토 영역으로 남긴다 |

## 적용 방식 1: Claude Code에서 사용

Claude Code에서는 세 가지 방식으로 사용할 수 있습니다.

첫 번째는 Output Style입니다. `/config -> Output style -> Opus-Fable`을 선택하면 모든 세션에서 Opus-Fable 규칙이 상시 적용됩니다. Opus를 주로 쓰고, 답변 품질과 검증 태도를 항상 올리고 싶을 때 가장 자연스럽습니다.

두 번째는 스킬입니다. 특정 세션이나 특정 작업에서만 `opus-fable` 스킬을 발동해 깊은 진단, 아키텍처 판단, 고위험 리뷰에 적용합니다.

세 번째는 `opus-reviewer` 에이전트입니다. Sonnet, Codex, 또는 일반 Opus가 만든 초안이 있을 때 최종 품질 게이트로 사용합니다. 이 에이전트는 글 전체를 다시 쓰는 역할이 아니라, 놓친 요구사항, 틀린 사실, 설명 안 된 단서, 위험한 추천, 약한 검증, 더 나은 대안을 찾는 역할입니다.

수동 복사 예시는 다음과 같습니다.

```bash
mkdir -p ~/.claude/skills/opus-fable ~/.claude/agents ~/.claude/output-styles ~/.claude/hooks
cp skills/opus-fable/SKILL.md ~/.claude/skills/opus-fable/SKILL.md
cp agents/opus-reviewer.md ~/.claude/agents/opus-reviewer.md
cp output-styles/opus-fable.md ~/.claude/output-styles/opus-fable.md
cp hooks/opus-reminder.sh ~/.claude/hooks/opus-reminder.sh
cp hooks/router.sh ~/.claude/hooks/router.sh
cp hooks/finish-the-work.sh ~/.claude/hooks/finish-the-work.sh
chmod +x ~/.claude/hooks/opus-reminder.sh
```

## 적용 방식 2: Codex에서 사용

Codex에는 두 층으로 적용하는 것을 권장합니다.

전역 `AGENTS.md`에는 짧은 운영 규칙만 넣습니다. 전역 파일이 너무 길면 모든 작업에 불필요한 지시가 들어가고, 작은 작업에서도 과도하게 무거워질 수 있습니다.

프로젝트나 중요한 작업에는 `.agents/skills/opus-fable/`을 넣고 `$opus-fable` 스킬로 호출합니다. 이 방식은 필요한 때만 전체 지침을 로드하므로 더 깔끔합니다.

프로젝트 적용 예시는 다음과 같습니다.

```bash
mkdir -p .agents/skills
cp -r /absolute/path/to/opus-fable-performance/.agents/skills/opus-fable .agents/skills/
cp /absolute/path/to/opus-fable-performance/codex/AGENTS.opus-fable.md AGENTS.md
```

PowerShell 설치 스크립트도 포함했습니다.

```powershell
.\setup\install-codex.ps1          # 현재 프로젝트에 설치
.\setup\install-codex.ps1 -Global  # 전역 Codex skill로 설치
```

## 언제 Opus-Fable을 직접 쓰나

다음 작업은 Opus-Fable을 처음부터 켜는 것이 좋습니다.

- 원인이 애매한 장애 진단
- 간헐적 오류, race condition, async/event loop, 분산 시스템 문제
- 보안·권한·개인정보·금융·데이터 손실 위험이 있는 변경
- 되돌리기 어려운 아키텍처 결정
- 최신 API, 가격, 정책, 모델 정보가 필요한 리서치
- 배포, 마이그레이션, 공개 문서, 고객 전달 전 최종 리뷰

## 언제 Sonnet/Codex 먼저 쓰나

모든 작업을 Opus-Fable로 시작할 필요는 없습니다. 구현 경로가 명확하거나, 문서 정리·단순 리팩토링·반복 작업처럼 실행량이 중요할 때는 Codex나 Sonnet으로 먼저 처리하고, 마지막에 Opus 리뷰어를 붙이는 방식이 좋습니다.

추천 라우팅은 다음과 같습니다.

```text
일반 구현/정리:
Codex 또는 Sonnet -> 테스트 -> 필요 시 Opus Reviewer

복잡한 진단/아키텍처:
Opus-Fable 직접 사용 -> 결정적 검증 -> 결론

고위험 변경:
Codex/Sonnet 초안 -> Opus Reviewer -> 수정 -> 검증
```

## 원본과의 관계

이 저장소는 `itsinseong/value-for-fable`의 fork가 아니며, 해당 저장소의 구현 파일을 복사하지 않았습니다. GitHub API로 확인했을 때 `itsinseong/value-for-fable` 자체도 GitHub fork로 표시되지 않았습니다.

다만 아이디어의 출처 체인은 명확히 기록합니다.

- `itsinseong/value-for-fable`: Sonnet에 Fable식 운영 구조를 입혀 비용 대비 품질을 높이는 프로젝트입니다.
- `fivetaku/fablize`: Opus가 작업을 끝까지 수행하도록 completion, evidence, verification을 절차로 강제하는 Claude Code plugin입니다.
- `elder-plinius/CL4R1T4S/ANTHROPIC/CLAUDE-FABLE-5.md`: VFF README가 Fable 5 운영 구조 원본으로 명시한 공개 자료입니다.
- Claude Code와 Codex 공식 문서: 플러그인, 스킬, output style, hooks, AGENTS.md, Codex skill 구조를 확인하는 데 사용했습니다.

자세한 분석은 `docs/research.md`에 정리했습니다.

## 검증

현재 repo는 아래 검증을 통과하도록 구성했습니다.

```bash
python scripts/validate_repo.py
python -m json.tool .codex-plugin/plugin.json
python -m json.tool hooks/hooks.json
python -m py_compile hooks/codex/*.py scripts/*.py tests/*.py
python -m unittest discover -s tests
python scripts/of_goals.py create --brief "smoke" --goal "work::do one thing" --goal "verify::verify result" --force
python C:/Users/USER/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/opus-fable
python C:/Users/USER/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

검증 대상은 필수 파일 존재, JSON 문법, skill frontmatter, JSONL 벤치마크 파일, Codex 플러그인 manifest 구조, Python hook 문법, hook 동작 계약, Windows-safe event journal 동시성입니다.

## 한 줄 요약

Opus-Fable은 Opus를 짧고 싸게 쓰기 위한 프롬프트가 아니라, **중요한 문제에서 Opus가 더 깊게 보고, 더 정확히 비교하고, 더 강하게 검증하게 만드는 성능 운영체계**입니다.
