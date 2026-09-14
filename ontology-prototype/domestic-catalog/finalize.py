"""Combine acquired catalogs and definitions; produce coverage and ontology manifest."""
from common import *
from build_inventory import DB,OUT
from collections import Counter
import sqlite3

def integrate():
    db=sqlite3.connect(DB)
    db.execute('PRAGMA foreign_keys=ON')
    # Rebuild only the adapter-owned rows in this generated local index.
    db.execute("DELETE FROM fields WHERE record_id IN (SELECT id FROM records WHERE portal_id IN ('neis','gyeonggi'))")
    db.execute('DELETE FROM documented_fields')
    db.execute("DELETE FROM records WHERE portal_id IN ('neis','gyeonggi')")
    with gzip.open(OUT/'additional-catalog-records.jsonl.gz','wt',encoding='utf-8') as out:
        for portal,base in [('neis','https://open.neis.go.kr'),('gyeonggi','https://data.gg.go.kr')]:
            for item in read(OUT/(portal+'-catalog.json')):
                key=item['infId'];seq=item.get('acolInfSeq') or item['infSeq']
                row={'id':portal+'-'+key,'portal_id':portal,'dataset_key':key,'title':item['infNm'],
                    'provider_id':None,'provider_name':None,'kind':'public_catalog_entry',
                    'url':base+'/portal/data/service/selectServicePage.do?infId='+key+'&infSeq='+str(seq),
                    'evidence_id':item['catalog_evidence_id'],'locator':'infId='+key,
                    'output_raw':None,'request_raw':None,'schema_status':'separate_definition_check',
                    'source_catalog_record':item,'provider_note':'목록 응답에 제공기관 없음; 기관은 별도 명세 필요'}
                keys=['id','portal_id','dataset_key','title','provider_id','provider_name','kind','url','evidence_id','locator','output_raw','request_raw','schema_status']
                db.execute('INSERT INTO records VALUES('+','.join('?' for _ in range(14))+')',
                           [row.get(k) for k in keys]+[json.dumps(row,ensure_ascii=False)])
                out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    documented=0
    with gzip.open(OUT/'documented-columns.jsonl.gz','wt',encoding='utf-8') as out:
        for path in sorted((HERE/'definitions').glob('*.json')):
            d=read(path)
            if not d.get('fields'):continue
            query='SELECT id FROM records WHERE portal_id=? AND dataset_key=?'
            if d['portal_id']=='data-go':query+=" AND kind='FILE'"
            ids=[r[0] for r in db.execute(query,(d['portal_id'],d['dataset_key']))]
            if not ids:raise ValueError('Definition without catalog record: '+str(path))
            for rid in ids:
                for pos,f in enumerate(d['fields'],1):
                    norm=lambda x: None if x in ('','-',None) else x
                    record={'record_id':rid,'ordinal':pos,'name':norm(f.get('name')),
                        'name_en':norm(f.get('name_en')),'description':norm(f.get('description')),
                        'datatype':norm(f.get('datatype')),'unit':norm(f.get('unit')),
                        'evidence_id':d['evidence_id'],'source_url':d['source_url'],
                        'status':'definition_observed_not_data_validated','raw_definition':f}
                    db.execute('INSERT INTO documented_fields VALUES(?,?,?,?,?,?,?,?,?)',
                        (rid,pos,record['name'],record['name_en'],record['description'],record['datatype'],record['unit'],json.dumps(record,ensure_ascii=False),d['evidence_id']))
                    out.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n');documented+=1
    db.execute('CREATE INDEX IF NOT EXISTS documented_names ON documented_fields(name)')
    db.execute('CREATE INDEX IF NOT EXISTS documented_record ON documented_fields(record_id)')
    # Project-curated catalog relations expose their actual evidence level.
    db.executescript('''
    DROP VIEW IF EXISTS relationship_evidence;
    CREATE VIEW relationship_evidence AS
      SELECT portal_id AS source,'listsRegistration' AS predicate,id AS target,evidence_id,'source_catalog_observed' AS status FROM records
      UNION ALL SELECT id,'reportedProvider',provider_id,evidence_id,'provider_reported_in_catalog' FROM records WHERE provider_id IS NOT NULL
      UNION ALL SELECT record_id,'hasDocumentedField',record_id||':'||ordinal,evidence_id,'definition_observed_not_data_validated' FROM documented_fields;
    ''')
    db.commit()
    counts=[]
    for portal,n,keys,providers in db.execute('SELECT portal_id,count(*),count(distinct dataset_key),count(distinct provider_id) FROM records GROUP BY portal_id'):
        declared=db.execute("SELECT count(*) FROM fields JOIN records ON records.id=fields.record_id WHERE portal_id=? AND role='output'",(portal,)).fetchone()[0]
        defs=db.execute('SELECT count(*),count(distinct record_id) FROM documented_fields JOIN records ON records.id=documented_fields.record_id WHERE portal_id=?',(portal,)).fetchone()
        pending=db.execute('SELECT count(*) FROM records WHERE portal_id=? AND NOT EXISTS(SELECT 1 FROM documented_fields d WHERE d.record_id=records.id)',(portal,)).fetchone()[0]
        counts.append({'portal_id':portal,'catalog_records':n,'distinct_catalog_keys':keys,
            'provider_codes_in_source_namespace':providers,'declared_output_tokens':declared,
            'documented_columns':defs[0],'records_with_documented_columns':defs[1],
            'records_without_documented_columns':pending})
    providers=[]
    for pid,name,portal,n in db.execute('SELECT provider_id,min(provider_name),portal_id,count(*) FROM records WHERE provider_id IS NOT NULL GROUP BY portal_id,provider_id ORDER BY portal_id,provider_id'):
        providers.append({'id':pid,'name_as_reported':name,'portal_id':portal,'catalog_records':n,
                          'cross_portal_organization_identity':'not_reconciled'})
    dump(OUT/'providers.json',providers)
    registry=read(HERE.parent/'national-catalog/portal-registry.json')
    states={x['portal_id']:x for x in counts}
    portals=[]
    for p in registry['services']:
        portals.append({**p,'scope':'domestic_portal','current_collection':states.get(p['id']),
            'collection_status':'catalog_acquired_columns_partial' if p['id'] in states else 'catalog_and_columns_pending',
            'all_portal_datasets_collected':False,'all_portal_columns_collected':False})
    dump(OUT/'domestic-portals.json',{'scope':'국내 제공처; 분야 제한 없음','national_census_complete':False,'portals':portals})
    # Export every declared token with a positional source reference, as candidates.
    with gzip.open(OUT/'declared-field-tokens.jsonl.gz','wt',encoding='utf-8') as out:
        for rid,role,pos,name,status in db.execute('SELECT * FROM fields ORDER BY record_id,role,ordinal'):
            out.write(json.dumps({'record_id':rid,'role':role,'ordinal':pos,'name':name,'status':status},ensure_ascii=False,separators=(',',':'))+'\n')
    summary={'generated_at':now(),'scope':'국내 포털 전 분야 공개 카탈로그와 공개 칼럼 명세',
        'registered_portal_candidates':len(portals),'portals_with_catalog_acquisition':len(counts),
        'portal_counts':counts,'total_catalog_records':sum(x['catalog_records'] for x in counts),
        'distinct_catalog_keys_across_portal_namespaces':sum(x['distinct_catalog_keys'] for x in counts),
        'declared_output_tokens':sum(x['declared_output_tokens'] for x in counts),
        'documented_column_occurrences':documented,'quarantined_source_records':db.execute('SELECT count(*) FROM quarantine').fetchone()[0],
        'all_domestic_portals_complete':False,'all_columns_complete':False,
        'cross_portal_deduplication_complete':False,'raw_observation_values_collected':0,
        'statistical_associations_verified':0,'semantic_relationships_approved':0}
    dump(HERE/'coverage-report.json',summary)
    model={'version':'0.5.0','scope':{'provider_geography':'KR','topic_restriction':None,
        'excluded_external_portals':['OECD','World Bank'],'all_domestic_portals_complete':False},
        'description':'실제 수집 목록을 참조하는 국내 메타데이터 온톨로지. 대규모 인스턴스는 파일/DB로 분리.',
        'entity_types':['Portal','CatalogRegistration','ReportedOrganization','DeclaredFieldToken','DocumentedField','SourceEvidence','HumanReview'],
        'relation_types':[
            {'predicate':'listsRegistration','source':'Portal','target':'CatalogRegistration','evidence':'공식 목록 행'},
            {'predicate':'reportedProvider','source':'CatalogRegistration','target':'ReportedOrganization','evidence':'목록의 기관 코드·명칭; 포털 간 기관 동일성 미확정'},
            {'predicate':'declaresOutputToken','source':'CatalogRegistration','target':'DeclaredFieldToken','evidence':'출력결과 문자열 분리; 구분자 검증 전 후보'},
            {'predicate':'hasDocumentedField','source':'CatalogRegistration','target':'DocumentedField','evidence':'공식 공개 칼럼 명세; 실제 값 검사 전'},
            {'predicate':'supportedBy','source':'CatalogRegistration|DocumentedField','target':'SourceEvidence','evidence':'URL·조회일·SHA256·원문 위치'},
            {'predicate':'sameAs|joinableWith|statisticallyAssociatedWith','status':'not_asserted','requires':'관계별 사람 검토·조건·분석 근거'}],
        'instance_files':{'portals':'inventory/domestic-portals.json','providers':'inventory/providers.json',
            'catalogs':['inventory/catalog-records.jsonl.gz','inventory/additional-catalog-records.jsonl.gz'],
            'declared_tokens':'inventory/declared-field-tokens.jsonl.gz','columns':'inventory/documented-columns.jsonl.gz'},
        'local_query_index':'.local/domestic-catalog/catalog.sqlite3 (repository root relative; rebuildable)',
        'counts':summary,'prior_demo':'../discovery-platform/model.json (v0.3 역사적 데모; 현재 국내 범위와 구분)'}
    dump(HERE/'model.json',model)
    db.close();print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':integrate()
