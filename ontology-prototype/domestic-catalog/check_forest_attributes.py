"""Source and live-search checks for the 19 linked forest usage documents."""
from common import *
from urllib.parse import urljoin,urlsplit,parse_qs,urlencode
from collections import Counter
import re,sqlite3

checks=[];originals={};manifest=[]
def source(eid):
    if eid not in originals:
        r=read(HERE/'evidence'/(eid+'.json'));assert r['status']=='fetched'
        raw=gzip.decompress((HERE/r['raw_file']).read_bytes())
        assert sha256(raw).hexdigest()==r['sha256'] and len(raw)==r['bytes']
        originals[eid]=(BeautifulSoup(raw,'html.parser'),r)
    return originals[eid]
def ok(name,detail):checks.append({'name':name,'passed':True,'detail':detail})
targets=read(HERE/'inventory/forest-usage-targets.json');assert targets['local_guide_pages_checked']==21 and len(targets['targets'])==19
docs={};fields=groups=unknown=0
for t in targets['targets']:
    s,r=source(t['evidence_id']);n=int(re.search(r'\[(\d+)\]',t['locator'])[1]);a=s.select('#txt a[href]')[n]
    assert urljoin(r['requested_url'],re.sub(r';jsessionid=[^?&#/]+','',a['href']))==t['url']
    assert parse_qs(urlsplit(t['url']).query)['pblicDataId']==[t['dataset_key']]
    p=HERE/'definitions'/('forest-schema-'+t['dataset_key']+'-usage.json');raw=p.read_bytes();d=json.loads(raw);docs[t['dataset_key']]=d
    manifest.append({'path':p.name,'sha256':sha256(raw).hexdigest()})
    s,r=source(d['evidence_id']);content=s.select_one('#txt');tables=s.select('table')
    assert d['source_url']==r['requested_url'] and d['documentation_text']==content.get_text(' ',strip=True)
    assert not d['raw_values_checked'] and not d['human_approved'] and not d['file_downloaded'] and not d['observation_api_called']
    for group in d['schema_groups']:
        table=tables[group['table_index']];assert group['headers']==[c.get_text(' ',strip=True) for c in table.select('thead th')]
        assert group['caption']==table.caption.get_text(' ',strip=True)
        before=table.find_previous_sibling()
        if before:assert group['immediate_preceding_element']['text_as_reported']==before.get_text(' ',strip=True)
        else:assert group['immediate_preceding_element'] is None
        assert len(table.select('tbody tr'))==len(group['rows']);groups+=1
    assert sum(len(g['rows']) for g in d['schema_groups'])==len(d['fields'])
    for f in d['fields']:
        tr=tables[f['table_index']].select('tbody tr')[f['row_index']]
        cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]
        assert cells==f['source_cells'] and [f['name_en'],f['description'],f['datatype'],f['length_as_reported']]==cells
        assert f['schema_group_id']==d['evidence_id']+':table:'+str(f['table_index'])
        assert f['unit'] is None and f['length_numeric_interpretation'] is None and not f['latest_file_version_applicability_verified']
        fields+=1;unknown+=f['length_as_reported']=='?'
    for b in d['source_context_blocks']:
        n=int(re.search(r'\[(\d+)\]',b['locator'])[1]);assert content.select('ul,p,h3,h4,h5')[n].get_text(' ',strip=True)==b['text_as_reported']
    assert d['declared_epsg_code'] is None and not d['geometry_or_crs_normalization_performed']
assert (fields,groups,unknown)==(61,7,3)
ok('all_19_usage_tabs_resolve_from_their_original_guide_links',19)
ok('all_61_attributes_reconcile_to_7_original_tables',61)
ok('three_unspecified_lengths_preserved_as_question_marks',3)
assert sum(bool(d['fields']) for d in docs.values())==5
ok('14_usage_pages_without_attribute_tables_do_not_invent_columns',14)
hike=docs['PBD0000041'];assert len(hike['fields'])==31
assert [len(g['rows']) for g in hike['schema_groups']]==[9,16,6]
assert len({f['schema_group_id'] for f in hike['fields'] if f['name_en']=='MNTN_CODE'})==2
assert any(f['length_as_reported']=='5,2' for f in hike['fields'])
ok('hiking_point_line_and_safety_layers_preserve_separate_groups_and_raw_lengths',[9,16,6])
assert '2016년 12월 31일' in hike['documentation_text'] and '구간별거리:km' in hike['documentation_text']
assert 'WGS84' in docs['PBD0000031']['documentation_text'] and 'GRS80' in docs['PBD0000031']['documentation_text']
assert 'imsang_5th.zip' in docs['PBD0000059']['documentation_text']
ok('dates_units_geometry_and_file_version_text_are_preserved_without_epsg_inference',19)
db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3',timeout=60)
assert db.execute("SELECT count(*),sum(field_count) FROM schema_documents WHERE portal_id='forest' AND path LIKE '%-usage.json'").fetchone()==(19,61)
assert db.execute("SELECT count(*),count(distinct f.record_id) FROM documented_fields f JOIN records r ON r.id=f.record_id WHERE r.portal_id='forest' AND json_extract(f.definition_json,'$.role')='documented_file_layer_attribute'").fetchone()==(61,5)
ok('file_attributes_indexed_as_61_fields_in_5_existing_registrations',61)
with urlopen('http://127.0.0.1:8766/api/search?'+urlencode({'id':'forest-PBD0000041'}),timeout=60) as response:r=json.load(response)
assert len(r['definitions'])==31
assert len({f['raw_definition']['schema_group_id'] for f in r['definitions'] if f['name_en']=='MNTN_CODE'})==2
assert len([d for d in r['schema_documents'] if d['evidence_id']=='forest-usage-PBD0000041'])==1
ok('live_http_preserves_repeated_column_names_across_layer_dictionaries',31)
db.close()
dump(HERE/'forest-attribute-source-check.json',{'generated_at':now(),'passed':True,'checks_passed':len(checks),'checks':checks,
    'originals_hashed':len(originals),'definition_snapshot':manifest,'all_columns_complete':False,
    'scope':'19 additional usage documents and their 19 parent guide link sources, plus named SQLite/HTTP checks'})
print(json.dumps({'checks_passed':len(checks),'originals_hashed':len(originals),'attribute_fields':fields}))
