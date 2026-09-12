"""Check referential integrity and competency questions, never claim raw-data QA."""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '.prototype-tools'))
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, OWL, DCTERMS, SKOS

model = json.loads((HERE / 'model.json').read_text(encoding='utf-8'))
graph = json.loads((HERE / 'graph.json').read_text(encoding='utf-8'))
g = Graph().parse(HERE / 'ontology.ttl', format='turtle')
EX = Namespace(model['namespace'])
DCAT = Namespace('http://www.w3.org/ns/dcat#')
checks = []

def check(name, ok, evidence):
    checks.append({'name':name, 'passed':bool(ok), 'evidence':evidence})

ids = [n['id'] for n in graph['nodes']]
known = set(ids)
source_ids = {s['id'] for s in model['sources']}
check('노드 식별자 중복 없음', len(ids)==len(known), {'nodes':len(ids)})
bad = [e['id'] for e in graph['edges'] if e['subject'] not in known or e['object'] not in known or e['status'] not in model['statuses'] or not e['source_ids'] or not set(e['source_ids']) <= source_ids]
check('모든 관계에 유효한 양 끝·상태·근거 존재', not bad, bad)
q1 = {str(row.d).removeprefix(str(EX)) for row in g.query('''
  PREFIX dcat: <http://www.w3.org/ns/dcat#>
  PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
  PREFIX ex: <https://example.org/public-data/>
  SELECT DISTINCT ?d WHERE { ?d a dcat:Dataset; dcat:theme/skos:broader* ex:concept-transport . }
''')}
check('Q1 상위 교통 개념에서 버스·지하철 자료 탐색', q1=={'ds-bus-daily','ds-bus-hourly','ds-subway-daily'}, sorted(q1))
check('Q2 포털 안내는 사실, 정확한 등록 대응은 후보',
      (EX['portal-data-go'], EX.refersToPortal, EX['portal-seoul']) in g and
      (EX['record-go-bus'], EX.candidateTopic, EX['ds-bus-daily']) not in g and
      (EX['rel-crosslisting'], EX.status, Literal('candidate')) in g,
      '15051734의 외부 포털 안내와 OA-12912 대응 수준을 구분')
q3 = {str(row.d).removeprefix(str(EX)) for row in g.query('''
  PREFIX dcat: <http://www.w3.org/ns/dcat#>
  PREFIX ex: <https://example.org/public-data/>
  SELECT ?d WHERE {
    ?d a dcat:Dataset; dcat:theme ex:concept-living; ex:lifecycle ?state .
    FILTER(?state != "production_ended")
  }
''')}
check('Q3 생산 종료 생활인구를 현재 목록에서 제외', q3=={'ds-living-new'}, sorted(q3))
check('Q4 생활인구·주민등록인구 사이에 동일성 선언 없음',
      not list(g.triples((None, OWL.sameAs, None))) and
      not list(g.triples((None, SKOS.exactMatch, None))) and
      (EX['concept-living'], SKOS.related, EX['concept-resident']) in g,
      '관련성만 정의; 고유 인구 합산·동일성 추론 없음')
check('Q5 일별 지하철 자료의 출근시간 한계 보존',
      str(g.value(EX['ds-subway-daily'], EX.temporalGrain))=='일' and
      any('출근시간' in x for x in next(d for d in model['datasets'] if d['id']=='ds-subway-daily')['caveats']),
      '시간대 자료 추가 필요')
check('Q6 통계 작성기관과 포털 운영기관 구분',
      (EX['ds-resident'], DCTERMS.creator, EX['org-mois']) in g and
      (EX['portal-kosis'], EX.operatedBy, EX['org-mods']) in g,
      '행정안전부 작성 / 국가데이터처 운영')
candidate_leaks=[]
for e in graph['edges']:
    if e['status']=='candidate':
        pred = g.value(EX[e['id']], RDF.predicate)
        if (EX[e['subject']], pred, EX[e['object']]) in g:
            candidate_leaks.append(e['id'])
check('후보 관계를 확정 사실로 내보내지 않음', not candidate_leaks, candidate_leaks)
check('미검증 조인을 허용으로 표시하지 않음',
      all(j['status'] in ['requires_validation','blocked_for_blind_append'] and j['blockers'] for j in model['join_assessments']),
      {'join_assessments':len(model['join_assessments']), 'validated':0})
check('원본·API 확인 범위를 과장하지 않음',
      all(d['row_data_verified'] is False and d['api_verified'] is False for d in model['datasets']),
      '메타데이터 기반의 프로토타입')
bad_paths=[m['id'] for m in model['mappings'] if m['source_path'] is None and m['status']!='candidate']
check('원본 컬럼 미확정 매핑은 후보로 표시', not bad_paths, bad_paths)
check('종료일을 실제 마지막 관측일로 오인하지 않음',
      str(g.value(EX['ds-living-old'],EX.productionEndedAfter))=='2026-07-31' and
      not list(g.triples((EX['ds-living-old'],DCTERMS.temporal,None))),
      '생산 종료 안내만 저장')

report = {'reviewed_at':model['reviewed_at'], 'scope':'RDF 구문·참조·대표 질의·검증 상태; 원본 행/라이선스 법률 검토/API/조인 실행 검증 제외', 'rdf_triples':len(g), 'passed':all(c['passed'] for c in checks), 'checks':checks}
(HERE / 'validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'checks':len(checks),'rdf_triples':len(g)},ensure_ascii=False))
if not report['passed']:
    print(json.dumps([c for c in checks if not c['passed']],ensure_ascii=False,indent=2))
    sys.exit(1)
