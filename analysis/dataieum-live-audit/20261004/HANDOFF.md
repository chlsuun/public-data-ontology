# 데이터이음 운영 점검 인수인계

## 작업 범위

2026-10-04 운영 중인 `https://dataieum.com/`의 화면, 자연어 검색 흐름, 컨테이너 구조와 검색 결과를 점검했다. 점검 중 확인한 복합 지표 완전성 오류에 대해 운영 Luna 이미지 기반의 최소 수정안을 만들었다.

운영 서비스에는 아직 배포하지 않았다. 현재 서비스는 기존 이미지로 정상 실행 중이다.

## 핵심 발견

복합 질문의 의도 추출기는 요청 지표를 여러 `needs`로 정확히 분리한다. 이후 단계는 결합된 의미 검색 결과에서 하나의 지표만 검증되어도 전체 상태를 `results`로 만들 수 있다.

재현 질문:

```text
2015년부터 2024년까지 서울의 청년 인구와 청년 실업률을
연도별로 함께 비교할 수 있는 자료를 찾아줘
```

운영 기록에서 확인한 해석:

- `employment`: 청년 실업률, 서울특별시
- `population`: 청년, 서울특별시
- 공통 기간: 2015~2024년

검색 결과에는 KOSIS 인구 자료만 남았지만 응답 상태는 `results`였다.

## 후보 수정안

수정한 파일:

- `candidate/discovery_harness/similarity_results.py`
- `candidate/discovery_harness/site_search.py`

변경 동작:

- 두 개 이상의 요청 지표가 있는 관련성 판정 결과를 지표별 그룹으로 구성한다.
- 자료가 없는 지표 그룹도 결과에 남긴다.
- 하나라도 비면 `partial`, 모두 채워지면 `results`로 판정한다.
- `retrieval.selection.missing_needs`에 누락 지표를 기록한다.

이 수정안은 지표별 검색 자체를 추가하지 않는다. 거짓 완료 표시를 막는 정확성 수정이다.

## 빌드와 검증

빌드 기준 이미지는 운영 서버에 존재하는 다음 태그다.

```text
dataieum-auth-recovery-luna:20261003
```

후보 디렉터리에서 실행한다.

```bash
docker build -t dataieum-multi-need-completeness:20261004-r1 .
docker run --rm --entrypoint python \
  -v "$PWD/test_multi_need_completeness.py:/tmp/test_multi_need_completeness.py:ro" \
  dataieum-multi-need-completeness:20261004-r1 \
  /tmp/test_multi_need_completeness.py
```

기대 결과:

```text
multi-need completeness tests passed
```

운영 서버에 이미 빌드된 후보 이미지:

```text
tag: dataieum-multi-need-completeness:20261004-r1
id:  sha256:c14ce9924c1fc265046b87373dae8eca1d43666232399a3b0917284fa190426b
```

현재 운영 Luna 이미지:

```text
sha256:023cc3502352c464e445fe293c233eb863538f61e12d0990714b9793f093cf9c
```

## 운영 반영 시 확인할 사항

1. 신규 채팅 작업 수락을 잠시 멈추고 실행 중인 작업이 0인지 확인한다.
2. 기존 릴리스의 Compose 오버라이드 체계를 유지하면서 Luna 이미지만 후보 이미지로 교체한다.
3. Atlas, Luna, Vector의 health 상태가 모두 `healthy`인지 확인한다.
4. 단일 질문 `서울 청년 실업률 자료를 찾아줘`가 기존처럼 결과를 반환하는지 확인한다.
5. 재현 복합 질문이 청년 인구와 고용 그룹을 모두 표시하고, 한쪽이 비면 `partial`인지 확인한다.
6. 문제가 있으면 Luna 이미지만 위 운영 이미지로 되돌린다.

## 후속 구현

다음 단계는 지표별 임베딩과 검색을 수행하고 결과를 하나의 데이터 묶음으로 합치는 것이다. 이후 동일 원자료 중복 제거와 기간·지역·단위·연령정의·라이선스 호환성 검사를 연결해야 한다.

실제 상관분석은 이 호환성 검사를 통과한 관측값 조합에만 실행해야 한다. 메타데이터 관련성 판정만으로 변수 간 관계가 증명되지는 않는다.

## 보안과 데이터 취급

저장소에는 서버 접속 키, API 키, 게이트웨이 토큰, 사용자 채팅 원문 DB와 운영 비밀 파일을 포함하지 않았다. 운영 환경의 인증정보는 기존 서버 마운트와 릴리스 절차를 그대로 사용한다.
