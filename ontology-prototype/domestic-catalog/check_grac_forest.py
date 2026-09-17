"""Verify new finite source snapshots against raw HTML cells and immutable hashes."""
from common import *
from collections import Counter
from urllib.parse import urljoin,urlsplit,parse_qs
import re,sqlite3
import xml.etree.ElementTree as ET

checks=[];receipts={};soups={};manifest=[]

def original(eid):
    if eid not in receipts:
        r=read(HERE/'evidence'/(eid+'.json'));assert r['status']=='fetched',eid
        b=gzip.decompress((HERE/r['raw_file']).read_bytes())
        assert len(b)==r['bytes'] and sha256(b).hexdigest()==r['sha256'],eid
        receipts[eid]=(b,r)
    return receipts[eid]

def soup(eid):
    if eid not in soups:soups[eid]=BeautifulSoup(original(eid)[0],'html.parser')
    return soups[eid]

def doc(portal,key):
    p=HERE/'definitions'/f'{portal}-schema-{key}.json';raw=p.read_bytes();d=json.loads(raw)
    manifest.append({'path':p.name,'sha256':sha256(raw).hexdigest()})
    assert not d['human_approved'] and not d['raw_values_checked'] and not d['all_columns_complete'] and not d['observation_api_called']
    return d

def ok(name,detail):checks.append({'name':name,'passed':True,'detail':detail})

def physical_cell(s,loc):
    match=re.fullmatch(r'table\[(\d+)\]\.tbody\.tr\[(\d+)\]\.cell\[(\d+)\]',loc);assert match,loc
    tn,rn,cn=map(int,match.groups())
    return s.select('table')[tn].select('tbody tr')[rn].find_all(['th','td'],recursive=False)[cn]

grac=read(HERE/'inventory/grac-catalog.json');assert len(grac)==2
grac_docs={c['dataset_key']:doc('grac',c['dataset_key']) for c in grac}
for c in grac:
    a=soup(c['evidence_id']).select('a[href]')[int(re.search(r'\[(\d+)\]',c['locator'])[1])]
    assert urljoin(original(c['evidence_id'])[1]['requested_url'],a['href'])==c['url']
ok('grac_two_guide_registrations_are_explicit_source_links',2)
expanded=outputs=inputs=structures=0
for d in grac_docs.values():
    s=soup(d['evidence_id'])
    for group in ('fields','request_parameters','structural_elements'):
        for f in d[group]:
            expected=[]
            for v in f['expanded_cell_sources']:
                cell=physical_cell(s,v['locator'])
                assert cell.get_text(' ',strip=True)==v['text']
                assert int(cell.get('rowspan',1))==v['rowspan'] and int(cell.get('colspan',1))==v['colspan']
                expected.append(v['text']);expanded+=1
            assert expected==f['expanded_cells']
            assert (f['name_en'],f['source_type_as_reported'],f['requirement_as_reported'],f['description'])==tuple(expected)
    for t in d['definition_tables']:
        source=s.select('table')[t['table_index']]
        assert source.find_previous(['h2','h3','h4']).get_text(' ',strip=True)==t['heading']
        assert len(source.select('tbody tr'))==len(t['rows'])
    outputs+=len(d['fields']);inputs+=len(d['request_parameters']);structures+=len(d['structural_elements'])
assert (outputs,inputs,structures)==(24,10,4)
ok('grac_output_input_and_structure_rows_reconcile_to_physical_cells',{'output':24,'input':10,'structure':4,'expanded_cells':expanded})
game=grac_docs['game'];request={v['name_en']:v for v in game['request_parameters']}
assert all(request[k]['requirement_as_reported']=='X' for k in ['gametitle','entname','rateno','startdate','enddate'])
assert request['enddate']['expanded_cell_sources'][2]['source_row']==1
assert request['enddate']['expanded_cell_sources'][2]['rowspan']==5
ok('rowspan_optional_requirement_uses_explicit_source_span',5)
assert 'canceledddate' in {f['name_en'] for f in game['fields']}
assert 'canceleddate' not in {f['name_en'] for f in game['fields']}
for d in grac_docs.values():
    for ex in d['documentation_examples']:
        pn=int(re.search(r'\[(\d+)\]',ex['locator'])[1]);text=soup(d['evidence_id']).select('pre')[pn].get_text().strip()
        assert text==ex['text_as_reported']
        try:root=ET.fromstring(text);valid=True
        except ET.ParseError:valid=False
        assert valid==(ex['xml_parse_status']=='valid_documentation_xml')
