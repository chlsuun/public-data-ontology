"""Source-backed regression checks for embedded OpenAPI and the Library manual."""
from common import *
from openapi_schema import embedded_document,javascript_literal,local_ref,parse_document

def main():
    checks=[]
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    def rejected(text):
        try:javascript_literal(text,0)
        except ValueError:return True
        return False
    check('javascript_expressions_never_executed',rejected('`${someFunction()}`') and rejected('`unterminated'))
    fixture=read(HERE/'definitions/data-go-api-schema-15000827.json')
    check('actual_travel_warning_response_and_request_separated',
        len(fixture['fields'])==26 and len(fixture['request_parameters'])==7 and
        any(f['name_en']=='iso_code' and f['description']=='ISO 국가코드' for f in fixture['fields']) and
        all(f['name_en']!='serviceKey' for f in fixture['fields']) and
        any(p['definition'].get('name')=='serviceKey' for p in fixture['request_parameters']))
    # Exercise local references, arrays and alternative response media without HTTP.
    doc={'openapi':'3.0.3','paths':{'/books':{'get':{
        'parameters':[{'name':'authKey','in':'query','schema':{'type':'string'}}],
        'responses':{'200':{'$ref':'#/components/responses/Books'}}}}},'components':{
        'responses':{'Books':{'content':{'application/json':{'schema':{
            'type':'object','properties':{'books':{'type':'array','items':{'$ref':'#/components/schemas/Book'}}}}}}}},
        'schemas':{'Book':{'type':'object','properties':{'isbn':{'type':'string'}}}}}}
    result=parse_document(doc,'synthetic-check-only')
    check('openapi3_referenced_response_array_locator',len(result['fields'])==1 and
        result['fields'][0]['schema_path']==['books','[]','isbn'] and
        local_ref(doc,result['fields'][0]['locator'].removeprefix('swaggerJson'))=={'type':'string'} and
        result['all_advertised_operations_have_fields'])
    doc['components']['schemas']['Book']['properties']['next']={'$ref':'#/components/schemas/Book'}
    doc['components']['schemas']['Book']['properties']['remote']={'$ref':'https://example.invalid/schema.json'}
    doc['components']['schemas']['Book']['additionalProperties']={'type':'string'}
    partial=parse_document(doc,'synthetic-check-only')
    reasons={i['reason'] for i in partial['issues']}
    check('recursive_external_dynamic_schemas_remain_unresolved',not partial['all_advertised_operations_have_fields'] and
        {'recursive_schema_reference','external_schema_reference_not_fetched','additional_dynamic_properties_not_enumerated'}<=reasons)
    fields_checked=0;specs_checked=0;failures=[]
    for path in (HERE/'definitions').glob('data-go-api-schema-*.json'):
        d=read(path)
        if d.get('schema_format')!='embedded_openapi':continue
        receipt=read(HERE/'evidence'/(d['evidence_id']+'.json'))
        raw=gzip.decompress((HERE/receipt['raw_file']).read_bytes())
        spec=embedded_document(raw);specs_checked+=1
        if sha256(raw).hexdigest()!=receipt['sha256']:failures.append(path.name+': hash')
        for f in d['fields']:
            try:matches=local_ref(spec,f['locator'].removeprefix('swaggerJson'))==f['definition']
            except (ValueError,KeyError,TypeError):matches=False
            if not matches:failures.append({'file':path.name,'locator':f['locator']})
            fields_checked+=1
    check('every_cached_openapi_field_resolves_to_saved_source',specs_checked>=255 and not failures,
        {'specifications':specs_checked,'fields_checked':fields_checked,'failures':failures})
    catalog=read(HERE/'library-catalog-report.json')
    definitions=[read(p) for p in (HERE/'definitions').glob('library-schema-*.json')]
    services={d['dataset_metadata']['number']:d for d in definitions}
    check('library_19_services_18_endpoints_preserved',set(services)==set(range(1,20)) and
        catalog['catalog_records']==19 and catalog['distinct_endpoint_urls']==18 and
        services[4]['dataset_metadata']['endpoint_urls']==services[5]['dataset_metadata']['endpoint_urls'] and
        services[4]['dataset_key']!=services[5]['dataset_key'])
    check('library_split_url_reconstructed_from_printed_cells',services[15]['dataset_metadata']['endpoint_urls']==
        ['http://data4library.kr/api/extends/loanItemSrchByLib'])
    check('library_visually_reviewed_page5_fields',all(any(f['name_en']==name and f['pdf_page']==5 and
        f['printed_cell_bbox'] for f in services[1]['fields']) for name in ('latitude','longitude','BookCount')))
    check('library_authentication_inputs_not_response_columns',sum(len(d['fields']) for d in definitions)==436 and
        all(f['name_en']!='authKey' for d in definitions for f in d['fields']) and
        all(any(p['name']=='authKey' for p in d['request_parameters']) for d in definitions))
    tables=read(HERE/'inventory/library-manual-tables.json')['tables']
    lookup={(t['page'],t['table']):t for t in tables}
    check('library_field_rows_match_saved_manual_tables',all(
        f['source_row']==lookup[f['pdf_page'],f['pdf_table']]['rows'][f['pdf_row']-1]
        for d in definitions for f in d['fields']))
    check('library_manual_scope_not_entire_portal_complete',catalog['snapshot_manual_catalog_reconciles'] and
        not catalog['all_portal_catalogs_complete'] and not catalog['all_columns_complete'] and
        not catalog['rejected_response_rows'] and not catalog['services_missing_endpoint_url'])
    report={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,
        'scope':'원문 명세 추출·참조 위치·PDF 표 및 요청/출력 분리 검사. 실제 데이터 분석·관계 승인 아님.'}
    dump(HERE/'new-adapter-check.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
