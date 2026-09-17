## 프로젝트 개요

국내외에 분산된 공공데이터를 단순 키워드 검색이 아니라 **Ontology 기반 관계 그래프**를 통해 탐색할 수 있는 공공데이터 Discovery Platform을 구축한다.

기존 공공데이터 서비스는 사용자가 원하는 데이터의 정확한 명칭이나 기관을 알아야 검색하기 쉽다는 한계가 있다. 본 서비스는 사용자의 자연어 질문을 개념 단위로 변환하고, 해당 개념과 연관된 지표·데이터셋·기관을 그래프 형태로 연결하여 관련 데이터를 찾을 수 있도록 한다.

예를 들어 사용자가

> “청년 인구 유출과 관련된 데이터를 찾아줘”

라고 검색하면,

청년 인구 유출\
→ 고용\
→ 청년 실업률 / 청년 고용률\
→ 주거\
→ 주택가격 / 월세\
→ 교육\
→ 대학 졸업 후 이동\
→ 인구이동\
→ 전입 / 전출

과 같은 관계를 탐색하고, 각 지표에 연결된 KOSIS, OECD, World Bank, 공공데이터포털 등의 실제 데이터셋과 원문 사이트를 제공한다.

---

## 핵심 차별점

### 1. 자체 Ontology / Relationship DB

AI 모델 자체를 기술적 차별점으로 두지 않는다.

LLM은 교체 가능한 추론 인터페이스로 사용하고, 장기적으로 축적되는 핵심 자산은

**Dataset → Concept → Relation → Dataset**

구조의 자체 관계 DB이다.

각 데이터셋에 대해 다음 정보를 구조화한다.

- Dataset Metadata
- 제공 기관
- 국가
- 데이터 기간
- 데이터 단위
- 원본 URL / API
- 관련 Concept
- 다른 Concept과의 Relation
- Schema 요약

실제 대용량 공공데이터 원본 전체를 저장하지 않고 **Metadata + Relation + Source URL/API** 중심으로 관리해 서버 자원 사용을 최소화한다.

---

## Ontology Visualization

Ontology 관계를 Obsidian Graph View와 유사한 방식으로 시각화한다.

검색 주제를 중심으로

**주제 → 개념 → 지표 → 데이터셋 → 제공기관**

형태로 그래프가 확장된다.

사용자는 단순 데이터 목록이 아니라

- 왜 이 데이터가 검색되었는지
- 어떤 데이터와 관계가 있는지
- 추가적으로 어떤 데이터를 함께 분석할 수 있는지

를 시각적으로 탐색할 수 있다.

---

## Harness

Harness는 Agent의 행동뿐 아니라 **서버 자원 사용량까지 통제하는 Resource-aware Policy Layer**로 설계한다.

주요 제어 항목:

### Agent Budget

- 최대 Turn
- 최대 LLM API 호출 횟수
- 최대 Tool 호출 횟수
- Retry 제한
- Timeout

### Ontology Budget

- Graph 탐색 최대 Depth
- 최대 탐색 Node 수
- 최대 Edge 수
- 최대 Dataset 후보 수

### Memory Budget

- 최근 Context만 유지
- 오래된 대화 Summary 또는 폐기
- Session 비영구화
- 요청 완료 후 State 삭제

### Workspace / SSD Budget

- 임시 Workspace 최대 용량 제한
- TTL 적용
- 원본 Dataset 장기 저장 금지
- 작업 완료 후 임시 파일 즉시 삭제

### Cache Policy

- 모든 데이터를 캐싱하지 않음
- 재사용성이 높은 Metadata / Ontology mapping만 선택적 캐싱

예시:
```yaml
model:
  default: luna
  escalation: sol

agent:
  max_turns: 4
  max_llm_calls: 2
  max_tool_calls: 8
  max_retries: 1

ontology:
  max_depth: 2
  max_nodes: 30
  max_datasets: 10

memory:
  keep_recent_turns: 3
  persist_session: false
  cleanup_on_finish: true

workspace:
  max_size_mb: 200
  ttl_seconds: 300
  cleanup_on_finish: true

cache:
  policy: selective
```

이를 통해

**Ontology는 탐색 범위를 줄이고, Harness는 자원 사용 상한을 제한한다.**

---

## AI / API 구조

Codex 전체 Agent Runtime을 서비스 요청마다 사용하는 대신, 서비스에서는 OpenAI API 중심으로 설계한다.

구조:
```
사용자
 ↓
공공데이터 Web Service
 ↓
FastAPI
 ↓
Harness
 ↓
Query Understanding
 ↓
Ontology Graph
 ↓
Dataset Metadata DB
 ↓
OpenAI API
Luna / 필요시 Sol
 ↓
관련 Dataset + Relation + URL 반환
```

Luna를 기본 경량 모델로 사용하고, 관계가 모호하거나 복잡한 검증이 필요한 요청에만 Sol로 승격한다.

이를 통해 불필요한 멀티턴 Agent 실행 및 API 비용을 제한한다.

---

## AWS 구성

LLM 자체를 AWS에 직접 Hosting하지 않고 OpenAI API를 사용한다.

따라서 GPU 서버는 필요하지 않다.

### MVP

- App Server: 2 vCPU / 8GB RAM
- PostgreSQL: 2 vCPU / 4\~8GB RAM
- Storage: 100\~200GB
- GPU: 없음
- LLM: Luna / Sol API

### 초기 서비스

- App: 4 vCPU / 16GB RAM
- PostgreSQL: 8\~16GB RAM
- Storage: 300\~500GB
- 필요 시 App Container 수평 확장

사용량 증가 시 서버 한 대의 사양을 크게 올리기보다
```bash
Load Balancer
 ├─ App Container #1
 ├─ App Container #2
 ├─ App Container #3
 └─ ...
```

형태로 Scale-out한다.

---

## 배포 구조

초기 MVP에서는 Kubernetes까지 사용할 필요 없이

**Docker + AWS ECS/Fargate + RDS PostgreSQL**

구조로 시작한다.

Agent/API를 Docker Image 형태로 패키징한다.
```yaml
public-data-service:v1

├─ FastAPI
├─ Query Parser
├─ Harness
├─ Ontology Client
├─ Dataset Search
└─ OpenAI API Client
```

서비스 규모가 증가하면 Kubernetes/EKS로 확장한다.

---

## 최종 시스템 구조
```markdown
                      USER
                        │
                        ▼
                 Public Data UI
                        │
                        ▼
                     FastAPI
                        │
                        ▼
                     Harness
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
       Query Understanding      Resource Budget
             │
             ▼
        Ontology Graph
             │
      Concept / Relation
             │
             ▼
      Dataset Metadata DB
             │
       ┌─────┼─────────┐
       ▼     ▼         ▼
     KOSIS  OECD   World Bank
       │
       ▼
     Source URL/API

             +

        Luna / Sol API
```

---

## 한 문장 정의

**“국내외 공공데이터의 의미와 관계를 자체 Ontology DB로 구조화하고, Resource-aware Harness를 통해 AI의 탐색 범위와 서버 자원 사용량을 제어하며, 사용자가 데이터 관계를 그래프 형태로 탐색할 수 있도록 하는 공공데이터 Discovery Platform.”**

## 핵심 기술 메시지

**AI는 인터페이스이고, 실제 기술적 해자는 지속적으로 축적되는 공공데이터 관계 그래프다.**

Ontology는 **무엇을 찾을지**, Harness는 **어디까지 찾을지** 결정한다.