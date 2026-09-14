# v0.4 검토·QA 작업 준비

전체 흐름과 담당 업무는 [과정 확충안](../../docs/process-v0.4.md)에 있다. 기존 v0.3 탐색 데모에서 다음 개발 단계로 넘어가기 위한 규칙·양식·검토 대기열이다.

실제 관계부터 살펴보려면 [관계 31개 검토표](../../docs/relations-review.md)를 연다. 각 행에 원본 모델의 관계 ID·위치, 사람이 읽을 이름, 근거와 검토할 내용이 연결되어 있다.

| 파일 | 용도 |
|---|---|
| [workflow-policy.json](workflow-policy.json) | 관계 승인 상태, 검토 요건, 버전 변경, 커뮤니티·제공 정책 |
| [qa-policy.json](qa-policy.json) | 네 사이트별 검사 항목, 네 축의 점수 산식·가중치·미평가 처리 |
| [record-templates.json](record-templates.json) | 사람의 관계 검토, QA, 분석 실행, 제공 계획의 빈 양식 |
| [review-workspace.json](review-workspace.json) | 기존 관계 31개와 자료 6개에서 생성한 검토 작업 목록 |
| [score_qa.py](score_qa.py) | 입력된 측정값의 산식 계산. 수집·진위 검증·권한 승인은 수행하지 않음 |
| [validate.py](validate.py) | 미평가, 잘못된 분모, 최신성 미적용, 기존 근거 상태 보존 등 검증 |

```bash
python ontology-prototype/governance/build_workspace.py
python ontology-prototype/governance/validate.py
```

Python 표준 라이브러리만 사용하고 외부 요청은 하지 않는다. `review-workspace.json`은 재생성되는 준비 파일이다. 사람의 검토 원장을 덮어쓰는 도구가 아니며 운영 DB를 갱신하지 않는다.

실제 승인 기록은 0건이다. `documented` 10개·`curated` 12개·`candidate` 9개의 기존 근거 상태를 유지한다. 원본 관측값을 검사하지 않았으므로 6개 QA 기록의 점수는 모두 `null`이다. 검증 코드의 합성 숫자는 산식 검사 전용이며 실제 자료 평가로 저장하지 않는다.

다음 구현은 인증된 검토자 권한과 승인 원장, 사이트별 원본 검사기, 승인된 관계만 내보내는 생성기다. 기존 [v0.3 model.json](../discovery-platform/model.json)과 공유 그래프는 후보를 포함한 데모이며 이 새 승인 절차를 통과한 운영 그래프로 표시하면 안 된다.
