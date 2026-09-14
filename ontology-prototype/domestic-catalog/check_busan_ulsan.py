"""Check new catalog boundaries and metadata provenance against saved originals."""
from common import *
from collect_busan import candidates,parse_open
from collect_ulsan import parse_page,TABS
from collections import Counter,defaultdict

def source(eid):
    receipt=read(HERE/'evidence'/(eid+'.json'));raw=gzip.decompress((HERE/receipt['raw_file']).read_bytes())
    if sha256(raw).hexdigest()!=receipt['sha256']:raise ValueError('source_hash_mismatch:'+eid)
    return raw,receipt

def main():
    checks=[]
    def check(name,ok,details=None):checks.append(dict(name=name,passed=bool(ok),details=details))
    raw,_=source('busan-public-catalog-export');export=json.loads(raw);items=read(HERE/'inventory/busan-catalog.json')
    raw,_=source('busan-catalog-first');first=json.loads(raw)
    check('busan_export_search_and_source_ids_reconcile',len(items)==len(export['result'])==int(export['total'])==int(first['result']['total_count'])==12551 and len({r['dataset_key'] for r in items})==12551)
    check('busan_all_catalog_rows_trace_to_export',all(r['source_catalog_record']==export['result'][n] and r['dataset_key']==export['result'][n]['PUBLICDATAPK'] and r['locator']==f'result[{n}]' for n,r in enumerate(items)))
    check('busan_provider_codes_namespaced_and_types_preserved',all(r['provider_id']=='busan:org:'+r['source_catalog_record']['INSTTCODE'] and r['source_service_types']==r['source_catalog_record']['DATATY'] for r in items))
    errors=[]
    for key in ['3076513','15100392','FD_41','BT_14415']:
        raw,_=source('busan-detail-'+key);soup=BeautifulSoup(raw,'html.parser')
        errors.append('서버에서 문제가 발생했습니다.' in soup.get_text() and not soup.select('table'))
    check('busan_http_200_error_pages_not_treated_as_schemas',all(errors))
    raw,_=source('busan-selectOpenData-3076513');obj=json.loads(raw);lists,links=parse_open(obj,'3076513','busan-selectOpenData-3076513')
    check('busan_quoted_commas_preserved_without_schema_promotion',len(lists)==1 and len(lists[0]['response_label_candidates'])==len(lists[0]['response_name_candidates'])==13 and any('적합, 부적합' in x for x in lists[0]['response_label_candidates']) and 'ServiceKey' not in lists[0]['response_name_candidates'] and lists[0]['status']=='flattened_parameters_not_verified_schema')
    rejected=False
    try:parse_open(obj,'wrong-parent','test')
    except ValueError:rejected=True
    check('busan_wrong_operation_parent_rejected',rejected)
    raw,_=source('busan-selectFileData-15100392');files=json.loads(raw)
    check('busan_file_count_discrepancy_visible',files['fileCnt']=='0' and len(files['fileList'])==3 and len({f['id'] for f in files['fileList']})==3)
    docs=[read(p) for p in (HERE/'definitions').glob('busan-schema-*.json')]
    failures=[];sources=set();operation_count=0
    for d in docs:
        raw,_=source(d['evidence_id']);sources.add(d['evidence_id']);original=json.loads(raw)
        if original['detail']['publicdatapk']!=d['dataset_key'] or d['dataset_metadata']!=original['detail'] or d['fields']:failures.append(d['dataset_key'])
        for q in d['declared_parameter_lists']:
            raw,_=source(q['evidence_id']);sources.add(q['evidence_id']);original=json.loads(raw)
            n=int(q['locator'].split('[')[1].split(']')[0]);op=original['opendata'][n]
            if op['listId']!=d['dataset_key'] or op.get('responseParamNm')!=q['response_raw'] or op.get('responseParamNmEn')!=q['response_name_raw']:failures.append(d['dataset_key'])
            operation_count+=1
    check('busan_current_preview_documents_match_originals',not failures,dict(documents_checked=len(docs),operations_checked=operation_count,source_receipts_checked=len(sources),failures=failures))
    report=read(HERE/'ulsan-catalog-report.json');ulsan=read(HERE/'inventory/ulsan-catalog.json')
    check('ulsan_three_tab_page_ranges_reconcile',report['snapshot_navigation_traversal_complete'] and {k:(v['pages_received'],v['rows_received']) for k,v in report['tabs'].items()}=={'FILE':(153,2284),'API':(8,116),'STD':(13,182)} and len(ulsan)==2582)
    pages={};failures=[];fingerprints=defaultdict(list)
    for r in ulsan:
        eid=r['evidence_id']
        if eid not in pages:
            raw,receipt=source(eid);soup=BeautifulSoup(raw,'html.parser')
            rebuilt,last=parse_page(raw,r['source_catalog_tab'],r['source_page'],eid,receipt['requested_url'])
            pages[eid]=(soup,rebuilt)
            fingerprint=uid('page',r['source_catalog_tab'],[(x['title'],x['provider_name'],x['external_reference_url'],x['source_description']) for x in rebuilt])
            fingerprints[fingerprint].append(eid)
        soup,rebuilt=pages[eid];node=soup.select('.result_listbox .rsl_area')[r['source_row']]
        title=node.select_one('.rsl_tit');link=title.find_parent('a')
        if r!=rebuilt[r['source_row']] or r['title']!=title.get_text(' ',strip=True) or r['external_reference_url']!=link['href']:failures.append(r['id'])
    repeats=[ids for ids in fingerprints.values() if len(ids)>1]
    check('ulsan_all_rows_and_page_identity_match_originals',not failures and len(pages)==174,dict(rows_checked=len(ulsan),pages_checked=len(pages),failures=failures))
    check('ulsan_no_identical_whole_pages_repeated',not repeats,dict(repeated_pages=repeats))
    target_counts=Counter(r['external_reference_url'] for r in ulsan)
    check('ulsan_shared_target_occurrences_not_collapsed',len(target_counts)<len(ulsan) and all(r['provider_id'] is None and not r['same_dataset_asserted'] and not r['joinability_asserted'] for r in ulsan),dict(row_occurrences=len(ulsan),distinct_target_urls=len(target_counts),shared_target_groups=sum(n>1 for n in target_counts.values())))
    raw,_=source('ulsan-catalog-page');rejected=False
    try:parse_page(raw,'FILE',1,'ulsan-catalog-page','')
    except ValueError as exc:rejected=str(exc)=='truncated_html_document'
    check('ulsan_truncated_root_html_not_a_complete_catalog',rejected)
    raw,_=source('ulsan-fileList-size15-page1');rejected=False
    try:parse_page(raw,'API',1,'ulsan-fileList-size15-page1','')
    except ValueError as exc:rejected=str(exc)=='response_catalog_tab_mismatch'
    check('ulsan_wrong_tab_rejected',rejected)
    check('no_national_or_column_completion_claimed',not read(HERE/'busan-catalog-report.json')['all_columns_complete'] and not report['all_columns_complete'] and not report['all_portal_catalogs_complete'])
    result={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'Busan export and public preview provenance, Ulsan page/row boundaries and preserved external references; not observation quality or statistical relationship validation.'}
    dump(HERE/'busan-ulsan-adapter-check.json',result)
    print(json.dumps({'passed':result['passed'],'checks':len(checks),'failed':[c for c in checks if not c['passed']]},ensure_ascii=False),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
