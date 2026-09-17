"""Check real local search after SGIS and Chungnam operation imports."""
from common import *
from urllib.request import urlopen
from urllib.parse import urlencode
import sqlite3

def request(params):
    with urlopen('http://127.0.0.1:8766/api/search?'+urlencode(params),timeout=60) as r:return json.load(r)

def main():
    checks=[]
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3',timeout=60)
    check('sgis_all_68_catalog_records_searchable',request({'portal':'sgis'})['total']==68)
    actual=db.execute("SELECT count(*) FROM documented_fields f JOIN records r ON r.id=f.record_id WHERE r.portal_id='sgis'").fetchone()[0]
    check('sgis_all_618_response_fields_in_index',actual==618,actual)
    population=request({'id':'sgis-data-guide-4'});fs=population['definitions'];source=read(HERE/'definitions/sgis-schema-data-guide-4.json')
    check('sgis_population_fields_have_source_table_coordinates',len(fs)==len(source['fields']) and all(f['evidence_id']=='sgis-data-api-guide' and f['raw_definition']['guide_anchor']=='4' and f['raw_definition']['locator'] for f in fs))
    mixed=next(f for f in fs if f['name']=='naesuoga_ppltn')
    check('sgis_non_type_value_not_fabricated_as_datatype',mixed['datatype'] is None and mixed['raw_definition']['source_value_or_type']=='외각 공간 속성정보를 제공')
    js=request({'id':'sgis-data-guide-2'})
    check('javascript_artifact_visible_but_not_a_column',not js['definitions'] and any(d.get('response_artifacts') for d in js['schema_documents']))
    result=request({'portal':'sgis','field':'consumer_secret','documented':'yes'})
    check('request_credential_parameter_not_indexed_as_response',result['total']==0)
    docs=[read(p) for p in (HERE/'definitions').glob('chungnam-operations-*.json')]
    expected=sum(len(d['fields']) for d in docs);eids=sorted({f['evidence_id'] for d in docs for f in d['fields']})
    actual=db.execute('SELECT count(*) FROM documented_fields WHERE evidence_id IN ('+','.join('?' for _ in eids)+')',eids).fetchone()[0]
    check('chungnam_all_saved_operation_fields_in_index',actual==expected==3246,{'expected':expected,'indexed':actual})
    result=request({'id':'chungnam-publicdatapk-15157561'});fs=result['definitions']
    check('chungnam_request_and_generic_elements_excluded_from_output',len(fs)==18 and not ({'serviceKey','header','body','items','item'} & {f['name_en'] for f in fs}) and all(f['evidence_id']=='chungnam-entity-metadata-probe-15157561' for f in fs))
    result=request({'id':'chungnam-publicdatapk-15001170'})
    check('repeated_tabs_do_not_duplicate_imported_fields',len(result['definitions'])==16 and any(len(d.get('operations',[]))==4 and sum(len(o['tab_occurrences']) for o in d['operations'])==16 for d in result['schema_documents']))
    index=read(HERE/'index-progress-report.json');check('index_has_no_unmatched_documents_or_parse_errors',not index['unmatched_definition_documents'] and not index['parse_errors'])
    c=read(HERE/'coverage-report.json');check('completion_flags_remain_false',not c['all_columns_complete'] and not c['all_domestic_portals_complete'])
    db.close();report={'checked_at':now(),'index_generated_at':index['generated_at'],'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'New SGIS and Chungnam function schemas in SQLite and actual localhost HTTP responses. No full historical-source or statistical validation claim.'}
    dump(HERE/'sgis-chungnam-import-check.json',report);print(json.dumps({'passed':report['passed'],'checks':len(checks),'failures':[c for c in checks if not c['passed']]},ensure_ascii=False),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
