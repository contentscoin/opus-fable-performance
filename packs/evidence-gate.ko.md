# Evidence Gate

멀티스텝 작업에서는 "완료"를 말하기 전에 각 단계의 증거를 남긴다. 마지막 단계는 검증 명령과 검증 결과가 있어야 완료할 수 있다.

## 언제 사용하나

- 2개 이상의 순차 story가 있는 작업.
- 구현, 문서, 검증이 분리되는 작업.
- 재시작 후에도 진행 상태를 이어야 하는 작업.
- 사용자가 "끝까지", "검증하면서", "나눠서", "완주"를 요구한 작업.

## 권장 명령

repo root에서 실행한다.

```bash
python scripts/of_goals.py create --brief "<작업 요약>" \
  --goal "분석::요구사항과 위험을 정리한다" \
  --goal "구현::변경을 적용한다" \
  --goal "검증::테스트와 관찰 결과를 확인한다"

python scripts/of_goals.py next
python scripts/of_goals.py checkpoint --id G001 --status complete --evidence "<증거>"
python scripts/of_goals.py status
```

마지막 goal은 검증 gate다. 완료하려면 다음 인자가 필요하다.

```bash
python scripts/of_goals.py checkpoint --id G003 --status complete \
  --evidence "<검증 요약>" \
  --verify-cmd "<실행한 명령>" \
  --verify-evidence "<명령 결과 또는 관찰 결과>"
```

## 규칙

- `complete`에는 비어 있지 않은 evidence가 필요하다.
- final goal에는 `--verify-cmd`와 `--verify-evidence`가 필요하다.
- 막히면 `blocked`로 기록하고, 필요한 입력이나 외부 상태를 명시한다.

