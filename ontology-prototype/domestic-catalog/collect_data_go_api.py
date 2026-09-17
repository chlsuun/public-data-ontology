"""Keep public API operation output definitions separate from request parameters."""
from common import *
from queue_runner import run_queue
from openapi_schema import embedded_document,parse_document,PARSER_VERSION
import sqlite3,argparse

def parse_tables(data,operation,evidence_id):
    soup=BeautifulSoup(data,'html.parser');fields=[];requests=[]
    for table_no,table in enumerate(soup.find_all('table')):
        cap=table.find('caption');label=cap.get_text(' ',strip=True) if cap else ''
        output='Response Element' in label or '출력결과' in label
        request='Request Parameter' in label or '요청변수' in label
        if not output and not request:continue
        headers=[x.get_text(' ',strip=True) for x in table.select('thead th')]
        # Different portal renderers reverse Korean/English name order.
        ko=next((i for i,h in enumerate(headers) if '국문' in h),None)
        en=next((i for i,h in enumerate(headers) if '영문' in h),None)
        desc=next((i for i,h in enumerate(headers) if '설명' in h),None)
        if ko is None or en is None:continue
        for pos,tr in enumerate(table.select('tbody tr')):
            cells=[td.get_text(' ',strip=True) for td in tr.find_all('td',recursive=False)]
            if len(cells)!=len(headers) or not cells[en]:continue
            item={'name':cells[ko],'name_en':cells[en],'description':cells[desc] if desc is not None else None,
                'operation':operation,'evidence_id':evidence_id,'role':'output_column' if output else 'request_parameter',
                'datatype':None,'unit':None,'locator':f'table[{table_no}].tbody.tr[{pos}]',
                'documented_attributes':dict(zip(headers,cells))}
            (fields if output else requests).append(item)
    return fields,requests

def collect_one(row):
    key,url=row;eid='data-go-api-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    previous=read(path) if path.exists() else None
    stale_schema=previous and previous.get('schema_format')=='embedded_openapi' and previous.get('schema_parser_version',1)<PARSER_VERSION
    if previous and not stale_schema and (previous.get('parser_version',1)>=2 or previous['status']=='fetch_unresolved' or previous.get('all_advertised_operations_have_fields')):return previous
    body,receipt=fetch(eid,url)
    result={'portal_id':'data-go','dataset_key':key,'dataset_kind':'API','evidence_id':eid,'source_url':url,
        'status':'fetch_unresolved','fields':[],'request_parameters':[],'operations':[],
        'human_approved':False,'raw_values_checked':False,'collected_at':now(),'parser_version':2}
    if previous:result['previous_parser_attempt']={'status':previous['status'],'field_count':len(previous['fields']),'collected_at':previous['collected_at']}
    if body:
        try:
            spec=embedded_document(body)
            if spec:
                parsed=parse_document(spec,eid)
                result.update(parsed,schema_format='embedded_openapi',status='column_definition_observed' if parsed['fields'] else 'api_definition_route_unresolved')
                dump(path,result);return result
        except (ValueError,KeyError,TypeError) as exc:result['embedded_schema_error']=str(exc)[:300]
        soup=BeautifulSoup(body,'html.parser')
        options=soup.select('#open_api_detail_select option[value]')
        hidden=soup.select_one('#publicDataDetailPk')
        for index,option in enumerate(options):
            seq=option['value'];name=option.get_text(' ',strip=True);source=eid;data=body
            if index:
                source=eid+'-operation-'+seq
                data,_=fetch(source,'https://www.data.go.kr/tcs/dss/selectApiDetailFunction.do',
                    form={'oprtinSeqNo':seq,'publicDataDetailPk':hidden.get('value','') if hidden else '',
                        'publicDataPk':key},referer=url)
            fields,requests=parse_tables(data,{'id':seq,'name':name},source) if data else ([],[])
            # Some detail pages contain only an empty placeholder for the first
            # operation. Use the same public metadata request as the UI.
            if index==0 and not fields:
                source=eid+'-operation-'+seq
                data,_=fetch(source,'https://www.data.go.kr/tcs/dss/selectApiDetailFunction.do',
                    form={'oprtinSeqNo':seq,'publicDataDetailPk':hidden.get('value','') if hidden else '',
                        'publicDataPk':key},referer=url)
                fields,requests=parse_tables(data,{'id':seq,'name':name},source) if data else ([],[])
            result['fields'].extend(fields);result['request_parameters'].extend(requests)
            result['operations'].append({'id':seq,'name':name,'evidence_id':source,
                'output_fields':len(fields),'status':'definition_observed' if fields else 'definition_unresolved'})
        result['status']='column_definition_observed' if result['fields'] else 'api_definition_route_unresolved'
        result['all_advertised_operations_have_fields']=bool(options) and all(x['output_fields'] for x in result['operations'])
    dump(path,result);return result

def upgrade_cached_swagger():
    upgraded=0;fields=0;errors=[];scanned=0
    for path in (HERE/'definitions').glob('data-go-api-schema-*.json'):
        previous=read(path)
        stale_schema=previous.get('schema_format')=='embedded_openapi' and previous.get('schema_parser_version',1)<PARSER_VERSION
        if not stale_schema and (previous.get('parser_version',1)>=2 or previous['status']!='api_definition_route_unresolved'):continue
        receipt=read(HERE/'evidence'/(previous['evidence_id']+'.json'))
        if receipt.get('status')!='fetched':continue
        scanned+=1
        try:
            spec=embedded_document(gzip.decompress((HERE/receipt['raw_file']).read_bytes()))
            if not spec:continue
            parsed=parse_document(spec,previous['evidence_id'])
            d={**previous,**parsed,'schema_format':'embedded_openapi','parser_version':2,
                'status':'column_definition_observed' if parsed['fields'] else 'api_definition_route_unresolved',
                'reparsed_at':now(),'previous_parser_attempt':{'status':previous['status'],'field_count':len(previous['fields']),'collected_at':previous['collected_at']}}
            dump(path,d);upgraded+=1;fields+=len(parsed['fields'])
        except (ValueError,KeyError,TypeError) as exc:errors.append({'dataset_key':previous['dataset_key'],'error':str(exc)[:300]})
    report={'generated_at':now(),'cached_documents_examined':scanned,'embedded_specs_reparsed':upgraded,
        'documented_response_field_occurrences':fields,'parse_errors':errors,'external_requests':0,
        'all_columns_complete':False}
    dump(HERE/'data-go-api-swagger-upgrade-report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);ap.add_argument('--workers',type=int,default=1);ap.add_argument('--cached-swagger-only',action='store_true');args=ap.parse_args()
    if args.cached_swagger_only:upgrade_cached_swagger();return
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3')
    rows=db.execute("SELECT dataset_key,min(url) FROM records WHERE portal_id='data-go' AND kind='API' GROUP BY dataset_key ORDER BY dataset_key").fetchall();db.close()
    run_queue('data-go-api',rows[:args.limit] if args.limit else rows,collect_one,min(2,max(1,args.workers)),bool(args.limit))

if __name__=='__main__':main()
