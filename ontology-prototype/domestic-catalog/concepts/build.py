"""Build an evidence-linked concept draft from a consistent, read-only catalog snapshot.

No HTTP collection, inference approval, observation analysis, or changes to the live DB.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import *
from collections import Counter,defaultdict
from seeds import seed_model
import re,sqlite3

OUT=Path(__file__).resolve().parent

def record_terms(m):
    result=[]
    def add(role,value,locator):
        if isinstance(value,str) and value.strip():result.append((role,value.strip(),locator))
    for k in ('category_raw','source_category','source_classification_label'):
        add('source_category',m.get(k),'$.'+k)
    path=m.get('category_path_raw')
    if path:
        parts=path.split(' > ')
        for i,v in enumerate(parts):
            if i==0 or (i==len(parts)-1 and v.strip()==m.get('title','').strip()):continue
            add('source_category',v,'$.category_path_raw::segment['+str(i)+']')
    s=m.get('source_catalog_record') or {}
    for k in ('topCateNm','topCateNm2','cl_nm','cl_cd_nm'):
        add('source_category',s.get(k),'$.source_catalog_record.'+k)
    raw=m.get('keywords_raw')
    if isinstance(raw,str):
        for i,v in enumerate(raw.split(',')):add('keyword_token_candidate',v,'$.keywords_raw::comma_token['+str(i)+']')
    for k in ('kwrd_one','kwrd_two','kwrd_three'):
        add('keyword_token_candidate',s.get(k),'$.source_catalog_record.'+k)
    return list(dict.fromkeys(result))

def build_review_queue(mappings, previous):
    # A sampled mapping may disappear and return on a later collection snapshot.
    # Preserve its review in both cases, without converting it to an approved fact.
    prior={x['id']:x for x in previous.get('previous_items_outside_current_sample',[])}
    prior.update({x['id']:x for x in previous.get('items',[])})
    items=[]
    for m in mappings:
        item={'id':m['id'],'concept_id':m['concept_id'],'record_id':m['evidence']['record_id'],
            'status':'pending','reviewer':None,'reviewed_at':None,'decision':None,'rationale':None,
            'evidence_refs':[m['evidence']['evidence_id']],'scope_conditions':m['required_checks']}
        saved=prior.pop(item['id'],{})
        for field in ('status','reviewer','reviewed_at','decision','rationale','evidence_refs','scope_conditions'):
            if field in saved:item[field]=saved[field]
        items.append(item)
    return {'generated_at':now(),'required_review_fields':['reviewer','reviewed_at','decision','rationale','evidence_refs','scope_conditions'],
        'allowed_decisions':['approve','revise','reject','needs_more_evidence'],
        'note':'승인은 명시된 범위의 개념 매핑에 한정한다. sameAs·자료 간 연결·통계 관계를 승인하는 것이 아니다.',
        'items':items,'previous_items_outside_current_sample':list(prior.values()),
        'existing_review_decisions_preserved':True,'decisions_not_automatically_applied_to_model':True}

def main():
    started=now();model=seed_model();by_id={c['id']:c for c in model['concepts']}
    aliases=defaultdict(list)
    for c in model['concepts']:
        for alias in c['aliases']:aliases[alias].append(c['id'])
    db=sqlite3.connect((ROOT/'.local/domestic-catalog/catalog.sqlite3').as_uri()+'?mode=ro',uri=True)
    db.execute('PRAGMA cache_size=-8192');db.execute('PRAGMA temp_store=FILE');db.execute('BEGIN')
    record_count=db.execute('SELECT count(*) FROM records').fetchone()[0]
    terms={};mapping_counts=Counter();mapping_samples=defaultdict(list);sample_portals=defaultdict(Counter)
    provenance={};category_paths=Counter();seen_source_labels=Counter();portal_records=Counter()
    def term(role,label,portal,example):
        key=(role,portal,label)
        t=terms.setdefault(key,{'id':uid('term',*key),'role':role,'portal_id':portal,'label_as_reported':label,
            'occurrences_in_index':0,'examples':[],'status':'source_label_bucket_not_validated_concept'})
        t['occurrences_in_index']+=1
        if len(t['examples'])<2:t['examples'].append(example)
    def sample(cid,kind,portal,item):
        mapping_counts[cid]+=1
        if len(mapping_samples[cid])<12 and sample_portals[cid][portal]<2:
            mapping_samples[cid].append({'kind':kind,'portal_id':portal,**item})
            sample_portals[cid][portal]+=1
    for n,(rid,portal,title,url,eid,locator,raw) in enumerate(db.execute('SELECT id,portal_id,title,url,evidence_id,locator,metadata_json FROM records ORDER BY id'),1):
        m=json.loads(raw);portal_records[portal]+=1
        for role,label,loc in record_terms(m):
            example={'record_id':rid,'evidence_id':eid,'catalog_locator':locator,'metadata_locator':loc}
            term(role,label,portal,example);seen_source_labels[role]+=1
            for cid in aliases.get(label,[]):
                if by_id[cid]['kind']=='Unit':continue
                sample(cid,'catalog_label',portal,{'record_id':rid,'record_title':title,'record_url':url,
                    'evidence_id':eid,'source_label':label,'match_channel':role,'metadata_locator':loc,'catalog_locator':locator})
        if m.get('category_path_raw'):category_paths[portal]+=1
        if n%100000==0:print('CATALOG_LABELS',n,'/',record_count,flush=True)
    total_fields=0;control_fields=0
    sql="""SELECT f.record_id,f.ordinal,f.name,f.name_en,f.description,f.datatype,f.unit,f.evidence_id,
        r.portal_id,json_extract(f.definition_json,'$.role') FROM documented_fields f JOIN records r ON r.id=f.record_id
        ORDER BY f.record_id,f.evidence_id,f.ordinal"""
    for rid,ordinal,name,en,desc,datatype,unit,eid,portal,role in db.execute(sql):
        total_fields+=1
        # Control fields remain in the collection, but do not become analytic concept candidates here.
        controls=role in ('response_envelope','response_control','api_response_control','error_response') or en in (
            'resultCode','resultMsg','resultMgs','list_total_count','RESULT.CODE','RESULT.MESSAGE','totalCount','numOfRows','pageNo')
        if controls:control_fields+=1;continue
        labels=list(dict.fromkeys(x.strip() for x in (name,en) if isinstance(x,str) and x.strip()))
        identity={'record_id':rid,'evidence_id':eid,'ordinal':ordinal}
        for label in labels:term('documented_field_label',label,portal,identity)
        if unit:term('documented_unit',unit,portal,identity)
        cids=set()
        for label in labels:
            for cid in aliases.get(label,[]):
                if by_id[cid]['kind'] not in ('Topic','Unit'):cids.add(cid)
        for cid in aliases.get(unit,[]):
            if by_id[cid]['kind']=='Unit':cids.add(cid)
        # Explicit scope guards: generic names or English abbreviations alone are ambiguous.
        if portal!='neis' and name=='행정표준코드':cids.discard('identifierscheme:school-code')
        if portal=='hrfco':
            if en=='RF':cids.add('measure:precipitation')
            if en=='WL':cids.add('measure:water-level')
        for cid in sorted(cids):
            sample(cid,'documented_field',portal,{**identity,'field_name':name,'field_name_en':en,
                'description_as_reported':desc,'datatype_as_reported':datatype,'unit_as_reported':unit,'field_role':role,
                'match_channel':'literal_unit' if by_id[cid]['kind']=='Unit' else 'exact_alias_with_source_scope',
                'source_label':unit if by_id[cid]['kind']=='Unit' else next((v for v in labels if cid in aliases.get(v,[])),en)})
        if total_fields%250000==0:print('FIELD_LABELS',total_fields,flush=True)
    print('ENRICHING_SELECTED_EVIDENCE',flush=True)
    mappings=[]
    for cid,examples in sorted(mapping_samples.items()):
        for sample_index,x in enumerate(examples):
            if x['kind']=='documented_field':
                data=db.execute('SELECT definition_json FROM documented_fields WHERE record_id=? AND evidence_id=? AND ordinal=?',
                    (x['record_id'],x['evidence_id'],x['ordinal'])).fetchone()
                f=json.loads(data[0]);r=db.execute('SELECT title,url,dataset_key FROM records WHERE id=?',(x['record_id'],)).fetchone()
                x.update(record_title=r[0],record_url=r[1],dataset_key=r[2],source_url=f['source_url'])
                docpath=db.execute('SELECT path FROM schema_document_sources WHERE record_id=? AND evidence_id=? ORDER BY path LIMIT 1',
                    (x['record_id'],x['evidence_id'])).fetchone()
                x['definition_document']=docpath[0] if docpath else None
                raw=f['raw_definition'];x['source_locator']=raw.get('locator')
                x['stored_field_identity']={'record_id':x['record_id'],'evidence_id':x['evidence_id'],'ordinal':x['ordinal']}
                if 'declared_code_count' in raw:
                    codes=raw.get('observed_codes',[])
                    x['code_context']={'declared_code_count':raw['declared_code_count'],'code_list_complete':raw.get('code_list_complete'),
                        'display_sample':codes[:10],'display_sample_truncated':len(codes)>10,'codes_not_assumed_cross_portal_equivalent':True}
                x['source_locator_unavailable']=not bool(x['source_locator'])
                # Stored file position is distinct from the raw-source position; never fabricate the latter.
                if docpath:
                    dd=read(HERE/'definitions'/docpath[0]);indices=[i for i,v in enumerate(dd.get('fields',[])) if v==raw]
                    assert indices,(x['record_id'],x['ordinal'],docpath[0])
                    x['extracted_definition_locator']='/fields/'+str(indices[0])
            eid=x['evidence_id']
            if eid not in provenance:
                receipt_path=HERE/'evidence'/(eid+'.json')
                if receipt_path.is_file():
                    receipt=read(receipt_path)
                    provenance[eid]={k:receipt.get(k) for k in ('id','requested_url','retrieved_at','sha256','raw_file','status')}
                else:provenance[eid]={'id':eid,'status':'receipt_not_found_in_current_evidence_directory'}
            mappings.append({'id':uid('mapping',cid,x['kind'],x['record_id'],x['evidence_id'],x.get('ordinal'),x.get('metadata_locator')),
                'concept_id':cid,'proposed_predicate':'hasUnit' if by_id[cid]['kind']=='Unit' else 'describesConcept',
                'status':'candidate_pending_human_review','human_approved':False,
                'match_is_not_semantic_equivalence':True,'evidence':x,
                'required_checks':by_id[cid]['scope_checks']})
    # Examples explicitly requested in the conversation, preserved as a review task, not a statistical claim.
    joins=[{'id':'join-candidate:seoul-bus-living-population','source_record_id':'seoul-row-1340','target_record_id':'seoul-row-1804',
        'proposed_relation':'joinableUnderConditions','status':'candidate_pending_human_review','human_approved':False,
        'purpose':'지역별 생활인구와 버스 이용을 같은 분석 단위로 준비할 수 있는지 검토',
        'required_checks':['정류장 위치를 집계구 또는 행정동에 대응하는 별도 근거',
            '관측 기준일과 집계 시간·주기 일치','행정구역과 정류장 코드의 버전',
            '일대다 연결로 인한 중복 합산 방지','실인원과 이용 건수의 정의','원본 이용조건'],
        'statistical_association_asserted':False,'actual_join_executed':False}]
    assert all(db.execute('SELECT 1 FROM records WHERE id=?',(r,)).fetchone() for x in joins for r in (x['source_record_id'],x['target_record_id']))
    by_kind=Counter(c['kind'] for c in model['concepts'])
    mapped_ids={x['concept_id'] for x in mappings}
    for c in model['concepts']:
        c['candidate_occurrences_in_index']=mapping_counts[c['id']]
        c['displayed_evidence_examples']=sum(m['concept_id']==c['id'] for m in mappings)
        c['evidence_status']='source_label_examples_linked_semantics_pending' if c['id'] in mapped_ids else 'no_exact_source_label_example_yet'
    model.update(generated_at=now(),snapshot_started_at=started,counts={
        'catalog_records_scanned':record_count,'portals_scanned':len(portal_records),'formal_field_rows_scanned':total_fields,
        'control_field_rows_excluded_from_analytic_candidates':control_fields,'source_label_buckets':len(terms),
        'project_concepts':len(model['concepts']),'concepts_by_kind':dict(by_kind),
        'concepts_with_source_examples':len(mapped_ids),'mapping_examples':len(mappings),
        'human_approved_concept_mappings':0,'statistical_associations_verified':0},
        source_inventory={'record_counts_by_portal':dict(portal_records),'catalog_label_occurrences':dict(seen_source_labels),
            'term_buckets_are_portal_role_label_groups_not_unique_concepts':True,
            'field_counts_include_repeated_provider_links':True,'keyword_splitting_is_a_candidate_extraction':True},
        mappings=mappings,evidence=list(provenance.values()),join_review_candidates=joins,
        collection_complete=False,concept_system_complete=False)
    db.rollback();db.close()
    term_rows=sorted(terms.values(),key=lambda t:(-t['occurrences_in_index'],t['id']))
    dest=OUT/'source-terms.jsonl.gz'
    with gzip.open(dest,'wt',encoding='utf-8',compresslevel=3) as f:
        for t in term_rows:f.write(json.dumps(t,ensure_ascii=False)+'\n')
    term_db=OUT/'source-terms.sqlite3';temp=term_db.with_name('source-terms.build.sqlite3')
    if temp.exists():temp.unlink()
    store=sqlite3.connect(temp)
    store.execute('CREATE TABLE terms(id TEXT PRIMARY KEY,label TEXT,role TEXT,portal_id TEXT,occurrences INTEGER,data_json TEXT)')
    store.executemany('INSERT INTO terms VALUES(?,?,?,?,?,?)',[(t['id'],t['label_as_reported'],t['role'],t['portal_id'],t['occurrences_in_index'],json.dumps(t,ensure_ascii=False)) for t in term_rows])
    store.execute('CREATE INDEX terms_role ON terms(role,occurrences DESC)');store.commit();store.close();temp.replace(term_db)
    model['term_preview']=term_rows[:60]
    model['files']={'full_source_terms':'source-terms.jsonl.gz','review_queue':'review-queue.json','rdf':'concept-model.ttl'}
    dump(OUT/'concept-model.json',model)
    queue_path=OUT/'review-queue.json'
    previous=read(queue_path) if queue_path.exists() else {}
    dump(queue_path,build_review_queue(mappings,previous))
    export_rdf(model)
    template=(OUT/'explorer.template.html').read_text(encoding='utf-8') if (OUT/'explorer.template.html').exists() else None
    if template:
        payload=json.dumps(model,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
        (OUT/'explorer.html').write_text(template.replace('__CONCEPT_DATA__',payload),encoding='utf-8')
    write_docs(model)
    main_model=read(HERE/'model.json')
    main_model['concept_layer']={'status':'project_draft_with_source_evidence','version':'0.1.0','model':'concepts/concept-model.json',
        'guide':'concepts/README.md','explorer':'concepts/explorer.html','review_queue':'concepts/review-queue.json',
        'separate_from_source_collection_counts':True,'human_approved_mappings':0}
    main_model['instance_files'].update(concept_model='concepts/concept-model.json',concept_term_inventory='concepts/source-terms.jsonl.gz',
        concept_review_queue='concepts/review-queue.json',concept_rdf='concepts/concept-model.ttl')
    dump(HERE/'model.json',main_model)
    print(json.dumps({'generated_at':model['generated_at'],**model['counts']},ensure_ascii=False),flush=True)

def export_rdf(model):
    from rdflib import Graph,Namespace,URIRef,Literal
    from rdflib.namespace import RDF,SKOS
    g=Graph();p=Namespace('urn:public-data-ontology:');g.bind('pdo',p);g.bind('skos',SKOS)
    def node(x):return URIRef('urn:public-data-ontology:'+x)
    for c in model['concepts']:
        n=node(c['id']);g.add((n,RDF.type,SKOS.Concept));g.add((n,SKOS.prefLabel,Literal(c['label'],lang='ko')))
        g.add((n,p.facet,Literal(c['kind'])));g.add((n,p.workingDefinition,Literal(c['working_definition'],lang='ko')))
        g.add((n,p.reviewStatus,Literal('project_draft')))
        for alias in c['aliases']:g.add((n,p.candidateAlias,Literal(alias,lang='ko')))
    for r in model['relationships']:
        n=node(r['id']);g.add((n,RDF.type,p.RelationshipProposal));g.add((n,p.source,node(r['source'])))
        g.add((n,p.proposedPredicate,Literal(r['predicate'])));g.add((n,p.target,node(r['target'])))
        g.add((n,p.reviewStatus,Literal(r['status'])))
    for m in model['mappings']:
        n=node(m['id']);e=m['evidence'];g.add((n,RDF.type,p.ConceptMappingProposal))
        g.add((n,p.candidateConcept,node(m['concept_id'])));g.add((n,p.recordId,Literal(e['record_id'])))
        g.add((n,p.evidenceId,Literal(e['evidence_id'])));g.add((n,p.reviewStatus,Literal(m['status'])))
    g.serialize(destination=str(OUT/'concept-model.ttl'),format='turtle')

def write_docs(m):
    lines=['# 공공데이터 공통 개념 체계 초안','',
        '분야·지표·대상·분류·공간·시간·식별 기준·단위를 분리해 데이터의 의미를 찾기 위한 작업용 온톨로지다.',
        '통계적 상관관계가 아니라 개념과 명세의 연결 후보를 구성했다. 정의·동의어·연결은 사람 검토 전이다.','',
        '## 현재 구성','',f"- 저장 시각: {m['generated_at']}",
        f"- 등록정보 {m['counts']['catalog_records_scanned']:,}건, 저장 명세 행 {m['counts']['formal_field_rows_scanned']:,}개를 읽기 전용으로 조사했다.",
        f"- 공통 개념 {len(m['concepts'])}개, 원문 예시가 연결된 개념 {m['counts']['concepts_with_source_examples']}개, 검토할 연결 예시 {len(m['mappings'])}개.",
        f"- 출처·역할·표기별 용어 후보 묶음 {m['counts']['source_label_buckets']:,}개. 고유 의미 개념 수가 아니다.",
        '- 정식 개념 매핑 승인 0개, 통계적 관계 승인 0개. 전국 개념 수집 완료율은 산출하지 않는다.','',
        '## 읽는 순서','',
        '1. [개념 탐색 화면](http://127.0.0.1:8766/concepts)을 열고 분야나 개념을 선택한다.',
        '2. 개념의 작업용 정의와 구분 조건을 읽는다. 인구수·생활인구·주민등록인구를 자동 병합하지 않는다.',
        '3. 실제 자료·칼럼 예시의 원문과 단위·분류를 대조한다. 원문에 단위가 없으면 미확인으로 둔다.',
        '4. [검토 목록](review-queue.json)에 검토자·판정·근거·적용 조건을 기록한다. 현재 파일은 대기 상태다.',
        '5. 판정은 그 개념 매핑 범위에 한정한다. sameAs·자료 결합·상관관계 승인은 별도다.','',
        '## 이 작업에서 사람이 확인할 것','',
        '예를 들어 실업률을 선택하면 충남·KOSIS 등의 실제 명세 항목과 출처가 나온다. 이름이 같다는 사실만으로 통계의 대상·분모·기간까지 같다고 판단하지 않는다.',
        '지역은 공간 기준이고 실업률은 지표다. 지역을 실업률의 상위 개념으로 두거나 지역 코드 숫자와 실업률의 상관계수를 계산하지 않는다. 지역별 실업률 비교는 이후 실제 관측값을 확보해 수행하는 별도 분석이다.','',
        '| 검토 대상 | 확인할 내용 | 이번 초안의 처리 |','|---|---|---|',
        '| 개념과 칼럼 | 원문에서 무엇을 뜻하며 대상·단위·분모가 맞는가 | 의미 연결 후보와 원문 근거를 함께 저장 |',
        '| 다른 자료와 결합 | 코드 체계·버전·공간·시간·중복 집계 조건이 맞는가 | 별도 검토 과제로 두고 결합을 확정하지 않음 |',
        '| 수치적 관계 | 실제 값에서 어떤 통계적 관련성이 나타나는가 | 이번 작업에서는 분석하거나 승인하지 않음 |','',
        '## 구조와 식별자','',
        '- Topic은 탐색 분야다. 실업률이 지역의 하위 클래스라는 뜻이 아니다.',
        '- Measure는 지표, Dimension은 분류, SpatialReference/TemporalReference는 기준 공간·시간이다.',
        '- IdentifierScheme은 코드 계열이다. 문자나 숫자가 같아도 기관·체계·버전이 같다는 보장은 없다.',
        '- 개념 ID는 프로젝트 내부 이름공간이다. 원문 포털의 데이터셋 ID와 혼동하지 않는다.',
        '- RDF/Turtle에는 정의 초안과 RelationshipProposal/ConceptMappingProposal을 내보낸다. 후보를 확정 의미 관계로 직렬화하지 않는다.','',
        '## 개념 목록','', '|역할|개념|검토할 조건|원문 예시|','|---|---|---|---:|']
    for c in m['concepts']:
        lines.append('|'+m['facets'][c['kind']]['label']+'|'+c['label']+'|'+' / '.join(c['scope_checks']).replace('|','/')+'|'+str(c['displayed_evidence_examples'])+'|')
    lines+=['','## 파일','',
        '- [개념·관계·근거 JSON](concept-model.json)', '- [RDF/Turtle](concept-model.ttl)',
        '- [전체 용어 후보 JSONL gzip](source-terms.jsonl.gz)',
        '- source-terms.sqlite3는 용어 검색용 보조 DB이며 원래 catalog.sqlite3는 변경하지 않는다.',
        '- [검토 목록](review-queue.json). 자동 승인하지 않는다.',
        '- [출처·내보내기·HTTP 검사 결과](validation-report.json). 의미 관계를 승인하는 검사는 아니다.',
        '- 반복 실행: `python -X utf8 ontology-prototype/domestic-catalog/concepts/build.py`',
        '- 검사 실행: 검색 서버를 켠 뒤 `python -X utf8 ontology-prototype/domestic-catalog/concepts/check.py`',
        '- 빌더 재실행은 같은 ID의 기존 검토 판단을 보존하고, 새 표본에서 빠진 항목도 별도 배열에 남긴다. 판단을 모델에 자동 승인·적용하지 않는다.',
        '', '현재 이 화면은 LLM 추천·실제 값 분석·품질 점수 자동 산출 서비스가 아니다. 그 기능에 사용할 개념과 근거를 검토하는 도구다.','']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')

if __name__=='__main__':
    if '--render-only' in sys.argv:
        model=read(OUT/'concept-model.json')
        payload=json.dumps(model,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
        (OUT/'explorer.html').write_text((OUT/'explorer.template.html').read_text(encoding='utf-8').replace('__CONCEPT_DATA__',payload),encoding='utf-8')
        print('Concept explorer rendered from saved snapshot')
    else:main()
