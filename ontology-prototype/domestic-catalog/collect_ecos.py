"""ECOS public statistical-code browser: catalog, classifications, codes and units."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from collections import Counter

ENDPOINT='https://ecos.bok.or.kr/api/serviceEndpoint/httpService/request.json'
PUBLIC_PAGE='https://ecos.bok.or.kr/api/#/DevGuide/StatisticalCodeSearch'

def metadata(eid,trx,data=None):
    # Exactly the anonymous defaults and read transactions in ECOS's public UI.
    body={'header':{'guidSeq':1,'trxCd':trx,'scrId':'OPENAPI','sysCd':'04','fstChnCd':'WEB',
        'langDvsnCd':'KO','envDvsnCd':'D','sndRspnDvsnCd':'S',
        'sndDtm':datetime.now().strftime('%Y%m%d%H%M%S%f')[:17],
        'ipAddr':None,'usrId':'OPENAPI','pageNum':1,'pageCnt':1000},'data':data or {}}
    b,r=fetch(eid,ENDPOINT,json_body=body,referer=PUBLIC_PAGE)
    if not b:return None
    obj=json.loads(b)
    if obj.get('message',{}).get('detailMsgs'):raise ValueError('public_metadata_service_message:'+json.dumps(obj['message'],ensure_ascii=False)[:250])
    if not isinstance(obj.get('data'),dict):raise ValueError('metadata_object_unresolved')
    return obj['data']

def collect_one(item):
    key=item['dsId'];eid='ecos-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    result={'portal_id':'ecos','dataset_key':key,'dataset_kind':'statistical_table','evidence_id':eid,
        'source_url':PUBLIC_PAGE,'fields':[],'status':'fetch_unresolved','collected_at':now(),
        'raw_values_checked':False,'human_approved':False,'dataset_metadata':item,'code_coverage':[]}
    try:
        response=metadata(eid,'OSUUA01R02',item)
        if response is not None:
            dimensions=response.get('statClfItmList') or []
            result['dimension_count_as_reported']=response.get('dataCcnt')
            result['dimension_count_reconciles']=response.get('dataCcnt')==len(dimensions)
            for pos,dimension in enumerate(dimensions):
                code_eid=eid+'-codes-'+dimension['statItmId']
                codes_data=metadata(code_eid,'OSUUA01R03',{**dimension,'dsId':key})
                codes=(codes_data or {}).get('statClfItmCdList') or []
                count=(codes_data or {}).get('dataCcnt')
                result['fields'].append({'name':dimension.get('statItmNm'),
                    'name_en':dimension.get('statItmEngNm'),'code':dimension.get('statItmId'),
                    'role':'statistical_classification','datatype':None,'unit':None,'description':None,
                    'locator':f'data.statClfItmList[{pos}]','source_definition':dimension,
                    'observed_codes':codes,'code_evidence_id':code_eid,
                    'declared_code_count':count,'code_count_reconciles':codes_data is not None and count==len(codes),
                    'note':'코드·항목별 단위는 observed_codes의 공식 값을 따른다. 코드 목록을 물리 칼럼 목록으로 합산하지 않는다.'})
                result['code_coverage'].append({'dimension':dimension['statItmId'],'evidence_id':code_eid,
                    'declared':count,'observed':len(codes),'count_reconciles':codes_data is not None and count==len(codes)})
            result['status']='statistical_definition_observed' if result['fields'] else 'definition_unresolved'
            result['all_reported_counts_reconcile']=bool(dimensions) and result['dimension_count_reconciles'] and all(c['count_reconciles'] for c in result['code_coverage'])
            if result['fields'] and not result['all_reported_counts_reconcile']:
                result['status']='statistical_definition_observed_codes_unresolved'
    except (ValueError,KeyError,TypeError) as exc:result.update(status='metadata_unresolved',error=str(exc)[:300])
    dump(path,result);return result

def main():
    eid='ecos-statistical-classification-tree';data=metadata(eid,'OSUUA01R01')
    if data is None:raise ValueError('catalog_fetch_unresolved')
    items=data.get('statClfList') or [];types=Counter(x['typ'] for x in items)
    tables=[x for x in items if x['typ']=='S'];keys={x['dsId'] for x in tables}
    dump(HERE/'inventory/ecos-classification-tree.json',{'evidence_id':eid,'source_url':PUBLIC_PAGE,'data':data})
    dump(HERE/'inventory/ecos-catalog.json',tables)
    report={'scope':'ECOS 공개 OpenAPI 통계코드검색 트리; 파일제공 표도 목록에 보존',
        'generated_at':now(),'source_evidence_id':eid,'reported_tree_nodes':data.get('dataCcnt'),
        'received_tree_nodes':len(items),'node_types':dict(types),'statistical_table_registrations':len(tables),
        'unique_table_codes':len(keys),'snapshot_catalog_count_reconciles':data.get('dataCcnt')==len(items) and len(keys)==len(tables),
        'all_portal_catalogs_complete':False,'all_columns_complete':False}
    dump(HERE/'ecos-catalog-report.json',report)
    store_catalog('ecos',[row('ecos',x['dsId'],x['dsNm'],PUBLIC_PAGE,eid,kind='statistical_table',
        source_catalog_record=x,locator='data.statClfList[dsId='+x['dsId']+']') for x in tables])
    print('CATALOG',report,flush=True);run_queue('ecos',tables,collect_one,2)

if __name__=='__main__':main()
