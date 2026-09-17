"""Offline checks on evidence references, census scope and RDF claim semantics."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent.parent/'.prototype-tools'))
from rdflib import Graph,Namespace,Literal
from rdflib.namespace import RDF,OWL


def load(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))


def main():
    registry=load('portal-registry.json'); services=registry['services']; profile=load('ontology-profile.json')
    evidence=load('source-evidence.json');eids={e['id'] for e in evidence}
    graph=Graph().parse(ROOT/'portal-registry.ttl',format='turtle')
    schema=Graph().parse(ROOT/'common-ontology.ttl',format='turtle')
    ex=Namespace(profile['namespace']); checks=[]
    def check(name,condition,detail):
        checks.append({'name':name,'passed':bool(condition),'detail':detail})
    check('등록부 ID 유일성',len({s['id'] for s in services})==len(services),len(services))
    check('모든 제공처의 관찰 근거 존재',all(set(s['evidence_ids'])<=eids for s in services),len(evidence))
    check('상태 enum과 합계 일치',all(s['observation_status'] in profile['observation_statuses'] for s in services)
          and sum(registry['summary']['observation_counts'].values())==len(services),registry['summary']['observation_counts'])
    check('페이지 접근과 자료 API·전량수집 분리',all(s['data_api_tested'] is False and s['catalog_collected'] is False for s in services),
          '기관목록 ALIO 조회 성공과 개별 자료 API 검증을 혼동하지 않음')
    check('이용 조건 미확인을 허용으로 바꾸지 않음',all(s['license_review']=='not_reviewed' for s in services),
          '실제 자료·행위별 검토 전')
    bad_candidates=[];bad_documented=[];bad_refs=[]
    for c in graph.subjects(RDF.type,ex.RelationshipClaim):
        sub=graph.value(c,RDF.subject);pred=graph.value(c,RDF.predicate);obj=graph.value(c,RDF.object)
        status=str(graph.value(c,ex.claimStatus)); evs=list(graph.objects(c,ex.evidence))
        if not evs or any((ev,RDF.type,ex.SourceEvidence) not in graph for ev in evs):bad_refs.append(str(c))
        if status=='candidate' and (sub,pred,obj) in graph:bad_candidates.append(str(c))
        if status=='documented' and (sub,pred,obj) not in graph:bad_documented.append(str(c))
    check('후보 기관 관계는 실제 운영 사실로 출력하지 않음',not bad_candidates,bad_candidates)
    check('확인된 링크·운영 관계의 근거 연결',not bad_documented and not bad_refs,{'missing_facts':bad_documented,'bad_evidence':bad_refs})
    check('포털·자료 동일성 자동 선언 없음',not list(graph.triples((None,OWL.sameAs,None))),'owl:sameAs 0개')
    check('데이터목록 미확보 항목을 Catalog로 과장하지 않음',not list(graph.subjects(RDF.type,ex.Catalog)),
          '현 단계는 ServiceEntry로 표현')
    alio=load('alio-roster.json')
    check('ALIO 출처의 전체 페이지 수집·식별자 중복 확인',
          len(alio['rows'])==alio['reported_total']==len({r['apbaId'] for r in alio['rows']}),
          {'source_rows':len(alio['rows']),'reported':alio['reported_total'],'pages':len(alio['pages'])})
    institutions=load('institution-review-queue.json')
    check('전국 완료와 출처별 수집 완료 구별',registry['summary']['national_census_complete'] is False
          and institutions['national_census_complete'] is False and alio['national_institution_roster_complete'] is False,
          institutions['gaps'])
    scan=load('institution-scan-summary.json')
    lines=[json.loads(x) for x in (ROOT/'institution-site-observations.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    check('홈페이지 탐색 manifest 완료 및 유일성',scan['targets']==scan['attempted']==len({r['id'] for r in lines}),scan)
    iids={i['id'] for i in institutions['institutions']}
    leads=load('navigation-review-queue.json')
    check('추가 경로 후보의 기관·관찰 근거 유효성',all(set(l['institution_ids'])<=iids and set(l['evidence_ids'])<=eids
          and l['status']=='navigation_candidate' for l in leads),len(leads))
    check('RDF 스키마와 등록부 재파싱 성공',len(schema)>0 and len(graph)>0,{'schema_triples':len(schema),'registry_triples':len(graph)})
    failures=[c for c in checks if not c['passed']]
    report={'passed':not failures,'checks':checks,'scope':'참조·상태·출처집계·RDF 검증; 원본 데이터 품질·법률·자료 API 검증 제외'}
    (ROOT/'validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':not failures,'checks':len(checks),'failures':failures,'schema_triples':len(schema),'registry_triples':len(graph)},ensure_ascii=False,indent=2))
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
