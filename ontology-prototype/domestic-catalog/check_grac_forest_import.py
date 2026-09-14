"""Check the source expansion through the running read-only search API and DB."""
from common import *
from urllib.parse import urlencode
from collections import Counter
import sqlite3

db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3',timeout=60);checks=[]

def query(**kw):
    with urlopen('http://127.0.0.1:8766/api/search?'+urlencode(kw),timeout=60) as r:return json.load(r)

def ok(name,detail):checks.append({'name':name,'passed':True,'detail':detail});print(name,flush=True)

for portal,n,fields in [('grac',2,24),('forest',75,217)]:
    assert db.execute('SELECT count(*),sum(field_count) FROM schema_documents WHERE portal_id=?',(portal,)).fetchone()==(n,fields)
    assert db.execute('SELECT count(*) FROM documented_fields f JOIN records r ON r.id=f.record_id WHERE r.portal_id=?',(portal,)).fetchone()[0]==fields
ok('all_77_new_documents_and_241_api_or_file_fields_indexed_without_extra_copies',77)
assert query(portal='grac')['total']==2 and query(portal='forest')['total']==56
ok('live_http_catalog_counts_match_source_registrations',58)
assert query(portal='grac',documented='yes')['total']==2 and query(portal='forest',documented='yes')['total']==15
ok('documented_filter_excludes_41_forest_guides_or_links_without_schema',17)
r=query(id='grac-game');d=r['schema_documents'][0]
assert len(r['definitions'])==15 and len(d['request_parameters'])==8 and len(d['structural_elements'])==2
assert d['documentation_examples'][0]['xml_parse_status']=='malformed_documentation_xml' and d['issues']
assert any(f['name_en']=='canceledddate' for f in r['definitions'])
ok('game_detail_preserves_xml_errors_raw_names_and_separate_inputs',15)
assert query(portal='grac',field='canceledddate')['total']==1
assert query(portal='grac',field='canceleddate')['total']==0
assert query(portal='grac',field='resultItem')['total']==0
ok('source_typo_searches_and_sample_only_names_do_not_create_columns',3)
r=query(id='grac-recruit');d=r['schema_documents'][0]
assert len(r['definitions'])==9 and d['definition_tables'][1]['headers'][0]=='요청변수'
assert [x['name_en'] for x in d['structural_elements']]==['result','result']
ok('recruit_conflicting_header_and_repeated_structure_rows_are_visible',9)
r=query(id='forest-PBD0000022');d=next(x for x in r['schema_documents'] if x.get('request_parameters'))
assert len(r['definitions'])==27 and len(d['request_parameters'])==5 and d['parser_version']==2
assert next(f for f in r['definitions'] if f['name_en']=='regDate')['datatype']=='Int'
assert all(f['unit'] is None for f in r['definitions'])
ok('forest_detail_preserves_source_date_type_without_guessing_units',27)
assert query(portal='forest',field='serviceKey',documented='yes')['total']==0
ok('forest_authentication_input_excluded_from_response_search',0)
r=query(id='forest-PBD0000059');d=next(x for x in r['schema_documents'] if 'public_usage_note_candidates' in x)
assert len(r['definitions'])==5 and all(x['role']=='documented_file_layer_attribute' for x in r['definitions'])
assert any('비영리' in n['text_as_reported'] for n in d['public_usage_note_candidates'])
assert all(not n['license_or_reuse_approval_inferred'] for n in d['public_usage_note_candidates'])
ok('map_attributes_come_from_dictionary_and_usage_note_is_separate',r['id'])
refs=read(HERE/'inventory/forest-data-go-reference-resolution.json')['references']
for ref in refs:
    r=query(id=ref['source_record_id']);assert not r['definitions']
    assert any(x['url']==ref['target_url_as_reported'] for d in r['schema_documents'] for x in d['outgoing_links'])
    assert not ref['source_schema_copied'] and not ref['semantic_equivalence_approved'] and not ref['joinability_approved']
    assert all(db.execute('SELECT 1 FROM records WHERE id=?',(x['record_id'],)).fetchone() for x in ref['existing_catalog_matches'])
ok('nine_existing_data_go_references_resolve_without_copying_target_fields',9)
expected={}
for p in (HERE/'definitions').glob('forest-schema-*.json'):
    d=read(p)
    for l in d.get('outgoing_links',[]):expected.setdefault(uid('external-ref','forest',d['dataset_key'],l['url']),[]).append((d,l))
observed={}
with gzip.open(HERE/'inventory/external-references.jsonl.gz','rt',encoding='utf-8') as inp:
    for line in inp:
        x=json.loads(line)
        if x['source_portal']=='forest':observed[x['id']]=x
assert observed.keys()==expected.keys(),('Wait for frontier refresh',len(observed),len(expected))
for key,source_occurrences in expected.items():
    x=observed[key]
    assert any(x['evidence_id']==l.get('evidence_id',d['evidence_id']) and x['target_url']==l['url'] and x['locator']==l['locator'] for d,l in source_occurrences)
    assert not x['same_dataset_asserted'] and not x['joinability_asserted']
ok('all_distinct_forest_external_links_have_a_valid_original_evidence_in_frontier',
   {'distinct_references':len(expected),'source_link_occurrences':sum(len(x) for x in expected.values()),
    'additional_source_locations_remain_in_definition_documents':True})
with urlopen('http://127.0.0.1:8766/',timeout=20) as r:html=r.read().decode()
assert '게임물관리위원회 Open API' in html and '산림청 공공데이터 개방목록' in html
assert '파일·공개 미리보기의 머리글 후보' in html
ok('browser_labels_and_preview_candidate_wording_cover_new_sources',3)
model=read(HERE/'model.json');registry=read(HERE/model['instance_files']['portals'])
assert all(p['catalog_collected'] and not p['all_portal_columns_collected'] for p in registry['portals'] if p['id'] in ('grac','forest'))
assert not model['counts']['all_columns_complete'] and not registry['national_census_complete']
for key in ['grac_source_qa','forest_source_qa','forest_registration_reference_resolution','forest_navigation_observations','grac_disclosure_navigation']:
    assert (HERE/model['instance_files'][key]).is_file()
ok('model_registry_source_qa_links_exist_and_completeness_remains_false',5)
db.close()
dump(HERE/'grac-forest-import-check.json',{'generated_at':now(),'passed':True,'checks_passed':len(checks),'checks':checks,
    'coverage_snapshot':read(HERE/'coverage-report.json')['generated_at'],'all_columns_complete':False,
    'scope':'These new source registrations in SQLite and live local HTTP; not a full recertification of all continuously growing sources'})
print('PASSED',len(checks))