assert game['documentation_examples'][0]['names_not_in_output_table']==['canceleddate']
assert game['documentation_examples'][0]['output_table_names_not_in_example']==['canceledddate']
assert all(e['xml_parse_status']=='malformed_documentation_xml' for e in game['documentation_examples'])
ok('game_xml_errors_and_different_column_names_preserved_without_repair',2)
recruit=grac_docs['recruit'];t=recruit['definition_tables'][1]
assert t['heading']=='출력 변수' and t['headers'][0]=='요청변수' and t['role_from_heading']=='response'
assert [f['name_en'] for f in recruit['structural_elements']]==['result','result']
assert recruit['documentation_examples'][0]['names_not_in_output_table']==['resultItem','results']
assert recruit['documentation_examples'][0]['root_name']=='results'
ok('recruit_conflicting_header_and_distinct_repeated_root_rows_not_merged',{'output':9,'structure':2})
assert [r['expanded_cells'][0] for r in game['error_code_tables'][0]['rows']]==['0000','0010','0011','0013','0020']
ok('error_codes_retain_leading_zeros_and_are_not_output_fields',5)

forest=read(HERE/'inventory/forest-catalog.json');report=read(HERE/'forest-catalog-report.json')
assert len(forest)==len({x['dataset_key'] for x in forest})==56
assert [p['cards'] for p in report['category_pages']]==[8,13,3,2,30]
assert {p['tab']['code'] for p in report['category_pages']}=={'1','3','4','5','6'}
assert report['source_reported_total'] is None and not report['all_portal_catalogs_complete']
for p in report['category_pages']:
    s=soup(p['evidence_id'])
    assert len(s.select('.details_list > ul > li'))==p['cards']
    assert s.select_one('input[name=tabs]')['value']==p['tab']['code']
    assert b'</html>' in original(p['evidence_id'])[0].lower()
    assert not s.select('.paging a, .pagination a')
for c in forest:
    for occ in c['catalog_occurrences']:
        n=int(re.search(r'\[(\d+)\]',occ['locator'])[1]);card=soup(occ['evidence_id']).select('.details_list > ul > li')[n]
        a=card.select_one('.sm_wrap a')
        href=re.sub(r';jsessionid=[^?&#/]+','',a['href'],flags=re.I)
        assert c['title']==a.get_text(' ',strip=True)
        assert c['linked_resource_url']==urljoin(original(occ['evidence_id'])[1]['requested_url'],href)
        assert ';jsessionid=' not in c['linked_resource_url']
    q=parse_qs(urlsplit(c['linked_resource_url']).query)
    assert c['native_public_data_id']==q.get('pblicDataId',[None])[0]
    if c['native_public_data_id']:assert c['dataset_key']==c['native_public_data_id']
ok('forest_all_explicit_category_documents_and_56_source_cards',{'categories':5,'cards':56,'global_total_not_claimed':True})
fd={c['dataset_key']:doc('forest',c['dataset_key']) for c in forest};response=input_count=local=external=0
refs=[]
db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3',timeout=60)
for c in forest:
    d=fd[c['dataset_key']]
    if not c['local_html_guide']:
        external+=1;assert not d['fields'] and d['outgoing_links'][0]['url']==c['linked_resource_url']
        assert not d['outgoing_links'][0]['same_dataset_asserted']
        m=re.fullmatch(r'https?://(?:www\.)?data\.go\.kr/(data|dataset)/([0-9]+)/openapi\.do',c['linked_resource_url'])
        if m:
            matches=[{'record_id':rid,'title':title,'documented_fields':n} for rid,title,n in db.execute(
                'SELECT r.id,r.title,(SELECT count(*) FROM documented_fields f WHERE f.record_id=r.id) FROM records r WHERE r.portal_id=? AND r.dataset_key=? AND r.kind=?',
                ('data-go',m[2],'API'))]
            refs.append({'source_record_id':c['id'],'target_url_as_reported':c['linked_resource_url'],'source_path_style':m[1],
                'public_data_pk_as_linked':m[2],'evidence_id':c['evidence_id'],'locator':c['locator']+' .sm_wrap a@href',
                'existing_catalog_matches':matches,'live_target_url_rechecked':False,'source_schema_copied':False,
                'semantic_equivalence_approved':False,'joinability_approved':False})
        continue
    local+=1;s=soup(d['evidence_id']);tables=s.select('table')
    assert d['source_url']==original(d['evidence_id'])[1]['requested_url']
    assert not d['issues']
    assert parse_qs(urlsplit(d['source_url']).query)['pblicDataId']==[c['dataset_key']]
    for group in ('fields','request_parameters'):
        for f in d[group]:
            t=tables[f['table_index']];tr=t.select('tbody tr')[f['row_index']]
            values=[x.get_text(' ',strip=True) for x in tr.find_all(['td','th'],recursive=False)]
            assert f['source_cells']==values
            assert (f['name_en'],f['datatype'],f['description'])==tuple(values)
            caption=t.caption.get_text(' ',strip=True).replace(' ','') if t.caption else ''
            assert ('결과파라미터' if group=='fields' else '요청파라미터') in caption
            assert f['unit'] is None
    assert sum(len(t['rows']) for t in d['definition_tables'] if t['role']=='response')==len(d['fields'])
    assert sum(len(t['rows']) for t in d['definition_tables'] if t['role']=='request')==len(d['request_parameters'])
    for note in d['public_usage_note_candidates']:
        n=int(re.search(r'\[(\d+)\]',note['locator'])[1])
        assert s.select('#txt p')[n].get_text(' ',strip=True)==note['text_as_reported']
        assert not note['license_or_reuse_approval_inferred']
    response+=len(d['fields']);input_count+=len(d['request_parameters'])
