"""Check provenance and behavioural budget boundaries, without network calls."""
import copy
import json
from pathlib import Path
import sys
from explore import explore

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent.parent/'.prototype-tools'))
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, OWL

def main():
    model=json.loads((ROOT/'model.json').read_text(encoding='utf-8'))
    nids={n['id'] for n in model['nodes']};eids={e['id'] for e in model['source_evidence']}
    edges={e['id']:e for e in model['relations']};checks=[]
    def check(name,ok):checks.append({'name':name,'passed':bool(ok)})
    check('개체·관계 식별자와 참조',len(nids)==len(model['nodes']) and len(edges)==len(model['relations']) and all(e['source'] in nids and e['target'] in nids for e in edges.values()))
    check('모든 관계의 근거 존재',all(e['evidence_ids'] and set(e['evidence_ids'])<=eids for e in edges.values()))
    check('상관·인과를 계산 없이 선언하지 않음',all(e['causal_claim'] is False and e['correlation_coefficient'] is None for e in edges.values()))
    base=explore(model,'q-migration')
    check('깊이 2에서도 자료·기관까지 연결',len(base['recommendations'])==6 and any(n.startswith('provider-') for n in base['node_ids']))
    shallow=explore(model,'q-migration',{'max_depth':1})
    check('개념 확장 제한으로 직접 인구이동 자료만 반환',{r['dataset_id'] for r in shallow['recommendations']}=={'d-kosis-flows','d-kosis-net'})
    budget_cases=[('max_nodes',8,'nodes'),('max_edges',3,'edges'),('max_datasets',1,'datasets'),('max_scanned_edges',3,'scanned_edges')]
    for key,limit,count in budget_cases:
        result=explore(model,'q-migration',{key:limit})
        check(key+' 상한과 잘림 표시',result['counts'][count]<=limit and key in result['budget_stop_reasons'])
    timeout=explore(model,'q-migration',{'query_timeout_ms':0})
    check('시간 초과 시 추가 탐색 중단',timeout['counts']['edges']==0 and 'query_timeout_ms' in timeout['budget_stop_reasons'])
    check('후보와 직접 측정 경로의 구별',any(r['reason_kind']=='hypothesis_path' for r in base['recommendations']) and any(r['reason_kind']=='direct_measure_path' for r in base['recommendations']))
    check('결합 허가와 검색 안내 분리',all(not r['join_allowed'] and r['policy_decision']=='discovery_only' for r in base['recommendations']))
    paths_ok=True
    for r in base['recommendations']:
        cursor='q-migration'
        for eid in r['path']:
            e=edges[eid];paths_ok &= e['source']==cursor;cursor=e['target']
        paths_ok &= cursor==r['dataset_id']
    check('추천 이유가 실제 연속 경로를 가리킴',paths_ok)
    check('해결되지 않은 지표가 가짜 자료로 변환되지 않음',set(base['unresolved_indicators'])=={'i-neet','i-graduate'})
    error=False
    try:explore(model,'q-migration',{'max_nodes':999})
    except ValueError:error=True
    check('요청이 서버 정책 한도를 높일 수 없음',error)
    cyclic=copy.deepcopy(model)
    cyclic['relations'].append({'id':'test-cycle','source':'c-education','target':'c-migration','predicate':'test','semantic_cost':0,'priority':0,'status':'candidate','role':'context_hypothesis','evidence_ids':['user-requirements']})
    result=explore(cyclic,'q-migration')
    check('순환 관계가 있어도 탐색 한도 유지',result['counts']['nodes']<=30 and result['counts']['scanned_edges']<=200)
    graph=Graph().parse(ROOT/'discovery-ontology.ttl',format='turtle');ex=Namespace('https://example.org/public-data-discovery/')
    bad=[s for s in graph.subjects(ex.reviewStatus,Literal('candidate')) if (graph.value(s,RDF.subject),graph.value(s,RDF.predicate),graph.value(s,RDF.object)) in graph]
    check('RDF에서 후보 관계를 확정 사실로 내보내지 않음',not bad and not list(graph.triples((None,OWL.sameAs,None))))
    check('원본 행·자료 API 미검증 상태 보존',model['raw_rows_stored']==0 and all(d['raw_rows_stored']==0 and d['data_api_tested'] is False for d in model['datasets']))
    check('기존 전국 조사와 국제 범위를 유지',model['scope']['existing_domestic_service_entries']==122 and model['scope']['new_international_entries']==2 and model['scope']['example_is_product_scope_limit'] is False)
    report={'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'로컬 관계 모델·탐색 상한·근거 검증; 실 LLM·배포·원본 품질 검증 제외','rdf_triples':len(graph)}
    (ROOT/'validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'checks':len(checks),'failures':[c for c in checks if not c['passed']]},ensure_ascii=False,indent=2))
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
