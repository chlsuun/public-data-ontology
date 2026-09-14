"""Independent source reconciliation for this expansion, not a global recertification."""
from common import *
from collections import Counter
from urllib.parse import urlsplit,parse_qs
import re

checks=[];verified={}
def check(name,condition,detail=None):
    checks.append({'name':name,'passed':bool(condition),'detail':detail})
    if not condition:raise AssertionError(name)
def source(eid):
    r=read(HERE/'evidence'/(eid+'.json'))
    assert r['status']=='fetched',eid
    b=gzip.decompress((HERE/r['raw_file']).read_bytes())
    assert len(b)==r['bytes'] and sha256(b).hexdigest()==r['sha256'],eid
    verified[eid]=r['sha256']
    return b
def obj(eid):return json.loads(source(eid))
def soup(eid):return BeautifulSoup(source(eid),'html.parser')
def cells(tr):return [x.get_text(' ',strip=True) for x in tr.find_all(['th','td'],recursive=False)]

def main():
    raw=obj('expressway-dataset-unfiltered-list');records=read(HERE/'inventory/expressway-catalog.json')
    check('unfiltered_catalog_all_rows_and_native_service_ids_reconciled',len(raw)==len(records)==527 and len({x['service_ID'] for x in raw})==527)
    for n,(x,r) in enumerate(zip(raw,records)):
        assert x==r['source_catalog_record'] and r['dataset_key']==str(x['service_ID']) and r['locator']==f'[{n}]'
    counts=obj('expressway-unfiltered-counts')[0];bytype=Counter(r['kind'] for r in records)
    check('independent_type_and_category_totals_match_unfiltered_array',
        all(bytype[t]==int(counts[k]) for t,k in [('FILE','file_CNT'),('OPENAPI','openapi_CNT'),('ORG','org_CNT'),('LOD','lod_CNT')]) and
        all(sum(x['category']==k for x in raw)==int(counts[k.lower()+'_CNT']) for k in ('TR','CO','RO','MA','TO','BU','FU','AI')),dict(bytype))
    api=obj('expressway-open-api-intro-json-default0')['openApiInfoVOList'];apiids={x['apiId'] for x in api}
    check('separate_93_api_list_matches_catalog_with_leading_zeros_preserved',len(api)==len(apiids)==93 and apiids=={r['api_id'] for r in records if r['kind']=='OPENAPI'})
    docs=[read(HERE/'definitions'/('expressway-schema-'+r['dataset_key']+'.json')) for r in records]
    api_counter=Counter();html_columns=0;header_counts=Counter();html_status=Counter();unclassified=[]
    renderer=source('expressway-api-info-script').decode();guide=soup('expressway-detail-545')
    check('api_renderer_request_and_response_tables_and_literal_common_inputs_verified',
        guide.select_one('#listTable2 caption').get_text(' ',strip=True)=='OpenAPI 요청변수' and
        guide.select_one('#listTable3 caption').get_text(' ',strip=True)=='OpenAPI 출력결과' and
        re.search(r"if\(row.isInput=='Y'\)\s*\{\s*tbody2.append\(tr\);\s*\}\s*else\s*\{\s*tbody3.append\(tr\);",renderer) is not None and
        all(x in renderer for x in ('발급받은 인증키','검색결과 포맷','<span class="red">key</span>','<span class="red">type</span>')))
    for r,d in zip(records,docs):
        assert d['dataset_key']==r['dataset_key'] and d['source_url']==r['url']
        assert not d['human_approved'] and not d['raw_values_checked'] and not d['observation_api_called'] and not d['all_columns_complete']
        if r['kind']=='OPENAPI':
            rows=obj(d['evidence_id'])['openApiInfoVOList'];mapped={}
            for group,flag in [('fields','N'),('request_parameters','Y'),('unclassified_schema_rows',' ')]:
                for f in d[group]:
                    n=int(re.fullmatch(r'openApiInfoVOList\[(\d+)\]',f['locator'])[1]);x=rows[n]
                    assert n not in mapped and f['source_definition']==x and x['isInput']==flag
                    assert f['name_en']==x['columeCode'] and f['description']==x['columeName']
                    assert f['datatype']==(x['value'] or None) and f['unit'] is None
                    assert x['apiId']==r['api_id'];mapped[n]=True;api_counter[group]+=1
                    if group=='unclassified_schema_rows':unclassified.append({'dataset_key':r['dataset_key'],'evidence_id':d['evidence_id'],'field':f})
            assert set(mapped)==set(range(len(rows))) and len(d['common_ui_request_parameters'])==2
            metadata=obj(d['api_metadata_evidence_id'])
            assert metadata['OpenApiInfoVO']['apiId']==r['api_id'] and metadata['openApiInfoVOList']==d['api_metadata_rows']
        else:
            s=soup(d['evidence_id']);tables=s.select('table');expected=[];sample=[]
            assert s.title.get_text(' ',strip=True)=='고속도로 공공데이터 포털'
            if r['kind']=='ORG':assert s.select_one('input#datasetId')['value']==r['dataset_key']
            for tn,t in enumerate(tables):
                cap=t.caption.get_text(' ',strip=True) if t.caption else ''
                if cap=='컬럼 설명':expected.extend((tn,rn,cells(tr)) for rn,tr in enumerate(t.select('tbody tr')))
                if cap in ('샘플 데이터 입니다.','출입시설 현황 리스트','휴게소별 편의시설 현황 리스트'):
                    values=[c.get_text(' ',strip=True) for c in t.select('thead th')]
                    sample.append((tn,values))
            assert len(expected)==len(d['fields'])
            for f,(tn,rn,v) in zip(d['fields'],expected):
                assert f['source_cells']==v and f['name']==v[0] and f['description']==v[1]
                assert f['locator']==f'table[{tn}].tbody.tr[{rn}]' and f['datatype'] is None and f['unit'] is None
                assert not f['all_file_versions_share_this_definition_verified']
            assert [v for _,vs in sample for v in vs]==d['header_candidates']
            assert [(f'table[{tn}].thead th',vs) for tn,vs in sample]==[(p['locator'],p['values']) for p in d['preview_headers']]
            html_columns+=len(expected);header_counts[d['header_candidate_kind']]+=len(d['header_candidates']);html_status[d['status']]+=1
    check('all_api_schema_rows_preserved_with_requests_and_unknown_flags_separate',api_counter=={'fields':1553,'request_parameters':384,'unclassified_schema_rows':15},dict(api_counter))
    check('blank_input_output_flags_remain_unclassified_with_renderer_evidence',len({x['dataset_key'] for x in unclassified})==1 and unclassified[0]['dataset_key']=='884',len(unclassified))
    check('explicit_original_document_column_definitions_match_physical_cells',html_columns==306,{'records':html_status['file_column_definition_observed'],'fields':html_columns})
    check('sample_and_listing_headers_match_only_thead_not_observations',header_counts=={'public_html_sample_header':2728,'public_html_listing_header':9},dict(header_counts))
    original=source('expressway-original-document-script').decode();version_count=0;link_count=0;version_docs=[]
    assert '/portal/docu/getList' in original and '/portal/docu/getDocuUrlLinkList' in original
    for r in records:
        if r['kind']!='ORG':continue
        d=read(HERE/'definitions'/('expressway-schema-'+r['dataset_key']+'-files.json'));rows=obj(d['evidence_id'])
        assert len(rows)==len(d['file_versions']) and not d['fields'] and not d['parent_column_definitions_inherited']
        for n,(x,v) in enumerate(zip(rows,d['file_versions'])):
            assert x['datasetId']==r['dataset_key']==v['dataset_id'] and x['fileId']==v['file_id']
            assert x['fileName']==v['file_name'] and x['updateDate']==v['update_date_as_reported'] and v['locator']==f'[{n}]'
        if d.get('external_link_list_evidence_id'):
            links=obj(d['external_link_list_evidence_id']);assert links==d['source_external_link_rows']
            assert [(x['linkUrl'],f'[{n}].linkUrl') for n,x in enumerate(links)]==[(x['url'],x['locator']) for x in d['outgoing_links']]
        assert not d['dynamic_item_table_present'] and not d['original_files_downloaded'] and not d['usage_form_submitted']
        version_count+=len(rows);link_count+=len(d['outgoing_links']);version_docs.append(d)
    check('all_194_original_document_lists_and_version_ids_reconciled_without_download',len(version_docs)==194,{'version_rows':version_count,'outgoing_links':link_count})
    s=soup('hrfco-open-api-reference');tables=s.select('table');hrecords=read(HERE/'inventory/hrfco-catalog.json');hdocs=[]
    for r in hrecords:
        d=read(HERE/'definitions'/('hrfco-schema-'+r['dataset_key']+'.json'));hdocs.append(d)
        t=tables[d['response_table_index']];rows=t.select('tbody tr');assert len(rows)==len(d['fields'])
        for n,(tr,f) in enumerate(zip(rows,d['fields'])):
            v=cells(tr);assert v==f['source_cells'] and f['name_en']==v[1] and f['description']==v[2]
            assert f['locator']==f"table[{d['response_table_index']}].tbody.tr[{n}]" and int(v[0])==n+1 and f['datatype'] is None
            u=re.search(r'\(단위\s*:\s*([^)]*)\)',v[2]);assert f['unit']==(u[1] if u else None) and not f['unit_normalization_performed']
        request=tables[d['request_table_index']]
        for rr in d['request_parameter_rows']:
            assert rr['expanded_cells']==[c['text'] for c in rr['expanded_cell_sources']]
            current_row=int(re.search(r'tr\[(\d+)\]',rr['locator'])[1])
            for cell in rr['source_cells']+rr['expanded_cell_sources']:
                tn=int(re.search(r'table\[(\d+)\]',cell['locator'])[1])
                rn=int(re.search(r'tr\[(\d+)\]',cell['locator'])[1])
                cn=int(re.search(r'cell\[(\d+)\]',cell['locator'])[1])
                physical=tables[tn].select('tbody tr')[rn].find_all(['th','td'],recursive=False)[cn]
                assert physical.get_text(' ',strip=True)==cell['text']
                assert int(physical.get('rowspan',1))==cell['rowspan'] and int(physical.get('colspan',1))==cell['colspan']
                assert rn<=current_row<rn+cell['rowspan']
        assert not d['human_approved'] and not d['raw_values_checked'] and not d['observation_api_called']
    check('hrfco_all_reference_operation_groups_and_73_output_rows_reconciled',sum(len(c.select('.partBox'))//3 for c in s.select('.includeContainer'))==len(hrecords)==9 and sum(len(d['fields']) for d in hdocs)==73)
    check('hrfco_literal_unit_tokens_preserved_without_type_or_coordinate_inference',sum(bool(f['unit']) for d in hdocs for f in d['fields'])==24)
    hqa=read(HERE/'hrfco-source-qa.json');assert hqa['source_caution']['text_as_reported']==s.select_one('p.cauTitle.red').parent.get_text(' ',strip=True)
    check('hrfco_request_rows_and_two_source_description_mismatches_remain_separate',sum(len(d['request_parameter_rows']) for d in hdocs)==74 and len(hqa['source_description_review_candidates'])==2)
    e=read(HERE/'inventory/hrfco-error-code-tables.json');assert len(e['tables'])==1
    for row in e['tables'][0]['rows']:
        n=int(re.search(r'tr\[(\d+)\]',row['locator'])[1]);assert row['source_cells']==cells(tables[e['tables'][0]['table_index']].select('tbody tr')[n])
    check('hrfco_error_codes_and_source_caution_not_promoted_to_field_quality',len(e['tables'][0]['rows'])==18 and hqa['quality_scores_assigned'] is False)
    wqa=read(HERE/'water-source-access-qa.json');w=soup('water-api-main');source('water-public-guide');source('water-public-api-home-20260914')
    for n in wqa['source_notices']:assert n['text_as_reported']==w.select_one(n['locator']).get_text(' ',strip=True)
    check('wamis_login_boundary_and_radar_referral_scope_preserved',wqa['catalog_access']['login_or_protected_list_requested'] is False and wqa['official_referral']['equivalent_radar_service_verified'] is False)
    for eid in ['expressway-api-list-script','expressway-dataset-list-script','expressway-dataset-list-page1','expressway-public-api-list-20260914']:
        source(eid)
    dump(HERE/'expressway-source-qa.json',{'generated_at':now(),'portal_id':'expressway','scope':'Source metadata availability and consistency; not raw data QA scores',
        'catalog_counts':dict(bytype),'catalog_registration_count':527,'separate_api_count':93,
        'api_response_fields':1553,'api_source_input_rows':384,'common_ui_inputs_per_api':2,'unclassified_api_rows':unclassified,
        'original_document_definitions':{'records':56,'fields':306},'header_candidate_counts':dict(header_counts),
        'file_version_list_records':194,'file_version_rows':version_count,'external_link_occurrences':link_count,
        'definition_document_availability':{'with_fields':sum(bool(d['fields']) for d in docs),'total':527},
        'source_metadata_quality_dimensions':{'catalog_count_consistency':'matched_to_independent_current_counts','source_provenance':'sha256_and_source_positions_verified',
            'schema_completeness':'partial; sample/list headers and 15 blank-flag rows separate','freshness':'source registration/update labels retained; actual latest values not measured',
            'reliability':'not_measured','missingness':'not_measured','license_reuse':'not_reviewed'},
        'initial_metadata_request_errors':{'status':'resolved_by_source_supported_json_content_negotiation',
            'failed_evidence_ids':['expressway-open-api-intro','expressway-open-api-intro-default0','expressway-api-metadata-0618','expressway-api-schema-0618'],
            'successful_replacement_evidence_ids':['expressway-open-api-intro-json-default0','expressway-api-metadata-json-0618','expressway-api-schema-json-0618'],
            'authorization_or_service_keys_used':False},
        'source_recommendations_approved_as_relationships':False,'quality_scores_assigned':False,'raw_values_checked':False,'all_columns_complete':False})
    report={'generated_at':now(),'passed':all(c['passed'] for c in checks),'checks_passed':len(checks),'checks':checks,
        'source_hashes_verified':len(verified),'verified_sources':verified,'new_registration_count':536,
        'new_formal_field_occurrences':1932,'new_header_candidates':2737,'all_columns_complete':False,
        'scope':'Expressway 527 registrations and 194 file-list documents; HRFCO 9 reference operations; WAMIS public navigation. Not a global recertification.'}
    dump(HERE/'expressway-hrfco-source-check.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','verified_sources')},ensure_ascii=False))

if __name__=='__main__':main()
