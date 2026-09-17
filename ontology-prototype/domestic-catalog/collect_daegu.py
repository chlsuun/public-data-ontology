"""Observe Daegu's public dataset-detail registrations through its listing pages."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue,ordered_pages
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
import argparse,math,re

BASE='https://data.daegu.go.kr'
SORT='detailRegisterDate DESC, dataSetDetailId DESC'

def embedded_object(data,name):
    text=data.decode('utf-8-sig')
    match=re.search(r'var\s+'+re.escape(name)+r'\s*=\s*',text)
    if not match:raise ValueError(name+'_not_observed')
    obj,end=json.JSONDecoder().raw_decode(text[match.end():])
    if not text[match.end()+end:].lstrip().startswith(';'):raise ValueError('unexpected_object_boundary')
    return obj

def catalog_page(page,kind='all'):
    eid=f'daegu-catalog-{kind}9-{page}'
    url=BASE+'/open/data/dataList.do?'+urlencode({
        'currentPageNo':page,'orderBy':SORT,'provdMethod':kind})
    data,r=fetch(eid,url)
    if not data:raise ValueError('catalog_fetch_unresolved:'+eid)
    obj=embedded_object(data,'dataSetListInfo');s=obj['search']
    if s.get('currentPageNo')!=page or s.get('recordCountPerPage')!=9:
        raise ValueError('catalog_page_identity_mismatch')
    if s.get('provdMethod')!=kind:raise ValueError('catalog_filter_not_applied')
    records=[]
    for pos,item in enumerate(obj['dataSetList']):
        # Monthly resources under a shared dataSetId remain distinct registrations.
        key=item.get('dataSetDetailId')
        if not key:raise ValueError('dataset_detail_id_missing')
        method=item.get('provdMethod');pid=item.get('detailInsttCode')
        public={k:v for k,v in item.items() if k not in ['registerId','registerName','updateUserId','updateUserName',
            'detailRegisterId','detailUpdateUserId','detailRegisterName','detailUpdateUserName']}
        records.append(row('daegu',key,item.get('detailDataName') or item.get('dataName'),
            BASE+'/open/data/dataView.do?'+urlencode({'dataSetId':item['dataSetId'],
                'dataSetDetailId':key,'provdMethod':method}),eid,
            provider_id='daegu:org:'+pid if pid else None,provider_name=item.get('detailInsttNm'),
            source_catalog_record=public,parent_dataset_key=item.get('dataSetId'),
            locator=f'dataSetListInfo.dataSetList[{pos}]',external_reference_url=item.get('dataUrl'),
            external_reference_relation='referencesExternalPage; identity_not_validated'))
    return records,s['totalRecordCount']

def collect_one(item):
    key=item['dataset_key'];eid='daegu-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    result={'portal_id':'daegu','dataset_key':key,'evidence_id':eid,'source_url':item['url'],
        'fields':[],'status':'fetch_unresolved','human_approved':False,'raw_values_checked':False,'collected_at':now()}
    data,r=fetch(eid,item['url'])
    if data:
        try:
            obj=embedded_object(data,'dataSetDetailListInfo')
            if obj['search'].get('dataSetDetailId')!=key:raise ValueError('detail_request_identity_mismatch')
            matches=[x for x in obj['dataSetDetailList'] if x.get('dataSetDetailId')==key]
            if len(matches)!=1:raise ValueError('requested_detail_not_in_returned_page')
            meta=matches[0]
            result['dataset_metadata']={k:v for k,v in meta.items() if k not in [
                'detailRegisterId','detailUpdateUserId','detailRegisterName','detailUpdateUserName']}
            # Endpoint links describe where data is served; no bulk observation request.
            result['outgoing_links']=[{'url':meta[k],'source_property':k,'relation':'referencesExternalPage'}
                for k in ['guidanceUrl','wsdUrl','apiLinkUrl','endPointUrl','dataUrl']
                if isinstance(meta.get(k),str) and meta[k].startswith(('https://','http://'))]
            result['status']='public_metadata_observed_schema_pending'
        except (ValueError,KeyError,TypeError) as exc:result.update(status='parse_unresolved',error=str(exc)[:300])
    dump(path,result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pages',type=int);args=ap.parse_args()
    # Check the smaller API view first so its distinct coverage is visible early.
    first_api,api_total=catalog_page(1,'API');apis={r['id']:r for r in first_api}
    for page in range(2,math.ceil(api_total/9)+1):
        rows,total=catalog_page(page,'API')
        if total!=api_total:raise ValueError('api_catalog_total_changed')
        apis.update({r['id']:r for r in rows})
    store_catalog('daegu',apis.values())
    dump(HERE/'inventory/daegu-api-catalog.json',list(apis.values()))
    # Do not tell the supervisor the entire worker has ended after this subqueue.
    for item in apis.values():collect_one(item)
    first,total=catalog_page(1);expected=math.ceil(total/9);limit=min(expected,args.pages or expected)
    records={};totals={total};completed=[];received=0;duplicates=[];errors=[]
    def absorb(page,rows,count):
        nonlocal received
        completed.append(page);totals.add(count);received+=len(rows)
        for item in rows:
            if item['id'] in records:duplicates.append({'id':item['id'],'page':page})
            records[item['id']]=item
    def checkpoint():
        combined={**apis,**records}
        store_catalog('daegu',combined.values())
        dump(HERE/'inventory/daegu-catalog.json',list(combined.values()))
        report={'scope':'D-데이터허브 데이터 상세검색의 데이터셋 목록; 별도 외부 LINK 목록은 추가 조사',
            'generated_at':now(),'reported_total':total,'reported_totals':sorted(totals),'received_rows':received,
            'unique_dataset_ids':len(records),'api_view_unique_ids':len(apis),'api_view_reported_total':api_total,
            'stored_catalog_records':len(combined),'pages_received':len(completed),'pages_expected':expected,
            'duplicate_observations':duplicates,'failed_pages':errors,
            'snapshot_pagination_complete':len(completed)==expected and len(totals)==1 and received==len(records)==total and not errors,
            'all_portal_catalogs_complete':False,'all_columns_complete':False,
            'identity_note':'dataSetDetailId로 월별·파일별 등록을 구분하며 dataSetId는 상위 목록 ID로 보존',
            'schema_followup':'공개 상세정보의 API 원기관 명세·파일 헤더 수집은 후속 작업; 현재 완료 처리하지 않음'}
        dump(HERE/'daegu-catalog-report.json',report)
        dump(HERE/'daegu-collection-report.json',{
            'phase':'catalog_pagination','generated_at':now(),'target_count':expected,'processed':len(completed),
            'queue_exhausted':False,'all_columns_complete':False,'status_counts':{'catalog_pages_observed':len(completed)},
            'documented_field_occurrences':0,'pid':os.getpid()})
        print('CATALOG',len(completed),'/',expected,'registrations',len(combined),'errors',len(errors),flush=True)
    absorb(1,first,total);checkpoint()
    def page_task(page):
        try:return page,catalog_page(page),None
        except (ValueError,KeyError,TypeError) as exc:return page,None,str(exc)[:300]
    stop=ROOT/'.local/domestic-catalog/daegu.stop'
    for page,data,error in ordered_pages(page_task,range(2,limit+1),stop):
        if error:errors.append({'page':page,'error':error})
        else:absorb(page,*data)
        if page%20==0:checkpoint()
    checkpoint()
    if args.pages or stop.exists():return
    run_queue('daegu',apis.values(),collect_one,1)

if __name__=='__main__':main()
