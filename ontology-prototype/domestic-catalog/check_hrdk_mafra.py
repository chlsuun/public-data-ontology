"""Source checks over a named snapshot; ongoing later collection is not covered."""
from common import *
import re,sqlite3

checks=[];receipts=set();cache={}
def original(eid):
    receipts.add(eid)
    if eid not in cache:
        r=read(HERE/'evidence'/(eid+'.json'))
        if r.get('status')!='fetched':return None,r
        b=gzip.decompress((HERE/r['raw_file']).read_bytes())
        assert sha256(b).hexdigest()==r['sha256'] and len(b)==r['bytes'],eid
        cache[eid]=(b,r)
    return cache[eid]
def ok(name,detail):checks.append({'name':name,'passed':True,'detail':detail})

started=now()
cards=read(HERE/'inventory/hrdk-api-catalog.json')
b,_=original('hrdk-public-home-20260914');s=BeautifulSoup(b,'html.parser');titles=s.select('#section2 .section-body-title')
assert len(cards)==len(titles)==len(s.select('#section2 a[href]'))==69
for i,(c,t) in enumerate(zip(cards,titles)):
    assert c['title']==t.get_text(' ',strip=True)
    assert c['external_reference_url']==t.parent.select_one('a')['href']
    assert c['locator']==f'#section2 .section-body-title[{i}]'
    assert c['provider_id'] is None and c['provider_name'] is None
ok('hrdk_entire_visible_catalog_and_source_positions',len(cards))
assert len({x['dataset_key'] for x in cards})==69
for c in cards:
    d=read(HERE/'definitions'/('hrdk-api-schema-'+c['dataset_key']+'.json'))
    assert d['fields']==[] and d['outgoing_links'][0]['url']==c['external_reference_url'] and d['human_approved'] is False
ok('external_referrals_do_not_duplicate_target_columns',69)
db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3')
res=read(HERE/'inventory/hrdk-api-reference-resolution.json')
assert len(res['references'])==69
for x in res['references']:
    expected=[v[0] for v in db.execute("SELECT id FROM records WHERE portal_id='data-go' AND dataset_key=? AND kind='API'",(x['target_public_data_pk_from_url'],))]
    assert expected==[v['id'] for v in x['local_target_registrations']]
    assert not x['same_dataset_asserted'] and not x['joinability_asserted']
ok('explicit_url_identifier_resolution_retains_unmatched_links',{'resolved':res['resolved_reference_count'],'unresolved':res['unresolved_reference_count']})

contracts=read(HERE/'inventory/hrdk-mcp-tool-contracts.json');tools=contracts['tools'];report=read(HERE/'hrdk-mcp-collection-report.json')
assert len(tools)==len({x['id'] for x in tools})==87
for t in tools:
    b,r=original(t['evidence_id']);messages=[json.loads(line[5:].strip()) for line in b.decode().splitlines() if line.startswith('data:')]
    response=next(x for x in messages if x.get('id')=='catalog-metadata')
    pos=int(re.search(r'\[(\d+)\]$',t['locator'])[1])
    assert response['result']['tools'][pos]==t['source_contract']
    assert r['requested_url']==t['endpoint'] and r['public_json_parameters']['method']=='tools/list'
    assert r['request_accept']=='application/json, text/event-stream'
    assert not t['tool_executed'] and t['input_parameters_are_not_dataset_columns']
ok('all_tool_contracts_reconcile_to_raw_sse_response',87)
assert sum(len(x['source_contract']['inputSchema']['properties']) for x in tools)==report['input_property_occurrences']==223
assert all('outputSchema' not in x['source_contract'] for x in tools)
assert report['documented_dataset_field_count_added']==0
ok('mcp_input_properties_kept_separate_from_dataset_output_columns',223)
b,_=original('hrdk-public-mcp-guide');guide=BeautifulSoup(b,'html.parser')
assert len(guide.select('.mcp-ep'))==6
assert [x['path'] for x in contracts['endpoints'][1:]]==[x.get_text(' ',strip=True) for x in guide.select('.mcp-ep')]
assert '41' in guide.get_text(' ',strip=True) and report['root_tool_count']==45 and report['root_tool_count_matches_guide'] is False
assert contracts['endpoints'][3]['path']=='/mcp/ncs' and contracts['endpoints'][3]['tool_contracts']==6
ok('guide_and_live_list_count_disagreements_preserved',{'root':'41 vs 45','ncs':'5 vs 6'})
rels=read(HERE/'inventory/hrdk-mcp-tool-relations.json')['relations'];model=read(HERE/'model.json')
assert {x['target'] for x in rels}=={x['id'] for x in tools}
assert all(x['source']=='hrdk-api' and x['predicate']=='advertisesPublicToolContract' for x in rels)
assert 'PublicToolContract' in model['entity_types']
ok('tool_ontology_references_resolve_without_dataset_equivalence',87)

