"""Source-grounded checks for meteorological guide and agriculture catalog adapters."""
from common import *
from check_finance_address_adapters import source
from collect_mafra import parse_detail
from collections import Counter
import re

def main():
    checks=[]
    def check(name,ok,details=None):checks.append(dict(name=name,passed=bool(ok),details=details))
    report=read(HERE/'kma-api-catalog-report.json');catalog=read(HERE/'inventory/kma-api-catalog.json')
    check('kma_public_navigation_traversed',report['root_group_count']==13 and report['guide_page_count']==56 and report['snapshot_navigation_traversal_complete'] and len(catalog)==626)
    docs=[read(p) for p in (HERE/'definitions').glob('kma-api-schema-*.json')];by={d['dataset_key']:d for d in docs}
    sources={};failures=[];count=0
    for item in catalog:
        eid=item['evidence_id']
        if eid not in sources:
            raw,_=source(eid);sources[eid]=BeautifulSoup(raw,'html.parser')
        soup=sources[eid];headings=soup.select('h4');tables=soup.select('table');d=by[item['dataset_key']]
        heading=headings[item['source_h4_index']]
        if 'API 활용신청' not in heading.get_text():failures.append((item['dataset_key'],'operation_heading_marker'))
        for f in d['fields']:
            table=tables[f['table_index']];tr=table.select('tbody tr')[f['row_index']];cells=[c.get_text(' ',strip=True) for c in tr.find_all('td',recursive=False)]
            pos=f['cell_start']
            if table.caption.get_text(strip=True)!='출력결과' or cells!=f['source_cells'] or cells[pos]!=f['name_en'] or (cells[pos+1] or cells[pos])!=f['name']:failures.append((item['dataset_key'],f['locator']))
            count+=1
    check('kma_all_output_fields_match_original_table_cells',not failures and count==4709,dict(fields_checked=count,failures=failures))
    check('kma_input_keys_and_combined_units_not_misclassified',all(f['name_en']!='authKey' and f['unit'] is None for d in docs for f in d['fields']) and any(p['name']=='authKey' for d in docs for p in d['request_parameters']))
    check('kma_shared_request_table_scope_retained',len(report['schema_association_issues'])==1 and report['schema_association_issues'][0]['section_heading']=='1. 낙뢰 원시자료 조회' and len(report['schema_association_issues'][0]['source_rows'])==4)
    check('kma_missing_payload_schemas_remain_pending',sum(d['status']=='public_guide_observed_output_schema_pending' for d in docs)==322 and all(not d['all_output_formats_documented'] and not d['api_observation_requests_executed'] for d in docs))
    report=read(HERE/'mafra-catalog-report.json');items=read(HERE/'inventory/mafra-catalog.json')
    check('mafra_three_catalog_totals_reconcile',len(items)==2142 and report['snapshot_pagination_complete'] and Counter(r['kind'] for r in items)=={'OPENAPI':183,'FILE':619,'LINK':1340})
    link=report['categories']['LINK']
    check('mafra_sort_boundary_duplicate_and_recovery_preserved',link['primary_pass_unique_ids']==1339 and len(link['duplicate_observations'])==1 and link['alternate_pass']['pages_received']==90 and link['unique_ids']==1340)
    failures=[];payloads={}
    for r in items:
        eid=r['evidence_id']
        if eid not in payloads:raw,_=source(eid);payloads[eid]=json.loads(raw)
        match=re.fullmatch(r'(\w+)\[(\d+)\]\._source',r['locator']);hit=payloads[eid][match[1]][int(match[2])]
        if hit['_source']!=r['source_catalog_record'] or hit['_id']!=r['dataset_key']:failures.append(r['id'])
    check('mafra_all_catalog_ids_resolve_to_source_hits',not failures,dict(records_checked=len(items),source_pages_checked=len(payloads),failures=failures))
    private=[r for r in items if r['source_listing_classification']=='PRIVATE']
    check('mafra_marketplace_links_not_declared_government_owned',len(private)==783 and all('/privatedata/indexPrivateDataDetail.do?' in r['url'] and r['producer_ownership_not_inferred_from_portal_membership'] and r['external_reference_url'].startswith('https://kadx.co.kr/') for r in private))
    raw,_=source('mafra-detail-probe-api');result=parse_detail(raw,'20141014000000000030')
    check('mafra_api_response_vs_example_and_request_distinction',len(result['fields'])==8 and len(result['request_parameters'])==7 and not any(f['name_en'] in ('API_KEY','ROW_NUM','totalCnt') for f in result['fields']) and any(p['name']=='API_KEY' for p in result['request_parameters']))
    api_docs=[read(p) for p in (HERE/'definitions').glob('mafra-schema-OPENAPI-*.json')]
    failures=[];count=0;api_sources={}
    for d in api_docs:
        for f in d['fields']:
            eid=f.get('evidence_id',d['evidence_id'])
            if eid not in api_sources:
                raw,_=source(eid);api_sources[eid]=BeautifulSoup(raw,'html.parser')
            soup=api_sources[eid];table=soup.select('table')[f['table_index']];tr=table.select('tbody tr')[f['row_index']]
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]
            output_role=bool(table.caption and table.caption.get_text(strip=True)=='출력결과')
            if not output_role:
                parent=table.find_parent(id='tab7');label=soup.select_one('a.tab7')
                output_role=parent is not None and label is not None and ''.join(label.find_all(string=True,recursive=False)).strip()=='출력결과'
            if not output_role or cells!=f['source_cells'] or cells[0]!=f['name_en'] or (cells[1] or cells[0])!=f['name'] or cells[1]!=f['description']:failures.append((d['dataset_key'],f['locator']))
            count+=1
    operations=read(HERE/'mafra-operations-collection-report.json')
    check('mafra_all_183_api_schemas_match_source_output_rows',len(api_docs)==183 and count==operations['api_definition_total_fields_after_expansion'] and not failures,
        dict(documents_checked=len(api_docs),fields_checked=count,failures=failures))
    failures=[]
    for result in operations['function_results']:
        raw,_=source(result['source_selector_evidence_id']);soup=BeautifulSoup(raw,'html.parser')
        options=soup.select('select#s_skll_sn option')
        option=next((o for o in options if o['value']==result['function_id']),None)
        if option is None or option.get_text(' ',strip=True)!=result['function_name']:failures.append(result['evidence_id'])
        if result['status']=='column_definition_observed':
            raw,_=source(result['evidence_id']);soup=BeautifulSoup(raw,'html.parser')
            names=[th.find_next_sibling('td').get_text(' ',strip=True) for th in soup.select('th') if th.get_text(' ',strip=True)=='기능명']
            if names!=[result['function_name']]:failures.append(result['evidence_id'])
    check('mafra_function_names_and_ids_trace_to_public_selector',not failures and operations['total_declared_functions']==197,
        dict(function_documents_checked=operations['processed'],failures=failures))
    partial=next(d for d in api_docs if d['dataset_key']=='OPENAPI-20221205000000002360')
    check('mafra_failed_sibling_not_hidden_or_invented',partial['all_declared_operation_variants_observed'] is False
        and {f['source_function_id'] for f in partial['fields']}=={'1','2','4'}
        and any(c['function_id']=='3' and c['status']=='function_definition_unresolved' for c in partial['operation_checks'])
        and len(partial['default_fields_before_operation_expansion'])==26)
    placeholders=[]
    for typ,key in [('file','20220719000000002282'),('link','20191010000000001139')]:
        raw,_=source('mafra-detail-probe-'+typ);placeholders.append(parse_detail(raw,key))
    check('mafra_placeholder_output_rows_not_fields',all(not x['fields'] and not x['issues'] for x in placeholders))
    raw,receipt=source('mafra-private-detail-probe');soup=BeautifulSoup(raw,'html.parser');key=soup.select_one('input#data_id')['value'];result=parse_detail(raw,key)
    check('mafra_public_marketplace_wrapper_preserves_reference',not result['fields'] and any(x['url'].startswith('https://kadx.co.kr/') for x in result['outgoing_links']))
    rejected=False
    try:parse_detail(raw,'wrong_data_id')
    except ValueError as exc:rejected=str(exc)=='detail_identity_mismatch'
    check('mafra_wrong_detail_identity_rejected',rejected)
    report={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,
        'scope':'Public catalog counts, identifiers, navigation and schema cell provenance; no statistical or data quality score validation.'}
    dump(HERE/'kma-mafra-adapter-check.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
