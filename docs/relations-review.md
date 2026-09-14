# model.json 관계 검토표

기준: v0.3.0 / 총 31개 관계. [원본 모델](../ontology-prototype/discovery-platform/model.json#L557)의 ID를 사람이 읽을 이름으로 풀어 쓴 목록이다.

상태: 후보 9개 · 편집 정의 12개 · 공식 설명 근거 10개. 이 상태는 새 사람 승인 절차의 완료 표시가 아니다.

이 표는 검토 대상을 정하는 읽기용 생성 파일이다. 검토 결론은 [검토 기록 양식](../ontology-prototype/governance/record-templates.json)에 별도로 남긴다. 다시 생성하면 이 표의 직접 수정 내용은 보존되지 않는다.

## 읽는 방법

1. 연결된 두 개체와 관계 종류를 확인한다.
2. ‘함께 탐색’, ‘해당 지표 제공’, ‘같은 자료로 결합’, ‘통계적 연관’ 중 무엇을 주장하는지 구분한다.
3. 관계 ID로 원본 위치를 열고 근거·자료 조건을 확인한다.
4. 출처 확인, 실제 계열 검사 또는 별도 분석 중 필요한 작업을 정한다.
5. 검토자·날짜·근거·적용 범위와 승인/수정 요청/기각 결정을 별도 기록한다.

현재 모델에는 실측 상관계수나 확정 인과관계가 없다. 아래 가설을 상관분석 대상으로 쓰려면 먼저 분석 질문과 입력 자료를 구체화해야 한다.

## 함께 탐색할 맥락 가설 — 5개

함께 찾아볼 관련성이 있다는 제안.

검토: 해당 맥락을 연결할 문헌·공식 설명 또는 적용 사례를 확인한다. 통계적 연관성을 주장하려면 변수·지역·기간·연령을 정한 별도 분석이 필요하다.

| 관계 ID · 원본 위치 | 연결 | 기존 근거 상태 | 현재 주의점 | 근거 |
|---|---|---|---|---|
| [r-ec83f4db154f](../ontology-prototype/discovery-platform/model.json#L610) | 인구이동 → 고용 | 후보 | 통계적 상관·인과관계를 검증한 연결이 아님 | [user-requirements](#evidence-user-requirements) |
| [r-7d5a01a773ed](../ontology-prototype/discovery-platform/model.json#L627) | 인구이동 → 주거 | 후보 | 통계적 상관·인과관계를 검증한 연결이 아님 | [user-requirements](#evidence-user-requirements) |
| [r-f6292fc89b0e](../ontology-prototype/discovery-platform/model.json#L644) | 인구이동 → 교육·진로 | 후보 | 통계적 상관·인과관계를 검증한 연결이 아님 | [user-requirements](#evidence-user-requirements) |
| [r-01721876a9a8](../ontology-prototype/discovery-platform/model.json#L661) | 고용 → 교육·진로 | 후보 | 관계 유형에 맞게 위 검토 항목을 확인 | [user-requirements](#evidence-user-requirements) |
| [r-7d4da1c5592e](../ontology-prototype/discovery-platform/model.json#L678) | 교육·진로 → 고용 | 후보 | 관계 유형에 맞게 위 검토 항목을 확인 | [user-requirements](#evidence-user-requirements) |

## 지표와 실제 자료의 대응 — 8개

이 자료에서 해당 지표를 찾을 수 있다는 연결.

검토: 실제 표/API에서 항목 코드·연령·지역·기간·단위를 확인한다. 원문 설명만 확인한 상태와 필요한 계열을 조회한 상태를 구분한다.

| 관계 ID · 원본 위치 | 연결 | 기존 근거 상태 | 현재 주의점 | 근거 |
|---|---|---|---|---|
| [r-442b5ce5e8f0](../ontology-prototype/discovery-platform/model.json#L848) | 전입자수 → KOSIS 이동자수 | 후보 | 자료 설명·목록 수준의 대응. 필요한 하위계열 선택과 결합은 별도 검증. 원본 통계표 직접 조회·전체 기간·코드·단위 미검증 / 연령구간과 행정구역 버전을 확인해야 결합 가능 | [kosis-migration](#evidence-kosis-migration) · [kosis-table-access](#evidence-kosis-table-access) |
| [r-d4546e8dce56](../ontology-prototype/discovery-platform/model.json#L866) | 전출자수 → KOSIS 이동자수 | 후보 | 자료 설명·목록 수준의 대응. 필요한 하위계열 선택과 결합은 별도 검증. 원본 통계표 직접 조회·전체 기간·코드·단위 미검증 / 연령구간과 행정구역 버전을 확인해야 결합 가능 | [kosis-migration](#evidence-kosis-migration) · [kosis-table-access](#evidence-kosis-table-access) |
| [r-393db8c3cac1](../ontology-prototype/discovery-platform/model.json#L884) | 순이동자수 → KOSIS 순이동 | 공식 설명 근거 있음 | 자료 설명·목록 수준의 대응. 필요한 하위계열 선택과 결합은 별도 검증. 원본 통계표 직접 조회·전체 기간·코드·단위 미검증 / 연령구간과 행정구역 버전을 확인해야 결합 가능 | [kosis-migration](#evidence-kosis-migration) · [kosis-table-access](#evidence-kosis-table-access) |
| [r-bff6a37d9e3b](../ontology-prototype/discovery-platform/model.json#L902) | 청년 실업률 → WB 청년 실업률 | 공식 설명 근거 있음 | 자료 설명·목록 수준의 대응. 필요한 하위계열 선택과 결합은 별도 검증. 국가별 제공 기간·빈도·관측값 응답 구조 미검증 / 국내 시군구 이동 통계와 직접 결합할 수 없음 / 국가 추정치·연령 정의·집계 방법의 차이를 확인해야 함 | [wb-unemployment](#evidence-wb-unemployment) |
| [r-c6da93d847f8](../ontology-prototype/discovery-platform/model.json#L919) | 청년 실업률 → OECD 실업 통계 | 후보 | 자료 설명·목록 수준의 대응. 필요한 하위계열 선택과 결합은 별도 검증. 대상은 JavaScript 화면만 확인. 링크의 기본 연령 필터 Y_GE15는 청년 15~24세 조건과 같지 않으므로 청년 하위계열 선택을 별도 검증해야 함. / 원본 관측값·국가별 범위·결합 조건 미검증 | [oecd-unemployment-web](#evidence-oecd-unemployment-web) |
| [r-f6448e7d3459](../ontology-prototype/discovery-platform/model.json#L936) | 청년 고용률 → WB 청년 고용률 | 공식 설명 근거 있음 | 자료 설명·목록 수준의 대응. 필요한 하위계열 선택과 결합은 별도 검증. 국가별 제공 기간·빈도·관측값 응답 구조 미검증 / 국내 시군구 이동 통계와 직접 결합할 수 없음 / 국가 추정치·연령 정의·집계 방법의 차이를 확인해야 함 | [wb-employment](#evidence-wb-employment) |
| [r-8ccbfb4143bc](../ontology-prototype/discovery-platform/model.json#L953) | 주택가격지수 → OECD 주택가격 | 공식 설명 근거 있음 | 자료 설명·목록 수준의 대응. 필요한 하위계열 선택과 결합은 별도 검증. 기본 링크는 실질 주택가격 RHP 선택. 임대료 지수 계열의 제공 위치·코드·기간은 추가 검증. 특정 도시의 원화 월세 금액 자료가 아님. / 원본 관측값·국가별 범위·결합 조건 미검증 | [oecd-housing-web](#evidence-oecd-housing-web) |
| [r-77d3d2b11c2c](../ontology-prototype/discovery-platform/model.json#L970) | 임대료 지수 → OECD 주택가격 | 후보 | 자료 설명·목록 수준의 대응. 필요한 하위계열 선택과 결합은 별도 검증. 기본 링크는 실질 주택가격 RHP 선택. 임대료 지수 계열의 제공 위치·코드·기간은 추가 검증. 특정 도시의 원화 월세 금액 자료가 아님. / 원본 관측값·국가별 범위·결합 조건 미검증 | [oecd-housing-web](#evidence-oecd-housing-web) |

## 개념과 측정 지표 — 9개

이 개념을 살펴볼 지표라는 편집 정의.

검토: 공식 지표 정의·산식·분모·단위·대상 범위를 확인한다. 이 관계만으로 해당 자료가 확보됐다고 판단하지 않는다.

| 관계 ID · 원본 위치 | 연결 | 기존 근거 상태 | 현재 주의점 | 근거 |
|---|---|---|---|---|
| [r-fdc5c86c04c3](../ontology-prototype/discovery-platform/model.json#L695) | 인구이동 → 전입자수 | 편집 정의 | 지역·연령·집계 기간의 경계 정의 필요 | [user-requirements](#evidence-user-requirements) |
| [r-2a6e492fd0b4](../ontology-prototype/discovery-platform/model.json#L712) | 인구이동 → 전출자수 | 편집 정의 | 청년 정의와 이동의 범위·중복 산정 기준 확인 필요 | [user-requirements](#evidence-user-requirements) |
| [r-7410a73ab7c8](../ontology-prototype/discovery-platform/model.json#L729) | 인구이동 → 순이동자수 | 편집 정의 | 순이동은 전입에서 전출을 뺀 방향을 사용; 순유출과 부호 구분 | [user-requirements](#evidence-user-requirements) |
| [r-6b09a8a44367](../ontology-prototype/discovery-platform/model.json#L746) | 고용 → 청년 실업률 | 편집 정의 | 15~24세 계열과 국내 청년 정의를 자동 일치시키지 않음 | [user-requirements](#evidence-user-requirements) |
| [r-8ee0a49ed72c](../ontology-prototype/discovery-platform/model.json#L763) | 고용 → 청년 고용률 | 편집 정의 | 15~24세 인구 대비 취업자 비중; 실업률과 분모가 다름 | [user-requirements](#evidence-user-requirements) |
| [r-3cbbc988fa60](../ontology-prototype/discovery-platform/model.json#L780) | 주거 → 주택가격지수 | 편집 정의 | 실질·명목·기준연도·국가별 집계 방법 구분 | [user-requirements](#evidence-user-requirements) |
| [r-98bd39dcd151](../ontology-prototype/discovery-platform/model.json#L797) | 주거 → 임대료 지수 | 편집 정의 | 원화 월세 금액과 다름; 제공 계열의 실제 코드 확인 필요 | [user-requirements](#evidence-user-requirements) |
| [r-ad4c905f9efe](../ontology-prototype/discovery-platform/model.json#L814) | 교육·진로 → 졸업 후 이동 | 편집 정의 | 출신·졸업·취업 지역과 추적 기간을 포함한 자료가 필요 적절한 자료 대응이 아직 확보되지 않음. | [user-requirements](#evidence-user-requirements) |
| [r-62a2741c3e3b](../ontology-prototype/discovery-platform/model.json#L831) | 교육·진로 → NEET 비율 | 편집 정의 | 교육·취업·훈련 미참여 비율; 졸업 후 지역 이동의 대리변수로 확정하지 않음 적절한 자료 대응이 아직 확보되지 않음. | [user-requirements](#evidence-user-requirements) |

## 자료와 제공기관 — 6개

해당 기관을 통해 자료가 제공된다는 연결.

검토: 원문 자료 ID와 제공기관을 대조한다. 제공 경로와 원생산기관은 별도로 확인한다.

| 관계 ID · 원본 위치 | 연결 | 기존 근거 상태 | 현재 주의점 | 근거 |
|---|---|---|---|---|
| [r-3ebfaa92f163](../ontology-prototype/discovery-platform/model.json#L987) | KOSIS 이동자수 → 국가데이터처 | 공식 설명 근거 있음 | 관계 유형에 맞게 위 검토 항목을 확인 | [kosis-migration](#evidence-kosis-migration) · [kosis-table-access](#evidence-kosis-table-access) |
| [r-d23d04edcb72](../ontology-prototype/discovery-platform/model.json#L1005) | KOSIS 순이동 → 국가데이터처 | 공식 설명 근거 있음 | 관계 유형에 맞게 위 검토 항목을 확인 | [kosis-migration](#evidence-kosis-migration) · [kosis-table-access](#evidence-kosis-table-access) |
| [r-469a8194a2f2](../ontology-prototype/discovery-platform/model.json#L1023) | WB 청년 실업률 → World Bank | 공식 설명 근거 있음 | 관계 유형에 맞게 위 검토 항목을 확인 | [wb-unemployment](#evidence-wb-unemployment) |
| [r-214581da5a9e](../ontology-prototype/discovery-platform/model.json#L1040) | WB 청년 고용률 → World Bank | 공식 설명 근거 있음 | 관계 유형에 맞게 위 검토 항목을 확인 | [wb-employment](#evidence-wb-employment) |
| [r-eb66a6bad6a2](../ontology-prototype/discovery-platform/model.json#L1057) | OECD 실업 통계 → OECD | 공식 설명 근거 있음 | 관계 유형에 맞게 위 검토 항목을 확인 | [oecd-unemployment-web](#evidence-oecd-unemployment-web) |
| [r-d531e88be642](../ontology-prototype/discovery-platform/model.json#L1074) | OECD 주택가격 → OECD | 공식 설명 근거 있음 | 관계 유형에 맞게 위 검토 항목을 확인 | [oecd-housing-web](#evidence-oecd-housing-web) |

## 질문과 개념 — 3개

질문을 해당 개념으로 해석한 예시.

검토: 질문의 의도와 개념이 맞는지 확인하고, 정해지지 않은 지역·기간·연령 조건을 기록한다. 통계분석 대상이 아니다.

| 관계 ID · 원본 위치 | 연결 | 기존 근거 상태 | 현재 주의점 | 근거 |
|---|---|---|---|---|
| [r-7c054165458d](../ontology-prototype/discovery-platform/model.json#L559) | 청년 인구 유출 → 인구이동 | 편집 정의 | 관계 유형에 맞게 위 검토 항목을 확인 | [user-requirements](#evidence-user-requirements) |
| [r-6e18da008003](../ontology-prototype/discovery-platform/model.json#L576) | 청년 고용 → 고용 | 편집 정의 | 관계 유형에 맞게 위 검토 항목을 확인 | [user-requirements](#evidence-user-requirements) |
| [r-14f0a12d1fd3](../ontology-prototype/discovery-platform/model.json#L593) | 주거비 → 주거 | 편집 정의 | 관계 유형에 맞게 위 검토 항목을 확인 | [user-requirements](#evidence-user-requirements) |

## 근거 기록

공식 페이지 링크와 과거 관찰 상태를 함께 표시한다. 이번 표 생성은 원문 재조사나 새 검증이 아니다.

<a id="evidence-user-requirements"></a>
### user-requirements

[프로젝트 요구사항](../ontology-prototype/discovery-platform/requirements-v0.3.md)에서 가져온 편집 근거. 외부 실증 연구 결과가 아니다.

기존 확인 상태: `user_supplied_design` · 확인일: 기록 없음.

요청 반영을 위한 프로젝트 명세. 외부 자료의 존재·통계적 상관·운영 환경 설정의 증거로 사용하지 않음.

<a id="evidence-kosis-migration"></a>
### kosis-migration

[원문 출처](https://kosis.kr/serviceInfo/newContrainDataDetail.do?boardIdx=1976003&boardOrgId=101)

기존 확인 상태: `page_observed` · 확인일: 2026-09-12T10:27:42.177153+00:00.

<a id="evidence-kosis-table-access"></a>
### kosis-table-access

[원문 출처](https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B26001)

기존 확인 상태: `detail_access_unresolved` · 확인일: 2026-09-12.

통계표 직접 조회의 SSO 이동을 완료하지 못함. 자료의 제목·ID는 공식 최근수록자료 페이지에서 확인했으며 전체 표·단위·코드·기간·API는 미검증.

<a id="evidence-wb-unemployment"></a>
### wb-unemployment

[원문 출처](https://api.worldbank.org/v2/indicator/SL.UEM.1524.ZS?format=json)

기존 확인 상태: `metadata_observed` · 확인일: 2026-09-12T10:27:42.327448+00:00.

<a id="evidence-oecd-unemployment-web"></a>
### oecd-unemployment-web

[원문 출처](https://www.oecd.org/en/data/indicators/youth-unemployment-rate.html)

기존 확인 상태: `indicator_definition_and_dataset_referral_observed` · 확인일: 2026-09-12.

15~24세 실업 인구를 같은 연령 노동력 대비 비율로 표현. 원본으로 Monthly unemployment rates를 안내.

<a id="evidence-wb-employment"></a>
### wb-employment

[원문 출처](https://api.worldbank.org/v2/indicator/SL.EMP.1524.SP.ZS?format=json)

기존 확인 상태: `metadata_observed` · 확인일: 2026-09-12T10:27:42.360225+00:00.

<a id="evidence-oecd-housing-web"></a>
### oecd-housing-web

[원문 출처](https://www.oecd.org/en/data/indicators/housing-prices.html)

기존 확인 상태: `indicator_definition_and_dataset_referral_observed` · 확인일: 2026-09-12.

주택가격·주택 임대료의 지수와 가격 대비 소득·임대료 비율을 설명하고 Analytical house price indicators를 안내.

## 다시 생성

```bash
python ontology-prototype/governance/build_review_table.py
```

모델 내용 해시(UTF-8, LF): `86f1fb4a5e62890d2ba19e0ae7cc20e45bbbfa505b18e60fa9ce12648b9ed030`
