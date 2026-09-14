"""Expand publicly declared multiple API functions without requesting observations."""
from common import *
from collect_mafra import parse_detail
from collections import Counter

def compact(value):return ' '.join(value.split())

def main():
    rows=read(HERE/'inventory/mafra-catalog.json');targets=[];selector_counts=Counter();old_total=0
    for item in rows:
        if item['kind']!='OPENAPI':continue
        path=HERE/'definitions'/('mafra-schema-'+item['dataset_key']+'.json')
        if not path.exists():raise ValueError('initial_api_definitions_not_yet_complete')
        d=read(path);receipt=read(HERE/'evidence'/(d['evidence_id']+'.json'));body=gzip.decompress((HERE/receipt['raw_file']).read_bytes())
        soup=BeautifulSoup(body,'html.parser');options=soup.select('select#s_skll_sn option');selector_counts[len(options)]+=1
        old_total+=len(d.get('default_fields_before_operation_expansion',d['fields']))
        if len(options)<=1:continue
        api_id=soup.select_one('input#api_id')
        if not api_id or '/opendata/data/openDataApiDetail.do' not in body.decode('utf-8-sig'):raise ValueError('public_function_route_unresolved')
        targets.append((item,path,d,api_id['value'],[{'id':o['value'],'name':o.get_text(' ',strip=True),'locator':f'select#s_skll_sn option[{n}]'} for n,o in enumerate(options)]))
    outcomes=[];changed=[];field_count=0
    for item,path,d,api_id,options in targets:
        fields=[];requests=[];checks=[]
        for option in options:
            eid='mafra-operation-'+item['source_data_id']+'-'+option['id'];url='https://data.mafra.go.kr/opendata/data/openDataApiDetail.do'
            body,receipt=fetch(eid,url,form={'data_id':item['source_data_id'],'api_id':api_id,'skll_sn':option['id']},referer=item['url'])
            first_attempt=eid
            if not body and receipt.get('http_status') in (None,500,502,503,504):
                eid+='-retry1'
                body,receipt=fetch(eid,url,form={'data_id':item['source_data_id'],'api_id':api_id,'skll_sn':option['id']},referer=item['url'])
            check={'dataset_key':item['dataset_key'],'source_api_id':api_id,'function_id':option['id'],'function_name':option['name'],
                'source_option_locator':option['locator'],'source_selector_evidence_id':d['evidence_id'],
                'evidence_id':eid,'first_attempt_evidence_id':first_attempt,'status':'function_definition_unresolved','fields':0}
            if body:
                try:
                    soup=BeautifulSoup(body,'html.parser');function_rows=[]
                    for th in soup.select('th'):
                        if th.get_text(' ',strip=True)=='기능명':
                            td=th.find_next_sibling('td')
                            if td:function_rows.append(td.get_text(' ',strip=True))
                    if [compact(x) for x in function_rows]!=[compact(option['name'])]:raise ValueError('response_function_name_mismatch')
                    result=parse_detail(body,item['source_data_id'])
                    if result['issues'] or not result['fields']:raise ValueError('function_output_schema_unresolved')
                    for f in result['fields']:f.update(evidence_id=eid,source_function_id=option['id'],source_function_name=option['name'],source_api_id=api_id)
                    for p in result['request_parameters']:p.update(evidence_id=eid,source_function_id=option['id'],source_function_name=option['name'])
                    fields.extend(result['fields']);requests.extend(result['request_parameters']);check.update(status='column_definition_observed',fields=len(result['fields']))
                except (ValueError,KeyError,TypeError) as exc:check['error']=str(exc)
            else:
                check['error']=receipt.get('error','public_function_document_unavailable')
                check['http_status']=receipt.get('http_status')
            checks.append(check);outcomes.append(check)
        all_ok=all(x['status']=='column_definition_observed' for x in checks)
        d.update(operation_checks=checks,operation_parser_version=1,all_declared_operation_variants_observed=all_ok)
        # Replace the initial schema only when its first/default function was
        # recovered. Other observed functions remain useful if a sibling fails.
        default_observed=checks[0]['status']=='column_definition_observed'
        if fields and default_observed:
            d.setdefault('default_fields_before_operation_expansion',d['fields'])
            d.setdefault('default_request_parameters_before_operation_expansion',d.get('request_parameters',[]))
            d.update(fields=fields,request_parameters=requests,status='column_definition_observed',operation_expanded_at=now())
            d['additional_evidence_ids']=list(dict.fromkeys(d.get('additional_evidence_ids',[])+[d['evidence_id']]))
            changed.append(item['dataset_key']);field_count+=len(fields)
        dump(path,d)
    total=sum(len(read(HERE/'definitions'/('mafra-schema-'+x['dataset_key']+'.json'))['fields']) for x in rows if x['kind']=='OPENAPI')
    report={'generated_at':now(),'scope':'Public function selector variants in all 183 acquired MAFRA API listings',
        'api_selector_option_counts':dict(selector_counts),'total_declared_functions':sum(k*v for k,v in selector_counts.items()),
        'multifunction_api_count':len(targets),'expanded_api_ids':changed,'function_results':outcomes,
        'target_count':len(outcomes),'processed':len(outcomes),'status_counts':dict(Counter(x['status'] for x in outcomes)),
        'queue_exhausted':True,'all_columns_complete':False,'api_fields_before_expansion':old_total,
        'api_definition_total_fields_after_expansion':total,'documented_field_occurrences':field_count,
        'count_note':'This function queue overlaps the base API queue; do not add its field count to the base queue. When the first/default function is observed, replace its initial schema with all successfully observed function schemas. Failed sibling functions remain explicitly unresolved; the original default schema is retained separately for audit.',
        'api_observation_requests_executed':False,'pid':os.getpid()}
    dump(HERE/'mafra-operations-collection-report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='function_results'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
