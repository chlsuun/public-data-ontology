"""Index newly collected definitions without rebuilding or discarding catalog rows."""
from common import *
import argparse,sqlite3

DB=ROOT/'.local/domestic-catalog/catalog.sqlite3'

def index_once(export=False):
    db=sqlite3.connect(DB,timeout=60);db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS schema_documents(
        path TEXT PRIMARY KEY,portal_id TEXT,dataset_key TEXT,kind TEXT,status TEXT,
        field_count INTEGER,metadata_json TEXT,mtime_ns INTEGER,size INTEGER,evidence_id TEXT);
      CREATE TABLE IF NOT EXISTS schema_document_sources(path TEXT,record_id TEXT,evidence_id TEXT,
        PRIMARY KEY(path,record_id,evidence_id));
      CREATE INDEX IF NOT EXISTS schema_source_record ON schema_document_sources(record_id);
      CREATE INDEX IF NOT EXISTS record_portal_key ON records(portal_id,dataset_key,kind);
    ''')
    known={r[0]:(r[1],r[2]) for r in db.execute('SELECT path,mtime_ns,size FROM schema_documents')}
    changed=0;unmatched=[];errors=[]
    for path in (HERE/'definitions').glob('*.json'):
        st=path.stat();relative=path.name
        if known.get(relative)==(st.st_mtime_ns,st.st_size):continue
        try:d=read(path)
        except (ValueError,OSError) as exc:errors.append({'path':relative,'error':str(exc)[:150]});continue
        kind=d.get('dataset_kind') or ('FILE' if d['portal_id']=='data-go' else None)
        query='SELECT id FROM records WHERE portal_id=? AND dataset_key=?';args=[d['portal_id'],d['dataset_key']]
        if kind:query+=' AND kind=?';args.append(kind)
        ids=[r[0] for r in db.execute(query,args)]
        if not ids:unmatched.append(relative);continue
        for rid,eid in db.execute('SELECT record_id,evidence_id FROM schema_document_sources WHERE path=?',(relative,)).fetchall():
            db.execute('DELETE FROM documented_fields WHERE record_id=? AND evidence_id=?',(rid,eid))
        db.execute('DELETE FROM schema_document_sources WHERE path=?',(relative,))
        default_eid=d['evidence_id']
        sources=set()
        for rid in ids:
            for pos,f in enumerate(d.get('fields',[]),1):
                norm=lambda v:None if v in ('','-',None) else v
                eid=f.get('evidence_id') or default_eid;url=d['source_url']
                if eid!=default_eid:
                    receipt=HERE/'evidence'/(eid+'.json')
                    if receipt.exists():url=read(receipt)['requested_url']
                item={'record_id':rid,'ordinal':pos,'name':norm(f.get('name')),
                    'name_en':norm(f.get('name_en')),'description':norm(f.get('description')),
                    'datatype':norm(f.get('datatype')),'unit':norm(f.get('unit')),
                    'evidence_id':eid,'source_url':url,'role':f.get('role','documented_column'),
                    'status':'definition_observed_not_data_validated','raw_definition':f}
                db.execute('INSERT OR REPLACE INTO documented_fields VALUES(?,?,?,?,?,?,?,?,?)',
                    (rid,pos,item['name'],item['name_en'],item['description'],item['datatype'],item['unit'],json.dumps(item,ensure_ascii=False),eid))
                sources.add((relative,rid,eid))
            sources.add((relative,rid,default_eid))
        db.executemany('INSERT OR IGNORE INTO schema_document_sources VALUES(?,?,?)',sources)
        metadata={k:v for k,v in d.items() if k!='fields'}
        db.execute('INSERT OR REPLACE INTO schema_documents VALUES(?,?,?,?,?,?,?,?,?,?)',
            (relative,d['portal_id'],d['dataset_key'],kind,d['status'],len(d.get('fields',[])),
             json.dumps(metadata,ensure_ascii=False),st.st_mtime_ns,st.st_size,default_eid))
        changed+=1
        if changed%100==0:db.commit()
    db.commit()
    counts=[]
    for portal,n,keys,providers in db.execute('SELECT portal_id,count(*),count(distinct dataset_key),count(distinct provider_id) FROM records GROUP BY portal_id'):
        tokens=db.execute("SELECT count(*) FROM fields JOIN records r ON r.id=fields.record_id WHERE r.portal_id=? AND role='output'",(portal,)).fetchone()[0]
        fields,records=db.execute('SELECT count(*),count(distinct d.record_id) FROM documented_fields d JOIN records r ON r.id=d.record_id WHERE r.portal_id=?',(portal,)).fetchone()
        source_fields=db.execute('SELECT coalesce(sum(field_count),0) FROM schema_documents WHERE portal_id=?',(portal,)).fetchone()[0]
        counts.append({'portal_id':portal,'catalog_records':n,'distinct_catalog_keys':keys,
            'provider_codes_in_source_namespace':providers,'declared_output_tokens':tokens,
            'documented_columns':fields,'records_with_documented_columns':records,
            'records_without_documented_columns':n-records,'fields_in_source_definition_documents':source_fields})
    coverage=read(HERE/'coverage-report.json')
    coverage.update(generated_at=now(),portal_counts=counts,portals_with_catalog_acquisition=len(counts),
        total_catalog_records=sum(x['catalog_records'] for x in counts),
        distinct_catalog_keys_across_portal_namespaces=sum(x['distinct_catalog_keys'] for x in counts),
        documented_column_occurrences=sum(x['documented_columns'] for x in counts),
        fields_in_source_definition_documents=sum(x['fields_in_source_definition_documents'] for x in counts),
        declared_output_tokens=sum(x['declared_output_tokens'] for x in counts),
        all_domestic_portals_complete=False,all_columns_complete=False,
        count_note='명세 항목에는 통계 분류·측정 항목·기간과 API 응답 제어 필드가 포함되며 출처별 중복이 있다.')
    coverage['field_count_distinction']='fields_in_source_definition_documents는 명세 문서별 항목 합계이며 의미상 중복 제거 전이다. documented_column_occurrences는 동일 표준 명세를 제공기관별 등록정보에 연결한 반복까지 포함한다.'
    coverage['observed_header_candidate_occurrences']=db.execute("SELECT coalesce(sum(json_array_length(metadata_json,'$.header_candidates')),0) FROM schema_documents").fetchone()[0]
    coverage['csv_first_record_header_candidates']=db.execute("SELECT coalesce(sum(json_array_length(metadata_json,'$.header_candidates')),0) FROM schema_documents WHERE json_extract(metadata_json,'$.header_candidate_kind') IS NULL OR json_extract(metadata_json,'$.header_candidate_kind')='csv_first_record'").fetchone()[0]
    registry=read(HERE/'inventory/domestic-portals.json');by_id={x['portal_id']:x for x in counts}
    coverage['registered_portal_candidates']=len(registry['portals'])
    dump(HERE/'coverage-report.json',coverage)
    for p in registry['portals']:
        if p['id'] in by_id:
            p['current_collection']=by_id[p['id']];p['collection_status']='catalog_acquired_columns_partial'
    dump(HERE/'inventory/domestic-portals.json',registry)
    providers=[]
    for pid,name,portal,n in db.execute('SELECT provider_id,min(provider_name),portal_id,count(*) FROM records WHERE provider_id IS NOT NULL GROUP BY portal_id,provider_id ORDER BY portal_id,provider_id'):
        providers.append({'id':pid,'name_as_reported':name,'portal_id':portal,'catalog_records':n,
            'cross_portal_organization_identity':'not_reconciled'})
    dump(HERE/'inventory/providers.json',providers)
    model=read(HERE/'model.json');model['counts']=coverage;model['version']='0.5.1'
    model['completion_policy']='completion-policy.json'
    model['collection_progress']='*-collection-report.json (queues and full completion are separate)'
    model['instance_files']['catalogs']=sorted(set(model['instance_files']['catalogs'])|{
        'inventory/'+p.name for p in (HERE/'inventory').glob('*-catalog-records.jsonl.gz')})
    model['instance_files']['observed_external_references']='inventory/external-references.jsonl.gz'
    model['instance_files']['csv_header_candidates']='inventory/csv-header-candidates.jsonl.gz'
    model['provider_discovery_frontier']='inventory/provider-discovery-frontier.json'
    dump(HERE/'model.json',model)
    if export:
        dest=HERE/'inventory/documented-columns.jsonl.gz';tmp=dest.with_suffix('.gz.tmp')
        with gzip.open(tmp,'wt',encoding='utf-8') as out:
            for (data,) in db.execute('SELECT definition_json FROM documented_fields ORDER BY record_id,evidence_id,ordinal'):out.write(data+'\n')
        tmp.replace(dest)
        dest=HERE/'inventory/csv-header-candidates.jsonl.gz';tmp=dest.with_suffix('.gz.tmp')
        with gzip.open(tmp,'wt',encoding='utf-8') as out:
            for portal,key,metadata in db.execute("SELECT portal_id,dataset_key,metadata_json FROM schema_documents WHERE json_array_length(metadata_json,'$.header_candidates')>0"):
                d=json.loads(metadata)
                out.write(json.dumps({'portal_id':portal,'dataset_key':key,'header_candidates':d['header_candidates'],
                    'evidence_id':d.get('header_evidence_id',d.get('evidence_id')),'source_url':d['source_url'],
                    'header_candidate_kind':d.get('header_candidate_kind','csv_first_record'),
                    'preview_headers':d.get('preview_headers'),
                    'status':'header_candidates_not_schema_verified'},ensure_ascii=False)+'\n')
        tmp.replace(dest)
    report={'generated_at':now(),'changed_documents':changed,'unmatched_definition_documents':unmatched,
        'parse_errors':errors,'documented_field_occurrences':coverage['documented_column_occurrences'],
        'portable_columns_exported':export,'all_columns_complete':False}
    dump(HERE/'index-progress-report.json',report);db.close();print(json.dumps(report,ensure_ascii=False),flush=True)
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--watch',action='store_true');ap.add_argument('--interval',type=int,default=300);args=ap.parse_args()
    last_export=float('-inf')
    while True:
        do_export=time.monotonic()-last_export>3600
        report=index_once(do_export)
        if report['changed_documents'] or do_export:
            import importlib,write_report,build_frontier
            importlib.reload(write_report).main();importlib.reload(build_frontier).main()
        if do_export:last_export=time.monotonic()
        if not args.watch:break
        if (ROOT/'.local/domestic-catalog/indexer.stop').exists():break
        time.sleep(max(60,args.interval))

if __name__=='__main__':main()