targets=read(HERE/'inventory/mafra-preview-targets.json');catalog=read(HERE/'inventory/mafra-catalog.json')
assert {x['dataset_key'] for x in targets['datasets']}=={x['dataset_key'] for x in catalog if x['kind']=='FILE'}
assert targets['dataset_count']==619 and targets['preview_count']==1510
occurrences=0;duplicates=0
for x in targets['datasets']:
    b,r=original(x['detail_evidence_id'])
    if not b:assert 'unresolved' in x['discovery_status'];continue
    soup=BeautifulSoup(b,'html.parser');buttons=soup.select('[onclick]')
    observed=[(i,a['onclick']) for i,a in enumerate(buttons) if 'filePreview(' in a['onclick']]
    saved=[]
    for p in x['previews']:
        positions=[{'locator':p['locator'],'source_onclick':p['source_onclick']}]+p['repeated_button_occurrences']
        for pos in positions:
            i=int(re.search(r'\[(\d+)\]@onclick$',pos['locator'])[1]);assert buttons[i]['onclick']==pos['source_onclick'];saved.append((i,pos['source_onclick']))
        duplicates+=len(p['repeated_button_occurrences'])
        assert p['data_id']==x['source_data_id']
    assert sorted(observed)==sorted(saved),x['dataset_key']
    occurrences+=len(observed)
ok('all_619_file_detail_pages_reconcile_preview_button_occurrences',{'buttons':occurrences,'unique_requests':1510,'repeated_buttons':duplicates})

snapshot=[];headers=0;versions=0;outcomes={}
paths=sorted((HERE/'definitions').glob('mafra-file-previews-*.json'))
for p in paths:
    raw=p.read_bytes();d=json.loads(raw);snapshot.append({'path':p.name,'sha256':sha256(raw).hexdigest(),'collected_at':d['collected_at']})
    assert d['fields']==[] and d['header_candidate_kind']=='public_file_preview_thead'
    assert not d['bulk_file_downloaded'] and not d['human_approved'] and not d['all_columns_complete']
    expected=[]
    for v in d['preview_headers']:
        b,r=original(v['evidence_id']);versions+=1;outcomes[v['status']]=outcomes.get(v['status'],0)+1
        assert r['requested_url']=='https://data.mafra.go.kr/opendata/data/previewOpenDataWebFile.do'
        assert r['public_form_parameters']=={k:v[k] for k in ('data_id','file_sn','file_ty_code')}
        if v['status']=='preview_fetch_unresolved':assert b is None;continue
        if v['status']=='preview_parse_unresolved':continue
        data=json.loads(b)
        if data=={'numberOfCells':0,'listHead':None,'listRow':None}:
            assert v['status']=='preview_header_empty' and v['headers']==[] and v['source_head_is_null'] and v['source_rows_are_null']
            continue
        assert v['number_of_cells_as_reported']==data['numberOfCells'] and v['source_preview_row_count']==len(data['listRow'])
        assert len(v['headers'])==sum(len(x) for x in data['listHead'])
        for h in v['headers']:
            assert h['value']==data['listHead'][h['header_row']][h['cell']]
            assert h['locator']==f"listHead[{h['header_row']}][{h['cell']}]" and h['evidence_id']==v['evidence_id']
            expected.append(h['value']);headers+=1
    assert d['header_candidates']==expected
ok('snapshot_preview_headers_match_source_cells_and_file_versions',{'documents':len(paths),'preview_versions':versions,'candidate_cells':headers})
ok('preview_error_empty_and_success_outcomes_remain_distinct',outcomes)
ok('preview_candidates_never_promoted_to_documented_columns',len(paths))
ok('all_fetched_originals_match_receipt_bytes_and_sha256',len(cache))
dump(HERE/'hrdk-mafra-source-check.json',{'started_at':started,'finished_at':now(),'passed':True,'checks':checks,
    'checks_passed':len(checks),'source_receipts_checked':len(receipts),'fetched_originals_hashed':len(cache),
    'preview_snapshot':snapshot,'snapshot_scope_note':'Only files named here; subsequent worker output is not covered.',
    'national_complete':False,'all_columns_complete':False})
print(json.dumps({'checks':len(checks),'source_receipts':len(receipts),'previews':len(paths),'headers':headers},ensure_ascii=False))
