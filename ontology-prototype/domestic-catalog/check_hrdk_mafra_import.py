from common import *
from urllib.parse import urlencode
import sqlite3

checks=[]
def ok(name,detail):
    checks.append({'name':name,'passed':True,'detail':detail});print(name,flush=True)
def query(**kw):
    with urlopen('http://127.0.0.1:8766/api/search?'+urlencode(kw),timeout=60) as r:return json.load(r)

r=query(portal='hrdk-api');assert r['total']==69;ok('http_hrdk_catalog_count',69)
r=query(portal='hrdk-api',documented='yes');assert r['total']==0;ok('hrdk_metadata_and_tools_do_not_inflate_columns',0)
r=query(portal='hrdk-api',field='careerQuery');assert r['total']==0;ok('mcp_input_is_not_a_dataset_output',0)
r=query(id='hrdk-api-data-go-link-15074415');assert r['definitions']==[] and r['schema_documents'];assert r['metadata']['external_reference_url']=='https://www.data.go.kr/data/15074415/openapi.do';ok('hrdk_detail_retains_official_referral',r['id'])
r=query(id='mafra-FILE-20141016000000000248');assert r['definitions']==[];d=next(x for x in r['schema_documents'] if x.get('preview_headers'));assert '메뉴명' in d['header_candidates'] and d['header_candidate_kind']=='public_file_preview_thead';title=r['title'];ok('http_detail_shows_file_version_and_cell_provenance',len(d['preview_headers']))
r=query(portal='mafra',q=title,field='메뉴명');assert r['total']>0;ok('exact_title_and_header_search_positive_control',r['total'])
r=query(portal='mafra',q=title,field='메뉴명',documented='yes');assert r['total']==0;ok('same_fixture_excluded_from_documented_filter',0)
exports=[]
with gzip.open(HERE/'inventory/csv-header-candidates.jsonl.gz','rt',encoding='utf-8') as f:
    for line in f:
        x=json.loads(line)
        if x['portal_id']=='mafra':exports.append(x)
assert exports and all(x['header_candidate_kind']=='public_file_preview_thead' and x['preview_headers'] for x in exports)
assert any(x['dataset_key']=='FILE-20141016000000000248' and '메뉴명' in x['header_candidates'] for x in exports)
ok('portable_export_preserves_multiple_preview_sources',len(exports))
c=read(HERE/'coverage-report.json');assert c['observed_header_candidate_occurrences']>c['csv_first_record_header_candidates'];ok('csv_and_all_header_candidate_counts_separated',{'csv':c['csv_first_record_header_candidates'],'all':c['observed_header_candidate_occurrences']})
refs=[]
with gzip.open(HERE/'inventory/external-references.jsonl.gz','rt',encoding='utf-8') as f:
    for line in f:
        x=json.loads(line)
        if x['source_portal']=='hrdk-api':refs.append(x)
assert len(refs)==69 and all(not x['same_dataset_asserted'] and not x['joinability_asserted'] for x in refs)
ok('frontier_contains_all_hrdk_referrals',69)
f=read(HERE/'hrdk-unresolved-target-check.json');assert len(f['targets'])==10 and all(x['http_status']==404 for x in f['targets']);ok('broken_links_preserved_as_observed_http_404',10)
i=read(HERE/'index-progress-report.json');assert not i['unmatched_definition_documents'] and not i['parse_errors'];ok('incremental_index_has_no_unmatched_or_parse_errors',i['generated_at'])
dump(HERE/'hrdk-mafra-import-check.json',{'generated_at':now(),'passed':True,'checks_passed':len(checks),'checks':checks,'coverage_snapshot':c['generated_at'],
    'source_scope':'HTTP fixtures, index and latest portable export, not all currently collected source files','all_columns_complete':False})
print('PASSED',len(checks),flush=True)
