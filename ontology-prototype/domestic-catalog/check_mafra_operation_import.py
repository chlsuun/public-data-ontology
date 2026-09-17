"""Check function variants survive import, without retaining duplicate defaults."""
from common import *
from urllib.request import urlopen
from urllib.parse import urlencode
import sqlite3

def main():
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3');checks=[]
    def check(name,ok,details=None):checks.append(dict(name=name,passed=bool(ok),details=details))
    ops=read(HERE/'mafra-operations-collection-report.json');failures=[];count=0
    for path in (HERE/'definitions').glob('mafra-schema-OPENAPI-*.json'):
        d=read(path);rid='mafra-'+d['dataset_key']
        actual=[json.loads(x[0]) for x in db.execute('SELECT definition_json FROM documented_fields WHERE record_id=? ORDER BY ordinal',(rid,))]
        expected=[(n,f.get('evidence_id',d['evidence_id']),f) for n,f in enumerate(d['fields'],1)]
        observed=[(f['ordinal'],f['evidence_id'],f['raw_definition']) for f in actual]
        if expected!=observed:failures.append(rid)
        count+=len(actual)
    check('all_mafra_api_fields_match_saved_source_definitions',not failures and count==ops['api_definition_total_fields_after_expansion'],dict(fields_checked=count,failures=failures))
    stale=[]
    for key in ops['expanded_api_ids']:
        n=db.execute('SELECT count(*) FROM documented_fields WHERE record_id=? AND evidence_id=?',('mafra-'+key,'mafra-schema-'+key)).fetchone()[0]
        if n:stale.append(key)
    check('initial_default_fields_not_counted_twice',not stale,dict(expanded_apis=len(ops['expanded_api_ids']),stale=stale))
    check('mafra_index_count_matches_coverage',next(p['documented_columns'] for p in read(HERE/'coverage-report.json')['portal_counts'] if p['portal_id']=='mafra')==count)
    for key,expected,functions in [('OPENAPI-20161121000000000611',21,{'1','2'}),('OPENAPI-20221205000000002360',78,{'1','2','4'})]:
        url='http://127.0.0.1:8766/api/search?'+urlencode({'id':'mafra-'+key})
        with urlopen(url,timeout=30) as response:result=json.load(response)
        fields=result['definitions']
        check('http_function_provenance_'+key,len(fields)==expected and {f['raw_definition']['source_function_id'] for f in fields}==functions,
            dict(fields_returned=len(fields)))
    result={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'Post-expansion MAFRA function import and local HTTP detail results; general 58-check validation is a separate earlier snapshot.'}
    dump(HERE/'mafra-operation-import-check.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
