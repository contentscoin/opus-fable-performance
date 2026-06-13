# Opus Fable Performance

`opus-fable-performance`는 Opus를 **가성비 모델처럼 아껴 쓰기 위한 레이어가 아니라**, Opus가 가진 추론력과 검증 능력을 최대한 끌어내기 위한 **최고 성능 운영 레이어**입니다.

이 저장소는 `itsinseong/value-for-fable`의 문제의식에서 출발했지만 목표가 다릅니다. 원래 VFF(Value-for-Fable)는 “Sonnet을 Fable처럼 운용해서 비용 대비 품질을 높일 수 있는가?”에 답하려는 프로젝트입니다. 반면 이 저장소는 “이미 강력한 Opus가 얕게 멈추거나, 그럴듯한 답에서 조기 종료하거나, 검증 없이 결론을 내리는 것을 막고 최고 품질로 운용할 수 있는가?”에 답하기 위해 만들었습니다.

## 핵심 결론

Opus에는 VFF를 그대로 붙이면 안 됩니다. VFF의 비용 절약, 출력 압축, 간결성 우선 규칙은 Sonnet에는 유용하지만 Opus의 장점인 깊은 탐색과 대안 비교를 제한할 수 있습니다. 그래서 이 저장소는 VFF의 뼈대 중 좋은 부분만 가져오고, 목적함수를 완전히 바꿉니다.

```text
Sonnet-VFF: 낮은 비용으로 Fable식 행동 패턴을 흉내낸다.
Opus-Fable: 비용보다 정확도, 깊이, 검증, 의사결정 품질을 우선한다.
```

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
│   └── opus-reminder.sh         # 긴 세션에서 운영 규칙을 다시 상기
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
└── scripts/
    └── validate_repo.py         # 구조 검증 스크립트
```

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
- `elder-plinius/CL4R1T4S/ANTHROPIC/CLAUDE-FABLE-5.md`: VFF README가 Fable 5 운영 구조 원본으로 명시한 공개 자료입니다.
- Claude Code와 Codex 공식 문서: 플러그인, 스킬, output style, hooks, AGENTS.md, Codex skill 구조를 확인하는 데 사용했습니다.

자세한 분석은 `docs/research.md`에 정리했습니다.

## 검증

현재 repo는 아래 검증을 통과하도록 구성했습니다.

```bash
python scripts/validate_repo.py
python C:/Users/USER/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/opus-fable
python C:/Users/USER/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

검증 대상은 필수 파일 존재, JSON 문법, skill frontmatter, JSONL 벤치마크 파일, Codex 플러그인 manifest 구조입니다.

## 한 줄 요약

Opus-Fable은 Opus를 짧고 싸게 쓰기 위한 프롬프트가 아니라, **중요한 문제에서 Opus가 더 깊게 보고, 더 정확히 비교하고, 더 강하게 검증하게 만드는 성능 운영체계**입니다.

