"""Verify catalog namespaces, current index and actual local search responses."""
from common import *
from urllib.parse import urlencode
from urllib.request import urlopen
import sqlite3

def request(params):
    with urlopen('http://127.0.0.1:8766/api/search?'+urlencode(params),timeout=60) as r:return json.load(r)

def main():
    checks=[]
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3',timeout=60)
    for portal,total in [('chungnam',4124),('jeonbuk',2233)]:
        actual=db.execute('SELECT count(*),count(DISTINCT dataset_key) FROM records WHERE portal_id=?',(portal,)).fetchone()
        check(portal+'_all_catalog_ids_in_db',actual==(total,total),list(actual))
        result=request({'portal':portal});check(portal+'_all_catalog_ids_in_http_search',result['total']==total)
    rid=db.execute("SELECT id FROM records WHERE portal_id='chungnam' AND dataset_key='3199'").fetchone()[0]
    result=request({'id':rid});fields=result['definitions']
    check('explicit_displayed_grid_fields_with_provenance_in_detail',len(fields)==4 and {f['name_en'] for f in fields}=={'yr','sigun','sx','nope'} and all(f['evidence_id']=='chungnam-schema-3199' and f['role']=='displayed_sheet_column' and f['raw_definition']['locator'] for f in fields))
    result=request({'portal':'chungnam','field':'선정 인원수','documented':'yes'})
    check('explicit_displayed_grid_column_searchable',any(r['id']==rid for r in result['results']))
    rid=db.execute("SELECT id FROM records WHERE portal_id='jeonbuk' AND dataset_key='15150560'").fetchone()[0]
    result=request({'id':rid});docs=result['schema_documents']
    check('multiple_file_versions_visible_without_schema_promotion',not result['definitions'] and any(len(d.get('resource_versions',[]))==2 for d in docs))
    result=request({'portal':'jeonbuk','documented':'yes'});check('metadata_only_jeonbuk_excluded_from_documented_filter',result['total']==0)
    refs=[]
    with gzip.open(HERE/'inventory/external-references.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            d=json.loads(line)
            if d['source_portal'] in ('chungnam','jeonbuk'):refs.append(d)
    check('new_source_links_in_frontier_without_semantic_identity_claim',bool(refs) and all(not d['same_dataset_asserted'] and not d['joinability_asserted'] and d['evidence_id'].startswith(d['source_portal']+'-schema-') for d in refs),{'observed_references':len(refs)})
    coverage=read(HERE/'coverage-report.json');index=read(HERE/'index-progress-report.json')
    check('new_index_has_no_orphan_definitions_or_parse_errors',not index['unmatched_definition_documents'] and not index['parse_errors'])
    check('national_completion_not_claimed',not coverage['all_domestic_portals_complete'] and not coverage['all_columns_complete'])
    db.close();report={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,'index_generated_at':index['generated_at'],'scope':'Current catalog SQLite index and actual localhost HTTP responses; not a full revalidation of all historical sources.'}
    dump(HERE/'provincial-import-check.json',report);print(json.dumps({'passed':report['passed'],'checks':len(checks),'failed':[c for c in checks if not c['passed']]},ensure_ascii=False),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
