"""Check the finite public catalog/document snapshot against original receipts."""
from common import *
from collections import Counter
import re

checks=[];receipts={};soups={}
def original(eid):
    if eid not in receipts:
        r=read(HERE/'evidence'/(eid+'.json'));assert r['status']=='fetched',eid
        b=gzip.decompress((HERE/r['raw_file']).read_bytes());assert len(b)==r['bytes'] and sha256(b).hexdigest()==r['sha256']
        receipts[eid]=(b,r)
    return receipts[eid]
def soup(eid):
    if eid not in soups:soups[eid]=BeautifulSoup(original(eid)[0],'html.parser')
    return soups[eid]
def ok(name,detail):checks.append({'name':name,'passed':True,'detail':detail})

items=read(HERE/'inventory/foodsafety-catalog.json');report=read(HERE/'foodsafety-catalog-report.json');summary=read(HERE/'foodsafety-definition-summary.json')
assert len(items)==len({x['dataset_key'] for x in items})==178
assert sum(p['rows'] for p in report['page_receipts'])==report['source_reported_total']==178
for c in items:
    data=json.loads(original(c['evidence_id'])[0]);pos=int(re.search(r'\[(\d+)\]',c['locator'])[1]);s=data['list'][pos]
    assert s==c['source_catalog_record'] and s['svc_no']==c['dataset_key'] and s['svc_nm']==c['title']
    assert data['total_cnt']==178 and int(s['no'])==(c['source_page']-1)*50+pos+1
    assert c['provider_name']==(s['provd_instt_nm'] or None)
    assert c['provider_id']==('foodsafety:org:'+s['provd_instt'] if s['provd_instt'] else None)
ok('catalog_total_all_four_pages_source_rows_and_namespace',178)
ids=[]
for p in read(HERE/'foodsafety-catalog-crosscheck.json')['page_receipts']:
    data=json.loads(original(p['evidence_id'])[0]);assert data['total_cnt']==169;ids.extend(x['svc_no'] for x in data['list'])
assert len(ids)==len(set(ids))==169
assert set(ids)=={x['dataset_key'] for x in items if x['source_service_types']==['API']}
ok('independent_api_filter_matches_unfiltered_catalog',169)
assert 'I-0050' in {x['dataset_key'] for x in items}
filters=read(HERE/'inventory/foodsafety-source-filter-codes.json')
for sel,options in filters['filters'].items():
    nodes=soup(filters['evidence_id']).select('#'+sel+' option');assert len(nodes)==len(options)
    for a,b in zip(options,nodes):assert a['value']==b.get('value') and a['label']==b.get_text(' ',strip=True)
ok('hyphenated_service_ids_and_filter_codes_preserved_without_inferred_provider_ids',39)

fields=inputs=duplicates=file_rows=0;manifest=[]
for c in items:
    path=HERE/'definitions'/('foodsafety-schema-'+c['dataset_key']+'.json');raw=path.read_bytes();d=json.loads(raw)
    manifest.append({'path':path.name,'sha256':sha256(raw).hexdigest()})
    assert not d['human_approved'] and not d['raw_values_checked'] and not d['observation_api_called']
    if c['dataset_key']=='I2791':
        assert d['fields']==[] and d['outgoing_links'][0]['url']=='https://www.data.go.kr/data/15127578/openapi.do'
        assert 'I2791' in original(d['evidence_id'])[0].decode();continue
    s=soup(d['evidence_id']);tables=s.select('table')
    assert s.select_one('input#svc_no')['value']==c['dataset_key']
    assert not d['issues']
    for f in d['fields']:
        t=tables[f['table_index']];assert t.caption.get_text(' ',strip=True)=='변수 목록'
        tr=t.select('tbody tr')[f['row_index']];cells=[x.get_text(' ',strip=True) for x in tr.find_all(['th','td'],recursive=False)]
        assert f['source_cells']==cells and f['name_en']==cells[1] and f['description']==cells[2]
        assert f['datatype'] is None and f['unit'] is None and f['role']=='api_response_column'
        fields+=1
    for p in d['request_parameters']:
        tr=tables[p['table_index']].select('tbody tr')[p['row_index']]
        assert [x.get_text(' ',strip=True) for x in tr.find_all(['th','td'],recursive=False)]==p['source_cells'];inputs+=1
    for t in d['response_table_occurrences']:
        if t['exact_duplicate_table']:
            a=[[x.get_text(' ',strip=True) for x in tr.find_all(['th','td'],recursive=False)] for tr in tables[t['table_index']].select('tbody tr')]
            b=[[x.get_text(' ',strip=True) for x in tr.find_all(['th','td'],recursive=False)] for tr in tables[t['same_table_as_index']].select('tbody tr')]
            assert a==b;duplicates+=1
    for t in d.get('file_metadata_tables',[]):
        assert not t['file_contents_downloaded'] and t['size_unit_kept_as_reported']
        for row in t['rows']:
            tr=tables[row['table_index']].select('tbody tr')[row['row_index']]
            assert row['source_cells']==[x.get_text(' ',strip=True) for x in tr.find_all(['th','td'],recursive=False)];file_rows+=1
    if c['source_service_types']==['FILE']:assert not d['fields'] and d.get('file_metadata_tables')
    else:assert d['source_notice_references'] and d['fields']
assert fields==summary['response_fields']==1861
ok('all_output_fields_reconcile_to_document_rows_and_do_not_infer_types',fields)
assert inputs==summary['request_parameters']==1315 and summary['request_parameter_occurrences_in_api_registrations']==1275
ok('request_tables_remain_separate_including_generic_rows_on_file_pages',{'api':1275,'file_page_template':40})
assert duplicates==summary['exact_duplicate_response_tables']==169
ok('identical_repeated_response_tables_not_double_counted',169)
assert file_rows==summary['file_metadata_rows']==316
ok('all_eight_file_pages_keep_version_rows_and_source_size_units',316)
ok('sample_rows_message_codes_and_external_link_not_promoted_to_fields',178)

notices=read(HERE/'inventory/foodsafety-source-notices.json')['notices']
for n in notices:
    assert soup(n['evidence_id']).select_one('#bdt_pre').get_text(' ',strip=True)==n['notice_body_text']
    assert not n['individual_dataset_field_mapping_verified'] and not n['raw_observation_values_verified']
assert '빈 값(Null)' in notices[0]['notice_body_text'] and 'CHNG_DT' in notices[1]['notice_body_text']
ok('privacy_and_usage_notices_are_source_statements_not_value_tests',2)
legacy=soup('foodsafety-api-legacy-home').get_text(' ',strip=True)
assert re.search(r'XML/JSON\s*\(172\)',legacy) and '171종' in notices[1]['notice_body_text']
assert read(HERE/'foodsafety-catalog-crosscheck.json')['scope_or_date_differences_resolved'] is False
ok('three_different_published_api_counts_preserve_unresolved_scope',{'catalog':169,'legacy_home':172,'notice':171})
for eid,(body,r) in receipts.items():
    assert 'openapi.foodsafetykorea.go.kr/api/' not in r['requested_url']
ok('source_receipt_hashes_and_no_observation_api_requests',len(receipts))
dump(HERE/'foodsafety-source-check.json',{'generated_at':now(),'passed':True,'checks_passed':len(checks),'checks':checks,
    'originals_hashed':len(receipts),'definition_snapshot':manifest,'all_columns_complete':False})
print(json.dumps({'checks_passed':len(checks),'originals_hashed':len(receipts),'fields':fields,'file_metadata_rows':file_rows}))
