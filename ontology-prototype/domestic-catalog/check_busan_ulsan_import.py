"""Local DB, HTTP and reference checks for the newly added portal catalogs."""
from common import *
from urllib.request import urlopen
from urllib.parse import urlencode
from check_busan_ulsan import source
import sqlite3,re

def get(route,params=None):
    url='http://127.0.0.1:8766'+route+('?' + urlencode(params) if params else '')
    with urlopen(url,timeout=60) as response:return json.load(response)

def main():
    checks=[];db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3')
    def check(name,ok,details=None):checks.append(dict(name=name,passed=bool(ok),details=details))
    for portal,expected in [('busan',12551),('ulsan',2582)]:
        n=db.execute('SELECT count(*) FROM records WHERE portal_id=?',(portal,)).fetchone()[0]
        check(portal+'_catalog_import_count',n==expected,dict(records=n))
        n=db.execute('SELECT count(*) FROM documented_fields d JOIN records r ON r.id=d.record_id WHERE r.portal_id=?',(portal,)).fetchone()[0]
        check(portal+'_unverified_metadata_not_promoted_to_columns',n==0)
    detail=get('/api/search',{'id':'busan-15004511'})
    docs=detail['schema_documents'];lists=[q for d in docs for q in d.get('declared_parameter_lists',[])]
    check('busan_http_detail_keeps_candidates_separate',not detail['definitions'] and bool(lists) and all(q['status']=='flattened_parameters_not_verified_schema' for q in lists))
    term=lists[0]['response_name_candidates'][0]
    hit=get('/api/search',{'portal':'busan','field':term})
    check('busan_candidate_field_search_works',hit['total']>0,dict(term=term,total=hit['total']))
    hit=get('/api/search',{'portal':'busan','field':term,'documented':'yes'})
    check('busan_documented_filter_excludes_candidates',hit['total']==0)
    rows=read(HERE/'inventory/ulsan-catalog.json');row=next(x for x in rows if x['source_catalog_tab']=='API')
    detail=get('/api/search',{'id':row['id']})
    check('ulsan_http_preserves_reference_and_row_identity',detail['metadata']['external_reference_url']==row['external_reference_url'] and not detail['definitions'] and not detail['metadata']['same_dataset_asserted'])
    with gzip.open(HERE/'inventory/external-references.jsonl.gz','rt',encoding='utf-8') as f:
        refs=[json.loads(line) for line in f]
    busan=[r for r in refs if r['source_portal']=='busan'];failures=[]
    for r in busan:
        raw,_=source(r['evidence_id']);obj=json.loads(raw)
        m=re.fullmatch(r'(opendata|fileList)\[(\d+)\]\.(metaUrl|guideUrl|linkUrl|downurl)',r['locator'])
        if not m or obj[m[1]][int(m[2])].get(m[3])!=r['target_url']:failures.append(r['id'])
    check('busan_reference_locator_uses_actual_preview_receipt',bool(busan) and not failures,dict(references_checked=len(busan),failures=failures))
    ulsan=[r for r in refs if r['source_portal']=='ulsan']
    check('ulsan_all_catalog_referrals_exported_without_identity_claim',len(ulsan)==2582 and all(not r['same_dataset_asserted'] and not r['joinability_asserted'] for r in ulsan),dict(references=len(ulsan)))
    coverage=get('/api/coverage')
    check('http_coverage_includes_both_portals_and_stays_incomplete',{'busan','ulsan'}<={x['portal_id'] for x in coverage['portal_counts']} and not coverage['all_columns_complete'] and not coverage['all_domestic_portals_complete'])
    with urlopen('http://127.0.0.1:8766/',timeout=10) as response:html=response.read().decode('utf-8')
    check('browser_has_new_portal_and_progress_labels','부산 Big-데이터웨이브' in html and '울산광역시 데이터포털' in html and 'busan-collection-report.json' in html and 'ulsan-collection-report.json' in html)
    result={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,
        'scope':'New portal import, candidate-only search behavior and observed reference provenance. Last full national import/hash check remains the separately timestamped validation report.'}
    dump(HERE/'busan-ulsan-import-check.json',result)
    print(json.dumps({'passed':result['passed'],'checks':len(checks),'failed':[c for c in checks if not c['passed']]},ensure_ascii=False),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