db.close()
assert (local,external,response,input_count)==(21,35,156,50)
assert sum(bool(d['fields']) for d in fd.values())==10
ok('forest_local_response_tables_and_inputs_reconcile_to_all_source_rows',{'local_guides':21,'response_guides':10,'output_fields':156,'input_rows':50})
ok('forest_other_guides_and_external_references_do_not_invent_schema',{'local_without_fields':11,'external_references':35})
qa=read(HERE/'forest-source-qa.json')
assert qa['documented_response_fields']==response and qa['input_parameter_rows']==input_count
assert qa['field_datatype_present']==156 and qa['unit_explicitly_documented']==0
assert not qa['quality_scores_assigned'] and not qa['raw_values_checked']
assert any('비영리' in n['text_as_reported'] for entry in qa['usage_note_candidates'] for n in entry['notes'])
ok('forest_source_usage_notes_are_preserved_for_review_without_reuse_approval',sum(len(d.get('public_usage_note_candidates',[])) for d in fd.values()))
dump(HERE/'inventory/forest-data-go-reference-resolution.json',{'generated_at':now(),'references':refs,
    'source_data_go_references':len(refs),'matched_in_existing_catalog':sum(bool(x['existing_catalog_matches']) for x in refs),
    'live_target_url_checks_performed':False,'fields_copied_into_source_registration':False})
ok('forest_explicit_data_go_links_matched_to_existing_namespace_without_field_copy',{'references':len(refs),'matched':sum(bool(x['existing_catalog_matches']) for x in refs)})
nav=read(HERE/'inventory/forest-navigation-observations.json')
for m in nav['moves']:
    assert m['source_statement'] in original(m['evidence_id'])[0].decode('utf-8')
assert original(nav['overview_evidence_id'])[1]['final_url']==nav['public_overview_final_url']
assert any(urljoin(nav['public_overview_final_url'],a['href'])==nav['catalog_url'] for a in soup(nav['overview_evidence_id']).select('a[href]'))
assert not nav['closed_or_unavailable_inferred']
ok('forest_landing_javascript_route_to_official_catalog_is_source_backed',2)
disclosure=read(HERE/'inventory/grac-disclosure-navigation.json')
for link in disclosure['links']:
    n=int(re.search(r'\[(\d+)\]',link['locator'])[1]);a=soup(link['evidence_id']).select('.contentBody a[href]')[n]
    assert link['url']==urljoin(original(link['evidence_id'])[1]['requested_url'],a['href'])
assert disclosure['staff_contact_table_not_used_as_dataset_schema']
ok('grac_disclosure_navigation_does_not_turn_staff_table_into_dataset_fields',3)
assert len(manifest)==58
for eid,(body,r) in receipts.items():
    assert 'api.forest.go.kr' not in r['requested_url'] and '/WebService/' not in r['requested_url'] and '/API/RecruitService' not in r['requested_url']
ok('all_new_snapshot_receipt_hashes_and_no_data_api_requests',len(receipts))
dump(HERE/'grac-forest-source-check.json',{'generated_at':now(),'passed':True,'checks_passed':len(checks),'checks':checks,
    'originals_hashed':len(receipts),'definition_snapshot':manifest,'all_columns_complete':False,'scope':'Only these 58 registration documents and their named sources'})
print(json.dumps({'checks_passed':len(checks),'originals_hashed':len(receipts),'grac_fields':outputs,'forest_fields':response,'external_data_go_refs':len(refs)}))
