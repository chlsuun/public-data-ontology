"""Reconcile KDI, KOCCA, referred KSPO metadata and primary culture dictionaries."""
from common import *
from collections import Counter
import re

def main():
    checks=[];hashes={}
    def check(name,ok,detail=None):
        checks.append({'name':name,'passed':bool(ok),'detail':detail})
        if not ok:raise AssertionError(name)
    def raw(eid):
        r=read(HERE/'evidence'/(eid+'.json'));assert r['status']=='fetched'
        b=gzip.decompress((HERE/r['raw_file']).read_bytes());assert len(b)==r['bytes'] and sha256(b).hexdigest()==r['sha256']
        hashes[eid]=r['sha256'];return b
    def soup(eid):return BeautifulSoup(raw(eid),'html.parser')
    def obj(eid):return json.loads(raw(eid))
    def cells(tr):return [x.get_text(' ',strip=True) for x in tr.find_all(['td','th'],recursive=False)]
    s=soup('kdi-api-public-guide-20260914');tables=s.select('table');r=read(HERE/'inventory/kdi-api-catalog.json');docs=[]
    assert [x['dataset_key'] for x in r]==[x['value'] for x in s.select('option')]
    for item in r:
        d=read(HERE/'definitions'/('kdi-api-schema-'+item['dataset_key']+'.json'));docs.append(d)
        for f in d['fields']+d['structural_elements']+d['request_parameters']:
            tn,rn=map(int,re.findall(r'\[(\d+)\]',f['locator']));v=cells(tables[tn].select('tbody tr')[rn]);assert v==f['source_cells'] and f['name_en']==v[0]
        assert all(f['unit'] is None for f in d['fields']) and not d['raw_values_checked'] and not d['observation_api_called']
    check('kdi_six_explicit_categories_and_113_response_fields_match_source',len(r)==6 and sum(len(d['fields']) for d in docs)==113)
    check('kdi_structure_inputs_and_conflicting_default_cd_preserved',sum(len(d['structural_elements']) for d in docs)==6 and sum(len(d['request_parameters']) for d in docs)==30 and sum(len(d['issues']) for d in docs)==5)
    s=soup('kocca-api-usage-guide');tables=s.select('table');r=read(HERE/'inventory/kocca-api-catalog.json');kdocs=[]
    for item in r:
        d=read(HERE/'definitions'/('kocca-api-schema-'+item['dataset_key']+'.json'));kdocs.append(d)
        c=s.select_one('#'+d['reference_container_id']);assert item['source_application_link_not_requested']==c.select_one('a')['href']
        for f in d['request_parameters']:
            numbers=list(map(int,re.findall(r'\[(\d+)\]',f['locator'])));tn=numbers[0]
            physical=tables[tn].tbody.find_all(['td','th'],recursive=False) if f.get('source_row_tag_missing') else tables[tn].select('tbody tr')[numbers[1]].find_all(['td','th'],recursive=False)
            assert f['source_cells']==[x.get_text(' ',strip=True) for x in physical]
        for f in d['fields']:
            values=f['expanded_cells'];assert f['name_en']==values[1] and f['datatype']==values[2] and f['description']==values[3]
            rn=int(re.search(r'tr\[(\d+)\]',f['locator'])[1]);assert values==[v['text'] for v in f['expanded_cell_sources']]
            for v in f['source_cells']+f['expanded_cell_sources']:
                tn,rr,cc=map(int,re.findall(r'\[(\d+)\]',v['locator']));cell=tables[tn].select('tbody tr')[rr].find_all(['td','th'],recursive=False)[cc]
                assert cell.get_text(' ',strip=True)==v['text'] and int(cell.get('rowspan',1))==v['rowspan'] and int(cell.get('colspan',1))==v['colspan']
                assert rr<=rn<rr+v['rowspan']
            sources=f['expanded_cell_sources'];expected='response' if sources[0]['locator']==sources[1]['locator'] else 'List'
            assert f['schema_group_id']==expected
        for table in d['error_code_tables']:
            for rr in table['rows']:
                tn,rn=map(int,re.findall(r'\[(\d+)\]',rr['locator']));assert rr['source_cells']==cells(tables[tn].select('tbody tr')[rn])
    check('kocca_101_output_rows_keep_root_and_list_paths_distinct',len(kdocs)==6 and sum(len(d['fields']) for d in kdocs)==101 and all(sum(f['name_en']=='title' for f in d['fields'])==2 for d in kdocs))
    q=read(HERE/'kocca-api-source-qa.json');counts=Counter(x['issue'] for x in q['issues'])
    check('kocca_six_orphan_input_cell_groups_and_one_overrunning_span_preserved',q['request_parameter_occurrences']==33 and counts['request_parameter_td_cells_without_tr']==6 and counts['source_rowspan_extends_past_table_end']==1)
    check('kocca_error_code_typo_sample_names_and_spelling_not_repaired',counts['error_table_resultMgs_differs_from_response_resultMsg']==6 and any(f['documented_path']=='List.cata' for d in kdocs for f in d['fields']))
    intro=soup('kocca-api-public-guide-20260914');groups=read(HERE/'inventory/kocca-api-introduction-groups.json')
    assert [x['source_cells'] for x in groups['rows']]==[cells(x) for x in intro.select('table')[0].select('tbody tr')]
    check('kocca_intro_and_guide_counts_reconciled_without_renaming_source_groups',len(groups['rows'])==len(kdocs)==6)
    source=obj('kspo-referred-explorer-data');data=source['payloads'];records=read(HERE/'inventory/kspo-catalog.json');kspo_docs=[]
    for n,(item,x) in enumerate(zip(records,data[0])):
        assert item['source_record']==x and item['dataset_key']=='explorer-'+str(x['no']) and item['locator']==f'payloads[0][{n}]'
        no=str(x['no']);d=read(HERE/'definitions'/('kspo-schema-'+item['dataset_key']+'.json'));kspo_docs.append(d)
        assert not d['fields'] and not d['external_host_ownership_verified'] and d['raw_preview_rows_not_extracted']
        for candidate in d['reported_schema_candidates']:
            pi=int(re.search(r'payloads\[(\d+)\]',candidate['locator'])[1]);assert all(data[pi][no][k]==v for k,v in candidate['source_copy'].items())
        for preview in d['preview_headers']:
            pi=int(re.search(r'payloads\[(\d+)\]',preview['locator'])[1]);entry=data[pi][no]
            if pi==5:entry=entry[int(re.findall(r'\[(\d+)\]',preview['locator'])[1])]
            expected=[c['name'] if isinstance(c,dict) else c for c in entry['columns']]
            assert preview['values']==expected
        assert [v for p in d['preview_headers'] for v in p['values']]==d['header_candidates']
        def scan(x):
            if isinstance(x,dict):
                assert not (set(x)&{'rows','totalRows','rowCount','totalCount'})
                for v in x.values():scan(v)
            elif isinstance(x,list):
                for v in x:scan(v)
        scan(d)
    check('kspo_active_183_registered_rows_and_3035_preview_headers_reconciled',len(records)==183 and sum(len(d['header_candidates']) for d in kspo_docs)==3035)
    check('kspo_detached_entries_observations_and_planned_relations_not_imported',not any(r['dataset_key'] in ('explorer-33','explorer-40','explorer-103') for r in records) and all(d['source_planned_relationships_not_imported'] for d in kspo_docs))
    primary=read(HERE/'inventory/bigdata-culture-catalog.json');comparisons=[];field_count=0
    for r in primary:
        s=soup(r['evidence_id']);assert s.select_one('input[name="id"]')['value']==r['dataset_key'] and s.select_one('.tit_w p.tit span').get_text(' ',strip=True)==r['title']
        d=read(HERE/'definitions'/('bigdata-culture-schema-'+r['dataset_key']+'.json'));o=obj(d['evidence_id']);assert o['status']=='OK'
        assert d['source_dictionary_header']==o['data'][0] and len(d['fields'])==len(o['data'])-1
        for n,(f,v) in enumerate(zip(d['fields'],o['data'][1:]),1):
            assert f['source_cells']==v and f['name_en']==v[1] and f['name']==(v[2] or v[1]) and f['datatype']==(v[3] or None)
            assert f['locator']==f'data[{n}]' and f['unit'] is None and not f['all_file_versions_share_definition_verified']
        field_count+=len(d['fields'])
        normalized=[dict(zip(('order','name','label','type','length','pk','notNull'),v[:7])) for v in o['data'][1:]]
        for ref in r['source_referrals']:
            no=ref['dataset_key'].removeprefix('explorer-');copy=data[1][no]['columns'];same=copy==normalized
            differences=[]
            for i in range(max(len(copy),len(normalized))):
                old=copy[i] if i<len(copy) else {};new=normalized[i] if i<len(normalized) else {}
                if old!=new:differences.append({'row_index':i,'source_copy_as_reported':old,'current_primary_as_reported':new})
            comparisons.append({'source_dataset_key':ref['dataset_key'],'source_evidence_id':ref['evidence_id'],'source_locator':ref['locator'],
                'primary_portal_id':'bigdata-culture','primary_dataset_key':r['dataset_key'],'primary_evidence_id':d['evidence_id'],
                'comparison':'exact_documented_cell_match' if same else 'differences_observed','differences':differences,
                'semantic_identity_human_approved':False,'primary_fields_not_copied_to_kspo_registration':True})
    check('primary_culture_92_pages_and_1577_dictionary_fields_reconciled',len(primary)==92 and field_count==1577)
    comparison_counts=Counter(x['comparison'] for x in comparisons)
    check('secondary_vs_primary_87_matches_and_5_differences_retained',comparison_counts=={'exact_documented_cell_match':87,'differences_observed':5},dict(comparison_counts))
    dump(HERE/'inventory/kspo-culture-primary-definition-comparison.json',{'generated_at':now(),'comparisons':comparisons,
        'counts':dict(comparison_counts),'observed_reference_and_document_cell_comparison_not_semantic_identity_approval':True})
    for eid in ('kspo-disclosure-catalog','kspo-public-guide-20260914','kspo-referred-explorer','kspo-referred-explorer-script','kdi-disclosure-page'):raw(eid)
    ref=soup('kspo-disclosure-catalog');assert any(a['href'].strip()=='https://pinkshark1.github.io/kspo_data_explorer/' for a in ref.select('a[href]'))
    check('external_map_official_referral_and_primary_origin_chain_verified',True,{'metadata_origin_is_explicit':True,'host_ownership_not_inferred':True})
    report={'generated_at':now(),'passed':True,'checks_passed':len(checks),'checks':checks,'source_hashes_verified':len(hashes),
        'verified_source_hashes':hashes,'new_catalog_records':287,'formal_field_occurrences':1791,'referred_header_candidates':3035,
        'all_columns_complete':False,'scope':'These institution reference pages, officially referred external map, and 92 primary culture pages only; not complete portal catalogs'}
    dump(HERE/'institutional-source-check.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','verified_source_hashes')},ensure_ascii=False))

if __name__=='__main__':main()
