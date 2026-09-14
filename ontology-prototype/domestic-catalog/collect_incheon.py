"""Collect Incheon's anonymous public catalog and metadata, never observation APIs."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue,ordered_pages
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import argparse,math,re

BASE='https://data.incheon.go.kr'
SORT='MDFCN_DT DESC'

def public_json(eid,url,body=None):
    b,r=fetch(eid,url,json_body=body)
    if not b:raise ValueError('fetch_unresolved:'+eid)
    j=json.loads(b)
    if str(j.get('code'))!='200' or j.get('result') is None:
        raise ValueError('public_metadata_response_error:'+str(j.get('msg'))[:180])
    return j['result']

def catalog_page(page):
    eid=f'incheon-catalog-public10-{page}'
    j=public_json(eid,BASE+'/api/data/public?'+urlencode({
        'numOfRows':10,'pageNo':page,'sortColNm':SORT,'dataGrd':'5'}),{'searchTitle':''})
    if j.get('pageNo')!=page or j.get('numOfRows')!=10 or not isinstance(j.get('result'),list):
        raise ValueError('catalog_page_identity_mismatch')
    records=[]
    for pos,item in enumerate(j['result']):
        if not item.get('dataId') or not item.get('srcSe'):raise ValueError('missing_source_scoped_identity')
        key=item['srcSe']+'/'+item['dataId']
        records.append(row('incheon',key,item.get('title'),BASE+'/findData/publicDataDetail?'+urlencode({
            'dataId':item['dataId'],'srcSe':item['srcSe']}),eid,
            provider_id='incheon:org:'+item['orgCd'] if item.get('orgCd') else None,
            provider_name=item.get('orgNm'),source_catalog_record=item,locator=f'result.result[{pos}]',
            external_reference_url=item.get('pageUrl'),external_reference_relation='referencesExternalPage; identity_not_validated'))
    return records,j['totalCount']

def declared_list(text):
    """Keep ambiguous flattened strings out of documented_fields."""
    if not text:return []
    # Backtick quoted descriptions can contain commas. A complete grammar is
    # required; plain comma strings remain candidates, never verified columns.
    if re.fullmatch(r'\s*`[^`]*`(?:\s*,\s*`[^`]*`)*\s*',text):
        return re.findall(r'`([^`]*)`',text)
    return [x.strip() for x in text.split(',') if x.strip()]

def parse_operation(meta,eid,operation_id):
    if not isinstance(meta,dict) or not isinstance(meta.get('responseInfo'),list):
        raise ValueError('responseInfo_not_observed')
    fields=[]
    for pos,item in enumerate(meta['responseInfo']):
        if not item.get('responseCd'):raise ValueError('response_code_missing')
        fields.append({'name':item.get('responseNm'),'name_en':item['responseCd'],
            'datatype':item.get('responseType'),'unit':None,'description':item.get('responseNm'),
            'role':'output_column','operation_id':operation_id,'evidence_id':eid,
            'locator':f'result.responseInfo[{pos}]','definition':item})
    return fields,meta.get('paramInfo') or []

def collect_one(item):
    key=item['dataset_key'];eid=uid('incheon-schema',key);path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    source=item['source_catalog_record']
    url=BASE+'/api/data/detail?'+urlencode({'dataId':source['dataId'],'srcSe':source['srcSe']})
    result={'portal_id':'incheon','dataset_key':key,'source_url':url,'evidence_id':eid,
        'fields':[],'request_parameters':[],'declared_parameter_lists':[],'operations':[],
        'status':'fetch_unresolved','human_approved':False,'raw_values_checked':False,'collected_at':now()}
    try:
        meta=public_json(eid,url)
        if str(meta.get('dataId'))!=source['dataId'] or meta.get('srcSe')!=source['srcSe']:
            raise ValueError('detail_identity_mismatch')
        # Full public metadata is preserved in evidence; avoid copying contact details.
        result['dataset_metadata']={k:v for k,v in meta.items() if k not in ['telno','fileInfo','apiInfo','relatiedData','relatedData']}
        for pos,api in enumerate(meta.get('apiInfo') or []):
            result['declared_parameter_lists'].append({
                'locator':f'result.apiInfo[{pos}]','evidence_id':eid,
                'request_raw':api.get('requestParamNm'),'request_name_raw':api.get('requestParamNmEn'),
                'response_raw':api.get('responseParamNm'),'response_name_raw':api.get('responseParamNmEn'),
                'response_label_candidates':declared_list(api.get('responseParamNm')),
                'response_name_candidates':declared_list(api.get('responseParamNmEn')),
                'status':'flattened_parameters_not_verified_schema','source_metadata_url':api.get('metaUrl'),
                'source_information_url':api.get('informUrl')})
        result['file_metadata']=[{k:v for k,v in f.items() if k not in ['telno','telephone']} for f in meta.get('fileInfo') or []]
        for api in meta.get('openapilist') or []:
            op=api.get('operationId')
            if not op:continue
            oeid=uid('incheon-operation',op)
            operation={'operation_id':op,'evidence_id':oeid,'status':'definition_unresolved'}
            try:
                obj=public_json(oeid,BASE+'/api/data/detail/api?'+urlencode({'operationId':op}))
                fields,params=parse_operation(obj,oeid,op)
                result['fields'].extend(fields)
                result['request_parameters'].append({'operation_id':op,'parameters':params,'evidence_id':oeid})
                operation.update(status='definition_observed',field_count=len(fields))
            except (ValueError,KeyError,TypeError) as exc:operation['error']=str(exc)[:200]
            result['operations'].append(operation)
        result['status']='column_definition_observed' if result['fields'] else 'public_metadata_observed_schema_pending'
    except (ValueError,KeyError,TypeError) as exc:result.update(status='metadata_unresolved',error=str(exc)[:300])
    dump(path,result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pages',type=int);args=ap.parse_args()
    first,total=catalog_page(1);expected=math.ceil(total/10);limit=min(expected,args.pages or expected)
    records={};received=0;totals={total};completed=[];errors=[];duplicates=[]
    def absorb(page,rows,count):
        nonlocal received
        completed.append(page);totals.add(count);received+=len(rows)
        for item in rows:
            if item['id'] in records:duplicates.append({'id':item['id'],'page':page})
            records[item['id']]=item
    def checkpoint():
        report={'scope':'인천데이터포털 공공데이터 공개 등급 5 목록; 다른 별도 자료실은 추가 조사',
            'generated_at':now(),'reported_totals':sorted(totals),'reported_total':total,
            'received_rows':received,'unique_dataset_ids':len(records),'pages_received':len(completed),
            'pages_expected':expected,'failed_pages':errors,'duplicate_observations':duplicates,
            'snapshot_pagination_complete':len(completed)==expected and len(totals)==1 and received==len(records)==total and not errors,
            'all_portal_catalogs_complete':False,'all_columns_complete':False}
        store_catalog('incheon',records.values());dump(HERE/'incheon-catalog-report.json',report)
        dump(HERE/'inventory/incheon-catalog.json',list(records.values()))
        dump(HERE/'incheon-collection-report.json',{
            'phase':'catalog_pagination','generated_at':now(),'target_count':expected,'processed':len(completed),
            'queue_exhausted':False,'all_columns_complete':False,'status_counts':{'catalog_pages_observed':len(completed)},
            'documented_field_occurrences':0,'pid':os.getpid()})
        print('CATALOG',len(completed),'/',expected,'records',len(records),'errors',len(errors),flush=True)
    absorb(1,first,total);checkpoint()
    def page_task(page):
        try:return page,catalog_page(page),None
        except (ValueError,KeyError,TypeError) as exc:return page,None,str(exc)[:300]
    stop=ROOT/'.local/domestic-catalog/incheon.stop'
    for page,data,error in ordered_pages(page_task,range(2,limit+1),stop):
        if error:errors.append({'page':page,'error':error})
        else:absorb(page,*data)
        if page%5==0:checkpoint()
    checkpoint()
    if args.pages or stop.exists():return
    run_queue('incheon',records.values(),collect_one,2)

if __name__=='__main__':main()
