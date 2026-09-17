"""Check new catalog identities and extracted fields against saved official sources."""
from common import *
from openapi_schema import javascript_literal
from collect_address import expanded_rows
import re,io,zipfile

def source(eid):
    receipt=read(HERE/'evidence'/(eid+'.json'))
    body=gzip.decompress((HERE/receipt['raw_file']).read_bytes())
    if sha256(body).hexdigest()!=receipt['sha256']:raise ValueError('source_hash_mismatch:'+eid)
    return body,receipt

def main():
    checks=[]
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    catalog=read(HERE/'opendart-catalog-report.json')
    check('opendart_catalog_discrepancy_exposed',catalog['catalog_records']==85 and
        catalog['introduction_records']==83 and catalog['introduction_pagination_reconciles'] and
        catalog['all_discovered_guide_groups_read'] and not catalog['snapshot_api_catalog_reconciles'])
    docs=[read(p) for p in (HERE/'definitions').glob('opendart-detail-*.json')]
    check('opendart_all_guide_ids_preserved',len(docs)==85 and {d['dataset_key'] for d in docs}==
        {r['dataset_key'] for r in read(HERE/'inventory/opendart-catalog.json')})
    failures=[];count=0
    for d in docs:
        raw,_=source(d['evidence_id']);soup=BeautifulSoup(raw,'html.parser');tables=soup.select('table')
        for f in d['fields']:
            m=re.fullmatch(r'table\[(\d+)\]\.tbody\.tr\[(\d+)\]',f['locator'])
            table=tables[int(m[1])];tr=table.select('tbody tr')[int(m[2])]
            if table.caption.get_text(strip=True)!='응답 결과' or not tr.select_one('i.iconFile') or f['source_cells']!=[c.get_text(' ',strip=True) for c in tr.find_all('td',recursive=False)]:failures.append(f['locator'])
            count+=1
    check('opendart_response_fields_match_source_rows',not failures and count==2175,{'fields_checked':count,'failures':failures})
    search=next(d for d in docs if d['dataset_key']=='2019001')
    check('opendart_control_structure_and_inputs_separated',len(search['fields'])==15 and
        {f['name_en'] for f in search['response_structure']}=={'result','list'} and
        not any(f['name_en']=='crtfc_key' for f in search['fields']) and
        any(p['name']=='crtfc_key' for p in search['request_parameters']))
    binary=[d for d in docs if d['status']=='response_control_observed_payload_unresolved']
    check('binary_payload_not_claimed_as_schema_complete',{d['dataset_key'] for d in binary}=={'2019003','2019019'} and
        all({f['name_en'] for f in d['fields']}=={'status','message'} for d in binary))
    address=[read(p) for p in (HERE/'definitions').glob('address-schema-*.json')]
    by_key={d['dataset_key']:d for d in address}
    check('address_catalog_and_guide_scope',len(address)==11 and sum(len(d['fields']) for d in address)==199 and
        read(HERE/'address-catalog-report.json')['snapshot_api_list_reconciles'] and
        not read(HERE/'address-collection-report.json')['all_columns_complete'])
    failures=[];count=0
    for d in address:
        raw,_=source(d['evidence_id']);src=raw.decode('utf-8-sig');fragments={}
        for f in d['fields']:
            start=f['literal_start']
            if start not in fragments:
                html,end=javascript_literal(src,start);fragments[start]=(BeautifulSoup(html,'html.parser').select('table'),end)
            tables,end=fragments[start];table=tables[f['table_index']]
            rows=list(expanded_rows(table));rn,values,original=rows[f['row_index']]
            if end!=f['literal_end'] or values!=f['expanded_source_cells'] or original!=f['source_cells'] or f['role']!='output_column':failures.append(f['locator'])
            count+=1
    check('address_fields_resolve_to_literal_source_tables',not failures,{'fields_checked':count,'failures':failures})
    guide=by_key['cntcInfoApi']
    check('address_actual_codes_and_rowspan_groups',any(f['name_en']=='admCd' and f['response_group_as_reported']=='juso' for f in guide['fields']) and
        any(f['name_en']=='currentPerPage' and f['response_group_as_reported']=='common' for f in guide['fields']) and
        all(f['name_en']!='confmKey' for f in guide['fields']))
    check('address_wrapped_input_name_preserves_original',all(any(p['name_en']=='useDetailAddr' and
        p['printed_identifier']=='useDetail Addr' and p['identifier_text_handling']=='HTML br layout break removed'
        for p in by_key[key]['request_parameters']) for key in ('cntcInfoUrl','cntcInfoCoordUrl','cntcInfoMobileUrl')))
    map_doc=by_key['cntcInfoMapApi'];archive,_=source('address-map-guide-2021');pdf,receipt=source('address-map-guide-pdf-2021')
    with zipfile.ZipFile(io.BytesIO(archive)) as z:matches=z.read(receipt['archive_member'])==pdf
    check('map_manual_inputs_not_promoted_to_outputs',matches and len(map_doc['request_parameters'])==14 and not map_doc['fields'] and
        any(p['name']=='Keyword' for p in map_doc['request_parameters']) and
        map_doc['status']=='public_manual_observed_output_schema_pending')
    # Positive source test for the native Incheon operation branch, previously pending.
    d=read(HERE/'definitions/incheon-schema-b44a743811f04477c0b3.json')
    raw,_=source('incheon-operation-6154530063f67cb2be43');meta=json.loads(raw)['result']
    check('incheon_native_operation_matches_real_responseInfo',len(d['fields'])==len(meta['responseInfo'])==26 and
        [f['definition'] for f in d['fields']]==meta['responseInfo'] and
        d['fields'][0]['name_en']=='LBRRY_NM' and d['fields'][0]['datatype']=='varchar(100)' and
        d['request_parameters'][0]['parameters']==meta['paramInfo'])
    report={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,
        'scope':'수집 명세·원문 위치·식별자·파일 근거 및 입력/출력 분리. 의미 동일성·상관관계 검증 아님.'}
    dump(HERE/'finance-address-adapter-check.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
