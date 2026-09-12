"""Compile reviewed inputs and source observations into a traceable registry."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, quote

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent.parent/'.prototype-tools'))
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, SKOS, DCTERMS


def load(name):
    return json.loads((ROOT/name).read_text(encoding='utf-8'))


def save(name,obj):
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def stable(url):
    return re.sub(r';jsessionid=[^/?#;]+','',url or '',flags=re.I).strip()


def host(url):
    return (urlsplit(url).hostname or '').lower().removeprefix('www.')


def urlref(url):
    return URIRef(quote(url, safe="/:?#[]@!$&'()*+,;=%"))


def observation_status(row):
    if row.get('status') != 'page_observed':
        return 'fetch_unresolved'
    title, final = row.get('title',''), row.get('final_url','')
    if re.search('접속 확인|접근 차단|Access Denied|maintenance|/Auth\\.do',title+' '+final,re.I):
        return 'interstitial_observed'
    if len(row.get('text','')) >= 200:
        return 'body_observed'
    if title and title.lower() not in ('index','init-page','메인'):
        return 'title_only'
    return 'response_only'


NAV = re.compile(r'공공\s*데이터|데이터셋|데이터\s*(?:검색|목록|제공)|OPEN\s*API|오픈\s*API|개발자|이용안내|이용약관|저작권',re.I)
NEGATIVE_NAV = re.compile(r'공지|설문|당첨|이벤트|경진대회|공모전|활용사례|개방요청|제공신청|채용|입찰|보도')
LABELS={'body_observed':'본문 확인','title_only':'제목만 확인','response_only':'응답만 확인',
        'fetch_unresolved':'조회 미해결','interstitial_observed':'중간·점검 화면'}


def main():
    now = datetime.now(timezone.utc).isoformat()
    profile = load('ontology-profile.json')
    reviews = load('service-reviews.json')
    seeds = load('service-seeds.json') + load('discovered-services.json')
    sources = []
    for filename in ('directory-observations.json','directory-detail-observations.json',
                     'page-observations.json','discovered-page-observations.json'):
        for row in load(filename):
            sources.append({**row,'evidence_file':filename})
    scans=[json.loads(s) for s in (ROOT/'institution-site-observations.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    for row in scans:
        sources.append({**row,'links':row.get('candidate_data_links',[]),
                        'evidence_file':'institution-site-observations.jsonl'})
    byid={s['id']:s for s in sources}
    evidence=[]
    for row in sources:
        evidence.append({'id':row['id'],'source_url':stable(row.get('requested_url')),
            'observed_final_url':stable(row.get('final_url')) or None,
            'retrieved_at':row.get('retrieved_at'),'sha256':row.get('sha256'),
            'status':row.get('status'),'title':row.get('title'),
            'file':row['evidence_file'],'record_id':row['id']})
    evidence.append({'id':'design-profile','source_url':None,'file':'ontology-profile.json',
        'record_id':profile['profile_id'],'status':'project_curated_design','retrieved_at':now})
    evidence.append({'id':'manual-review','source_url':None,'file':'service-reviews.json',
        'record_id':'manual-review','status':'project_curated_review','retrieved_at':now})
    services=[]
    for seed in seeds:
        row=byid[seed['id']]
        navigation=[]
        for link in row.get('links',[]):
            label=link['label']
            if host(link['url'])==host(row.get('final_url') or seed['url']) and NAV.search(label) and not NEGATIVE_NAV.search(label):
                navigation.append({'label':label[:200],'url':stable(link['url']),
                                   'status':'link_observed_target_not_tested'})
        navigation=list({r['url']:r for r in navigation}.values())[:24]
        referrals=[]
        target_hosts={host(seed['url']),host(row.get('final_url') or seed['url'])}
        for source in sources:
            if source['id']==seed['id'] or host(source.get('requested_url','')) in target_hosts:
                continue
            for link in source.get('links',[]):
                if host(link['url']) in target_hosts:
                    referrals.append({'source_evidence_id':source['id'],
                        'source_url':stable(source.get('requested_url')),'link_url':stable(link['url']),
                        'link_label':link.get('label','')[:240],
                        'scope':'link_to_service_domain; exact dataset or API identity not established'})
                    break
        org=reviews['operator_claims'].get(seed['id'])
        org_candidate={**org,'evidence_id':seed['id'],'status':'candidate',
                       'role':'responsible_organization_candidate'} if org else None
        # Only the explicitly worded operator claim is emitted as operatedBy.
        operator={**org,'evidence_id':seed['id'],'status':'documented'} if seed['id']=='busan' else None
        state=observation_status(row)
        if seed['id'] in reviews['entrypoints']:
            next_action='기관 대표 누리집에서 실제 데이터 목록 또는 공식 제공처 확인'
        elif state!='body_observed':
            next_action='공식 안내·대상 본문과 현행 제공 경로 재확인'
        elif navigation:
            next_action='안내 경로에서 전체 목록 획득 방식·원본 분류·인증 조건 확인'
        else:
            next_action='데이터 목록·API 문서의 실제 접근 경로 확인'
        services.append({'id':seed['id'],'research_name':seed['name'],'observed_title':row.get('title') or None,
            'requested_url':seed['url'],'observed_final_url':stable(row.get('final_url')) or None,
            'group':seed['group'],'topics':seed['topics'],'region':seed['region'],
            'classification_status':'project_curated','operator':operator,
            'responsible_organization_candidate':org_candidate,
            'official_referrals':referrals,'observation_status':state,
            'entry_kind':'institution_entrypoint' if seed['id'] in reviews['entrypoints'] else 'data_service_candidate',
            'evidence_ids':[seed['id']]+list(dict.fromkeys(x['source_evidence_id'] for x in referrals)),
            'navigation_candidates':navigation,'data_api_tested':False,'catalog_collected':False,
            'operational_status':'not_verified','license_review':'not_reviewed',
            'notes':[n for n in (seed.get('note'),reviews['notes'].get(seed['id'])) if n],
            'next_action':next_action})
    candidate_map={}
    for row in scans:
        for link in row.get('candidate_data_links',[]):
            url=stable(link['url'])
            item=candidate_map.setdefault(url,{'id':'lead-'+sha256(url.encode()).hexdigest()[:12],
                'url':url,'labels':[],'evidence_ids':[],'institution_ids':[],
                'status':'navigation_candidate','matching_service_domain_ids':[]})
            item['labels'].append(link['label'])
            item['evidence_ids'].append(row['id'])
            item['institution_ids']+=row['institution_ids']
    for item in candidate_map.values():
        for key in ('labels','evidence_ids','institution_ids'):
            item[key]=list(dict.fromkeys(item[key]))
        item['matching_service_domain_ids']=[s['id'] for s in services
            if host(item['url']) in (host(s['requested_url']),host(s['observed_final_url'] or s['requested_url']))]
        item['likely_notice']=all(bool(NEGATIVE_NAV.search(label)) for label in item['labels'])
    queue=load('institution-review-queue.json')
    scan_by_inst={i:r for r in scans for i in r['institution_ids']}
    institution_states=[]
    for i in queue['institutions']:
        observation=scan_by_inst.get(i['id'])
        institution_states.append({**i,'homepage_scan_id':observation['id'] if observation else None,
            'homepage_scan_status':observation.get('status') if observation else 'not_scanned',
            'data_navigation_candidates':len(observation.get('candidate_data_links',[])) if observation else None,
            'data_service_review_status':'navigation_scan_only' if observation else 'not_reviewed'})
    region_names=[x['text'] for x in byid['directory-gov24']['select_options']
                  if x['select']=='jrsdOrgAstCd2' and x['value'].startswith('0201')]
    coverage=[]
    for region in region_names:
        ss=[s for s in services if s['region']==region or s['region'].startswith(region+' ')]
        coverage.append({'region_label_as_source':region,'source_evidence_id':'directory-gov24',
            'service_entry_ids':[s['id'] for s in ss],
            'body_observed_count':sum(s['observation_status']=='body_observed' for s in ss),
            'status':'investigation_in_progress','full_regional_coverage':False})
    summary={'compiled_at':now,'profile_id':profile['profile_id'],
        'national_census_complete':False,'service_entries':len(services),
        'service_entry_unit':'포털·서비스·기관 입구 조사 항목 (미검증 후보 포함)',
        'entry_kind_counts':dict(Counter(s['entry_kind'] for s in services)),
        'observation_counts':dict(Counter(s['observation_status'] for s in services)),
        'group_counts':dict(Counter(s['group'] for s in services)),
        'with_official_referral':sum(bool(s['official_referrals']) for s in services),
        'with_navigation_candidates':sum(bool(s['navigation_candidates']) for s in services),
        'institution_source_counts':queue['source_counts'],'institution_source_entries':len(institution_states),
        'homepage_scan':load('institution-scan-summary.json'),
        'unique_candidate_navigation_urls':len(candidate_map),
        'data_apis_tested':0,'full_dataset_catalogs_collected':0,'verified_dataset_joins':0,
        'gaps':queue['gaps']}
    registry={'summary':summary,'services':services,'regional_coverage':coverage}
    save('portal-registry.json',registry)
    save('source-evidence.json',evidence)
    save('navigation-review-queue.json',list(candidate_map.values()))
    save('institution-review-status.json',institution_states)
    save('coverage-report.json',summary)

    ex=Namespace(profile['namespace'])
    schema=Graph()
    for prefix,uri in [('pc',ex),('dcat',Namespace('http://www.w3.org/ns/dcat#')),('skos',SKOS),
                       ('dct',DCTERMS),('prov',Namespace('http://www.w3.org/ns/prov#'))]:
        schema.bind(prefix,uri)
    for name,label,parent in profile['classes']:
        schema.add((ex[name],RDF.type,OWL.Class))
        schema.add((ex[name],RDFS.label,Literal(label,lang='ko')))
        if parent: schema.add((ex[name],RDFS.subClassOf,URIRef(parent)))
    for name,label,domain,range_ in profile['properties']:
        schema.add((ex[name],RDF.type,OWL.ObjectProperty))
        schema.add((ex[name],RDFS.label,Literal(label,lang='ko')))
        if domain:schema.add((ex[name],RDFS.domain,ex[domain]))
        if range_:schema.add((ex[name],RDFS.range,ex[range_]))
    schema.serialize(ROOT/'common-ontology.ttl',format='turtle')
    graph=Graph()
    graph.bind('pc',ex);graph.bind('skos',SKOS);graph.bind('dct',DCTERMS)
    for e in evidence:
        eid=ex['evidence/'+e['id']]
        graph.add((eid,RDF.type,ex.SourceEvidence))
        if e.get('source_url'):graph.add((eid,DCTERMS.source,urlref(e['source_url'])))
        if e.get('retrieved_at'):graph.add((eid,ex.retrievedAt,Literal(e['retrieved_at'])))
    for s in services:
        node=ex['service/'+s['id']]
        graph.add((node,RDF.type,ex.ServiceEntry))
        graph.add((node,RDFS.label,Literal(s['research_name'],lang='ko')))
        graph.add((node,ex.requestedURL,urlref(s['requested_url'])))
        graph.add((node,ex.observationStatus,Literal(s['observation_status'])))
        graph.add((node,ex.evidence,ex['evidence/'+s['id']]))
        for label in s['topics']:
            concept=ex['topic/'+sha256(label.encode()).hexdigest()[:10]]
            graph.add((concept,RDF.type,SKOS.Concept))
            graph.add((concept,SKOS.prefLabel,Literal(label,lang='ko')))
            graph.add((node,ex.reviewedTopic,concept))
        for n,ref in enumerate(s['official_referrals']):
            claim=ex[f"claim/{s['id']}/referral/{n}"]
            graph.add((claim,RDF.type,ex.RelationshipClaim))
            graph.add((claim,RDF.subject,urlref(ref['source_url'])))
            graph.add((claim,RDF.predicate,ex.pageHyperlink))
            graph.add((claim,RDF.object,urlref(ref['link_url'])))
            graph.add((claim,ex.claimStatus,Literal('documented')))
            graph.add((claim,ex.evidence,ex['evidence/'+ref['source_evidence_id']]))
            graph.add((urlref(ref['source_url']),ex.pageHyperlink,urlref(ref['link_url'])))
        org=s['responsible_organization_candidate']
        if org:
            orgnode=ex['organization/'+sha256(org['name'].encode()).hexdigest()[:12]]
            graph.add((orgnode,RDF.type,ex.Organization))
            graph.add((orgnode,RDFS.label,Literal(org['name'],lang='ko')))
            claim=ex[f"claim/{s['id']}/organization"]
            graph.add((claim,RDF.type,ex.RelationshipClaim))
            graph.add((claim,RDF.subject,node))
            graph.add((claim,RDF.predicate,ex.operatedBy))
            graph.add((claim,RDF.object,orgnode))
            status='documented' if s['operator'] else 'candidate'
            graph.add((claim,ex.claimStatus,Literal(status)))
            graph.add((claim,ex.evidence,ex['evidence/'+s['id']]))
            if s['operator']:graph.add((node,ex.operatedBy,orgnode))
    graph.serialize(ROOT/'portal-registry.ttl',format='turtle')
    render_markdown(registry,list(candidate_map.values()),evidence)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def cell(text):
    return str(text or '미확인').replace('|',' / ').replace('\n',' ')


def markdown_url(url):
    return quote(url, safe="/:?#@!$&'*+,;=%")


def render_markdown(registry,leads,evidence):
    s=registry['summary']
    lines=['# 국내 공공데이터 제공처 등록부','',f"조사 기준: {s['compiled_at'][:10]}",'',
      f"포털·서비스·기관 입구 {s['service_entries']}개를 기록했다. 현재 운영·전량 수집 완료 목록이 아니며 미검증 후보를 포함한다.",
      '','첫 페이지 확인과 자료 API 동작, 전체 목록 확보, 라이선스 검토는 서로 다른 상태다.',
      '','## 전체 조사 현황','',
      f"- 공식 출처별 조사 항목 {s['institution_source_entries']}개. 기관 중복을 통합한 수가 아니다.",
      f"- 주소가 있는 홈페이지 {s['homepage_scan']['targets']}곳의 첫 페이지를 탐색했다.",
      f"- {s['homepage_scan']['pages_with_candidates']}곳에서 데이터 관련 링크 후보를 발견했다.",
      f"- 원문 링크 후보 {s['homepage_scan']['candidate_links']}개, 동일 URL을 묶은 검토 항목 {len(leads)}개.",
      '- 전체 자료 목록 수집·자료 API 실행·자료 간 결합 검증: 아직 수행하지 않음.',
      '','## 제공처 목록','',
      '| ID | 조사명·원문 주소 | 구분 | 조사 지역 | 페이지 확인 | 안내 경로 후보 |',
      '|---|---|---|---|---|---|']
    for row in registry['services']:
        lines.append(f"| {row['id']} | [{cell(row['research_name'])}]({markdown_url(row['requested_url'])}) | {row['group']} | {cell(row['region'])} | {LABELS[row['observation_status']]} | {len(row['navigation_candidates'])} |")
    lines+=['','## 지역별 조사 상태','',
       '아래 지역 이름은 정부24 조회 시점의 선택항목을 보존했다. 최신 행정구역 법적 효력·공간 경계의 검증을 뜻하지 않는다.',
       '','| 원문 지역명 | 제공처 조사 항목 | 본문 확인 항목 | 상태 |','|---|---|---|---|']
    for row in registry['regional_coverage']:
        lines.append(f"| {row['region_label_as_source']} | {len(row['service_entry_ids'])} | {row['body_observed_count']} | 조사 진행 중 |")
    lines+=['','## 항목별 근거와 다음 작업','']
    for row in registry['services']:
        lines += [f"### {row['research_name']} · {row['id']}",'',
            f"- 조회 제목: {cell(row['observed_title'])}",
            f"- 조회 주소: {row['requested_url']}",
            f"- 도착 주소: {cell(row['observed_final_url'])}",
            f"- 상태: {LABELS[row['observation_status']]} / 운영 상태 미검증 / 자료 API 미검증",
            f"- 조사 주제: {', '.join(row['topics'])} (프로젝트 편집 분류)"]
        org=row['operator'] or row['responsible_organization_candidate']
        if org:
            lines.append(f"- 기관: {org['name']} / {'운영기관 명시 확인' if row['operator'] else '관계 후보: 역할 추가 검토'} / {org['basis']}")
        else:lines.append('- 운영기관 역할: 미확인')
        for ref in row['official_referrals'][:3]:
            lines.append(f"- 연결 근거: [{cell(ref['link_label'])}]({markdown_url(ref['source_url'])}) → [관찰한 대상 경로]({markdown_url(ref['link_url'])})")
        for nav in row['navigation_candidates'][:6]:
            lines.append(f"- 안내 경로 후보: [{cell(nav['label'])}]({markdown_url(nav['url'])})")
        lines += [f"- 주의할 해석: {n}" for n in row['notes']]
        lines += [f"- 다음 작업: {row['next_action']}",'']
    (ROOT/'portal-registry.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    evidence_by_id={r['id']:r for r in evidence}
    lines=['# 추가 데이터 제공 경로 검토 목록','',
           '기관 홈페이지의 링크명으로 찾은 후보다. 공지·설문 링크가 섞일 수 있고, 데이터 포털이나 전체 자료 목록으로 확정하지 않았다.',
           '','| 후보 | 안내명 | 출처 | 기존 서비스 도메인과 일치 |','|---|---|---|---|']
    for lead in sorted(leads,key=lambda r:(r['likely_notice'],r['url'])):
        ev=evidence_by_id[lead['evidence_ids'][0]]
        lines.append(f"| [{lead['id']}]({markdown_url(lead['url'])}) | {cell(lead['labels'][0])} | [기관 페이지]({markdown_url(ev['source_url'])}) | {', '.join(lead['matching_service_domain_ids']) or '별도 검토'} |")
    (ROOT/'navigation-review-queue.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
