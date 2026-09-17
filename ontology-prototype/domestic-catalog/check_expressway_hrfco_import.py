"""Verify the completed new source slice in SQLite and the running HTTP browser."""
from common import *
from urllib.request import urlopen
from urllib.parse import urlencode
from collections import Counter
import sqlite3

def main():
    checks=[]
    def check(name,value,detail=None):
        checks.append({'name':name,'passed':bool(value),'detail':detail})
        if not value:raise AssertionError(name)
    def http(**params):
        with urlopen('http://127.0.0.1:8766/api/search?'+urlencode(params),timeout=30) as r:return json.load(r)
    db=sqlite3.connect((ROOT/'.local/domestic-catalog/catalog.sqlite3').as_uri()+'?mode=ro',uri=True)
    paths=list((HERE/'definitions').glob('expressway-schema-*.json'))+list((HERE/'definitions').glob('hrfco-schema-*.json'))
    portable=[];links={}
    for path in paths:
        d=read(path);row=db.execute('SELECT field_count,metadata_json FROM schema_documents WHERE path=?',(path.name,)).fetchone()
        assert row is not None,path.name
        assert json.loads(row[1])=={k:v for k,v in d.items() if k!='fields'},path.name
        assert row[0]==len(d['fields'])
        rid=d['portal_id']+'-'+d['dataset_key']
        actual=[json.loads(x[0]) for x in db.execute('SELECT definition_json FROM documented_fields WHERE record_id=? AND evidence_id=? ORDER BY ordinal',(rid,d['evidence_id']))]
        assert [x['raw_definition'] for x in actual]==d['fields'],path.name
        portable.extend(actual)
        for link in d.get('outgoing_links',[]):
            k=(d['portal_id'],d['dataset_key'],link['url'])
            links.setdefault(k,set()).add((link.get('evidence_id',d['evidence_id']),link['locator']))
    check('all_new_definition_metadata_and_fields_match_source_files',len(paths)==730 and len(portable)==1932,{'documents':len(paths),'fields':len(portable)})
    check('new_record_counts_match_live_http',http(portal='expressway')['total']==527 and http(portal='hrfco')['total']==9)
    check('documented_filter_excludes_candidates_and_metadata_only_registrations',http(portal='expressway',documented='yes')['total']==149 and http(portal='hrfco',documented='yes')['total']==9)
    x=http(id='expressway-884');d=next(d for d in x['schema_documents'] if 'api_id' in d)
    check('blank_flag_rows_visible_as_unclassified_without_silent_repair',len(d['unclassified_schema_rows'])==15 and d['status']=='response_definition_observed_partial' and len(x['definitions'])==3)
    x=http(id='expressway-1')
    check('file_column_definition_and_version_metadata_coexist_without_deletion',len(x['definitions'])==15 and len(x['schema_documents'])==2 and any(d.get('file_versions') for d in x['schema_documents']))
    x=http(id='expressway-144');d=next(d for d in x['schema_documents'] if d.get('header_candidates'))
    check('sample_header_candidates_visible_without_becoming_formal_columns',len(x['definitions'])==0 and len(d['header_candidates'])==14 and d['header_candidate_kind']=='public_html_sample_header')
    x=http(id='expressway-787');d=x['schema_documents'][0]
    check('lod_listing_header_role_and_control_warning_preserved',not x['definitions'] and d['header_candidate_kind']=='public_html_listing_header' and d['preview_headers'][0]['listing_controls_may_be_included'])
    x=http(id='hrfco-dam-info')
    check('source_description_mismatch_and_literal_units_survive_http_import',any(f['name_en']=='OBSNM' and '강수량' in f['description'] for f in x['definitions']) and any(f['unit'] for f in http(id='hrfco-dam-list')['definitions']))
    check('hrfco_request_auth_parameter_not_promoted_to_response_search',http(portal='hrfco',field='ServiceKey')['total']==0)
    refs=[]
    with gzip.open(HERE/'inventory/external-references.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            x=json.loads(line)
            if x['source_portal']=='expressway':refs.append(x)
    actual={(r['source_portal'],r['source_dataset_key'],r['target_url']) for r in refs}
    check('all_external_references_have_valid_source_positions_without_identity_claims',actual==set(links) and all((r['evidence_id'],r['locator']) in links[(r['source_portal'],r['source_dataset_key'],r['target_url'])] and not r['same_dataset_asserted'] and not r['joinability_asserted'] for r in refs),len(refs))
    with urlopen('http://127.0.0.1:8766/',timeout=30) as r:html=r.read().decode()
    check('browser_serves_new_portal_and_progress_labels',all(s in html for s in ("expressway:'고속도로 공공데이터 포털'","hrfco:'한강홍수통제소 Open API'",'expressway-files-collection-report.json','hrfco-collection-report.json')))
    m=read(HERE/'model.json');registry=read(HERE/'inventory/domestic-portals.json')
    check('model_qa_files_exist_and_national_completion_stays_false',all((HERE/m['instance_files'][k]).exists() for k in ('expressway_source_qa','hrfco_source_qa','water_source_access_qa')) and not registry['national_census_complete'] and not m['counts']['all_columns_complete'])
    # Export only this stable slice, leaving the live hourly aggregate export to its single owner.
    dest=HERE/'inventory/expressway-hrfco-columns-snapshot.jsonl.gz'
    with gzip.open(dest,'wt',encoding='utf-8') as f:
        for row in sorted(portable,key=lambda x:(x['record_id'],x['evidence_id'],x['ordinal'])):f.write(json.dumps(row,ensure_ascii=False)+'\n')
    with gzip.open(dest,'rt',encoding='utf-8') as f:exported=[json.loads(line) for line in f]
    check('stable_expansion_export_equals_sqlite_without_changing_hourly_aggregate',exported==sorted(portable,key=lambda x:(x['record_id'],x['evidence_id'],x['ordinal'])),len(exported))
    report={'generated_at':now(),'passed':all(x['passed'] for x in checks),'checks_passed':len(checks),'checks':checks,
        'coverage_snapshot':read(HERE/'coverage-report.json')['generated_at'],'expansion_export':str(dest.relative_to(HERE)),
        'aggregate_portable_export_can_lag_live_sqlite':True,'all_columns_complete':False,
        'scope':'This new stable source slice in SQLite and live HTTP; no global recertification of concurrently growing sources'}
    dump(HERE/'expressway-hrfco-import-check.json',report);db.close()
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
