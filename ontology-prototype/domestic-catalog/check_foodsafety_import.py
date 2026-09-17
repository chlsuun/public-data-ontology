from common import *
from urllib.parse import urlencode
import sqlite3

db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3');checks=[]
def ok(name,detail):checks.append({'name':name,'passed':True,'detail':detail});print(name,flush=True)
def query(**kw):
    with urlopen('http://127.0.0.1:8766/api/search?'+urlencode(kw),timeout=60) as r:return json.load(r)

count,fields=db.execute("SELECT count(*),sum(field_count) FROM schema_documents WHERE portal_id='foodsafety'").fetchone()
assert (count,fields)==(178,1861),('Wait for current indexer',count,fields)
ok('all_foodsafety_source_documents_indexed',(count,fields))
assert db.execute("SELECT count(*) FROM documented_fields f JOIN records r ON r.id=f.record_id WHERE r.portal_id='foodsafety'").fetchone()[0]==1861
ok('physical_index_matches_source_field_count_without_duplicates',1861)
r=query(portal='foodsafety');assert r['total']==178;ok('http_catalog_has_178_registrations',178)
r=query(portal='foodsafety',documented='yes');assert r['total']==169;ok('http_documented_filter_excludes_files_and_link',169)
r=query(id='foodsafety-I0600');assert len(r['definitions'])==5 and any(x['name_en']=='EDC_INSTT_APPN_NO' for x in r['definitions'])
d=next(x for x in r['schema_documents'] if x.get('request_parameters'))
assert len(d['response_table_occurrences'])==2 and d['response_table_occurrences'][1]['exact_duplicate_table'] and d['source_notice_references']
ok('detail_keeps_duplicate_table_and_policy_evidence_without_double_counting',5)
r=query(id='foodsafety-I1140');assert r['definitions']==[] and any(x.get('file_metadata_tables') for x in r['schema_documents']);ok('file_page_has_version_metadata_but_no_fabricated_columns',r['id'])
r=query(portal='foodsafety',field='EDC_INSTT_APPN_NO');assert r['total']>=1;ok('official_response_column_is_searchable',r['total'])
r=query(portal='foodsafety',field='keyId',documented='yes');assert r['total']==0;ok('authentication_input_not_mixed_into_output_columns',0)
r=query(id='foodsafety-I2791');assert r['definitions']==[] and r['schema_documents'][0]['outgoing_links'][0]['url']=='https://www.data.go.kr/data/15127578/openapi.do';ok('link_only_registration_preserves_actual_external_destination',r['id'])
count,cells=db.execute("SELECT count(*),sum(json_array_length(metadata_json,'$.header_candidates')) FROM schema_documents WHERE path LIKE 'mafra-file-previews-%'").fetchone()
assert (count,cells)==(459,16990);ok('all_finished_mafra_preview_candidates_indexed',(count,cells))
assert db.execute("SELECT coalesce(sum(field_count),0) FROM schema_documents WHERE path LIKE 'mafra-file-previews-%'").fetchone()[0]==0
ok('mafra_candidates_did_not_inflate_documented_field_count',0)
report={'generated_at':now(),'passed':True,'checks_passed':len(checks),'checks':checks,'coverage_snapshot':read(HERE/'coverage-report.json')['generated_at'],'all_columns_complete':False,
 'portable_export_scope_note':'These tests validate SQLite and live HTTP. They do not certify a later hourly portable export.'}
dump(HERE/'foodsafety-mafra-import-check.json',report);print('PASSED',len(checks))
