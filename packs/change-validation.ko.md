# Change Validation

commit, push, 배포, PR 생성처럼 변경이 밖으로 나가기 전에 적용한다. CI를 빨갛게 만드는 push는 한 사이클과 리뷰어의 신뢰를 비용으로 치른다. 한 번의 검증된 push가 세 번의 추측성 push보다 낫다.

## push 전에 증명한다

1. 저장소의 빠른 검사를 직접 돌린다. lint, format, typecheck, 변경한 패키지의 unit test처럼 기여자가 로컬에서 돌리는 것.
2. CI 수정이라면 먼저 원래 실패를 재현하고, 같은 검사가 통과하는 것을 보인다. 재현 없는 수정은 추측이다.
3. 자기 diff를 적대적으로 다시 읽는다. "CI가 이 변경을 거부한다면 어디서?" 찾은 것은 push 전에 고친다.
4. 수정은 최소로 유지한다. 실패나 코멘트가 요구하는 것만. 스스로 PR을 넓히지 않는다.
5. 모든 것이 깨끗하게 돌아온 뒤에만 push한다.

## 절대 규칙

- 테스트를 skip, disable, quarantine해서 green을 만들지 않는다. `@skip`, `it.skip`, `xit`, `#[ignore]`, `[skip ci]`는 근본 원인 수정이 아니다. 사용자가 명시적으로 요청한 경우에만 하고, 최종 보고에 밝힌다.
- `.only`, `fit`, `fdescribe`처럼 테스트를 좁히는 마커를 남기지 않는다.
- `--no-verify`로 hook을 우회하지 않는다. 실패한 검사를 고친다.
- CI를 다시 돌리려고 빈 commit을 만들거나 PR을 닫았다 열지 않는다.
- 다른 사람의 브랜치에서 history를 다시 쓰지 않는다. rebase, amend, force-push 금지. merge commit이 상대의 checkout을 유지한다. 자기가 만든 브랜치에서는 저장소 관례를 따른다.
- lockfile과 생성 파일은 저장소 도구로 재생성한다. 손으로 고치지 않는다.

## 상태를 바꾸는 명령 전에

restart, delete, config 수정, 파일 덮어쓰기, `git checkout --`, `git restore`, `git stash drop`, `docker rm`, `kubectl delete`처럼 시스템 상태를 바꾸는 명령 전에:

- 관찰된 증거가 **그 특정 행동**을 지지하는지 확인한다. 알려진 실패와 패턴이 비슷한 신호는 다른 원인일 수 있다.
- 삭제하거나 덮어쓰기 전에 대상을 본다. 설명과 다르거나, 자기가 만든 것이 아니면 진행하지 말고 그 사실을 보고한다.
- 되돌릴 수 없거나 외부로 나가는 행동은 durably 허가되지 않았다면 먼저 확인한다.

## 외부 전송

외부 서비스로 내용을 보내는 것은 공개다. 나중에 삭제해도 캐시되거나 색인될 수 있다. 사용자 이메일, 비밀값, 내부 호스트명은 요청되지 않았다면 요청 헤더, URL, payload, PR 본문, commit 메시지에 넣지 않는다. 비밀값이 관련되면 값을 복사하지 말고 위치를 말한다.

## hook 연동

`hooks/codex/pre_tool_use.py`는 다음 상황에서 차단하지 않고 컨텍스트를 주입한다.

| 신호 | 주입 내용 |
|---|---|
| 이 턴에 파일 변경이 있고 성공한 검증이 없는데 `git push` | push gate: 빠른 검사 먼저 |
| `--force`, `rebase`, `--amend` | history 재작성 경고 |
| `--no-verify` | hook 우회 경고 |
| `--allow-empty` | 빈 commit 경고 |
| 상태 변경 명령 | evidence-before-action 경고 |
| 테스트 skip/only 마커가 담긴 편집 | test-skip 경고, Stop 시점에 정당화 요구 |

push 자체는 막지 않는다. 사용자가 명시적으로 요청한 정상 경로일 수 있기 때문이다.
