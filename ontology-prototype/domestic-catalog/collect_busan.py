"""Busan public catalog export and preview metadata; no observation downloads."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from urllib.parse import urlencode
from collections import Counter
import argparse,csv,io

BASE='https://data.busan.go.kr'

def public_json(eid,route,params,limit=8*1024*1024):
    body,receipt=fetch(eid,BASE+route,json_body=params,limit=limit,referer=BASE+'/bdip/opendata/dataSet.do')
    if not body:raise ValueError('fetch_unresolved:'+eid)
    obj=json.loads(body)
    if not isinstance(obj,dict):raise ValueError('public_json_object_missing:'+eid)
    return obj

def catalog():
    dest=HERE/'inventory/busan-catalog.json';rp=HERE/'busan-catalog-report.json'
    if dest.exists() and rp.exists() and read(rp).get('snapshot_catalog_count_reconciles'):return read(dest)
    eid='busan-public-catalog-export'
    obj=public_json(eid,'/bdip/srh/getListSearch.do',dict(searchSort='title',dataTy='',brmnCd='',insttCd='',offset=0,pagelength=-1),32*1024*1024)
    first=public_json('busan-catalog-first','/bdip/srh/getPublicDataListSearch.do',dict(searchSort='title',dataTy='',brmnCd='',insttCd='',offset=0,pagelength=12,listOrderCd='ASC'))
    src=obj['result'];total=int(obj['total']);first_rows=first['result']['rows']
    keys=[str(r['PUBLICDATAPK']) for r in src]
    if len(keys)!=len(set(keys)):raise ValueError('catalog_export_duplicate_source_ids')
    if total!=len(src) or total!=int(first['result']['total_count']):raise ValueError('catalog_export_and_search_counts_disagree')
    if not {r['fields']['PUBLICDATAPK'] for r in first_rows}<=set(keys):raise ValueError('search_ids_missing_from_export')
    records=[]
    for pos,item in enumerate(src):
        key=str(item['PUBLICDATAPK']);provider=item.get('INSTTCODE')
        records.append(row('busan',key,item['PUBLICDATASJ'],BASE+'/bdip/opendata/detail.do?'+urlencode({'publicdatapk':key}),eid,
            provider_id='busan:org:'+provider if provider else None,provider_name=item.get('INSTTNM'),
            locator=f'result[{pos}]',source_catalog_record=item,source_service_types=item.get('DATATY'),
            identity_note='PUBLICDATAPK is a Busan registration ID. A numeric ID is not automatically declared identical to a data.go.kr registration.',
            catalog_scope='public data catalog export; marketplace, custom and linked-data catalog tabs remain separate scopes'))
    store_catalog('busan',records);dump(dest,records)
    dump(rp,{'generated_at':now(),'catalog_records':len(records),'unique_registration_ids':len(set(keys)),
        'export_total':total,'search_total':int(first['result']['total_count']),'snapshot_catalog_count_reconciles':True,
        'export_evidence_id':eid,'search_evidence_id':'busan-catalog-first','navigation_evidence_id':'busan-catalog-page',
        'source_service_type_counts':dict(Counter(x.get('DATATY') for x in src)),
        'all_portal_catalogs_complete':False,'all_columns_complete':False,
        'remaining':'Other catalog tabs, public API output definitions, sheet/file schemas and linked-origin definitions.',
        'non_tabular_items_not_automatically_excluded':True})
    return records

def candidates(value):
    if not value:return []
    try:
        parsed=list(csv.reader(io.StringIO(value),strict=True,skipinitialspace=True))
        return parsed[0] if len(parsed)==1 else []
    except csv.Error:return []

def parse_open(obj,key,eid):
    api=obj.get('opendata')
    if not isinstance(api,list):raise ValueError('opendata_list_unresolved')
    lists=[];links=[]
    for pos,item in enumerate(api):
        if str(item.get('listId'))!=key:raise ValueError('operation_parent_identity_mismatch')
        lists.append({'locator':f'opendata[{pos}]','evidence_id':eid,'operation_id_as_reported':item.get('operationSeq'),
            'operation_name_as_reported':item.get('operationNm'),'request_raw':item.get('requestParamNm'),
            'request_name_raw':item.get('requestParamNmEn'),'response_raw':item.get('responseParamNm'),
            'response_name_raw':item.get('responseParamNmEn'),'response_label_candidates':candidates(item.get('responseParamNm')),
            'response_name_candidates':candidates(item.get('responseParamNmEn')),
            'status':'flattened_parameters_not_verified_schema','source_metadata_url':item.get('metaUrl')})
        for prop in ('metaUrl','guideUrl','linkUrl'):
            url=item.get(prop)
            if isinstance(url,str) and url.startswith(('http://','https://')):links.append({'url':url,'locator':f'opendata[{pos}].{prop}','evidence_id':eid})
    return lists,links

def collect_one(item,force=False,evidence_replacements=None):
    replacements=evidence_replacements or {}
    key=item['dataset_key'];eid=replacements.get('busan-selectDataSet-'+key,'busan-selectDataSet-'+key);path=HERE/'definitions'/('busan-schema-'+key+'.json')
    if path.exists() and not force:return read(path)
    d={'portal_id':'busan','dataset_key':key,'source_url':BASE+'/bdip/opendata/selectDataSet.do','evidence_id':eid,
        'additional_evidence_ids':[item['evidence_id']],'fields':[],'declared_parameter_lists':[],'outgoing_links':[],
        'status':'metadata_unresolved','human_approved':False,'raw_values_checked':False,'collected_at':now(),'preview_parser_version':1}
    try:
        obj=public_json(eid,'/bdip/opendata/selectDataSet.do',{'publicdatapk':key});detail=obj.get('detail')
        if not isinstance(detail,dict) or str(detail.get('publicdatapk'))!=key:raise ValueError('detail_identity_mismatch')
        d['dataset_metadata']=detail;d['additional_metadata_as_reported']=obj.get('dataSetMeta',[])
        types=set((item.get('source_service_types') or '').split());d['preview_issues']=[]
        if 'A' in types:
            oeid=replacements.get('busan-selectOpenData-'+key,'busan-selectOpenData-'+key)
            try:
                obj=public_json(oeid,'/bdip/opendata/selectOpenData.do',{'publicdatapk':key})
                lists,links=parse_open(obj,key,oeid);d['declared_parameter_lists']=lists;d['outgoing_links'].extend(links)
                d['additional_evidence_ids'].append(oeid)
                d['operation_metadata_as_reported']=obj['opendata']
            except (ValueError,KeyError,TypeError) as exc:d['preview_issues'].append({'evidence_id':oeid,'error':str(exc)})
        if types & {'F','L','H'} and not key.startswith('FD_'):
            feid=replacements.get('busan-selectFileData-'+key,'busan-selectFileData-'+key)
            try:
                obj=public_json(feid,'/bdip/opendata/selectFileData.do',{'publicdatapk':key});files=obj.get('fileList')
                if not isinstance(files,list) or any(str(f.get('listId'))!=key for f in files):raise ValueError('file_list_identity_mismatch')
                d['file_metadata']=files;d['file_count_as_reported']=obj.get('fileCnt');d['additional_evidence_ids'].append(feid)
                for pos,f in enumerate(files):
                    for prop in ('metaUrl','downurl'):
                        url=f.get(prop)
                        if isinstance(url,str) and url.startswith(('http://','https://')):d['outgoing_links'].append({'url':url,'locator':f'fileList[{pos}].{prop}','evidence_id':feid,'target_content_not_fetched':True})
            except (ValueError,KeyError,TypeError) as exc:d['preview_issues'].append({'evidence_id':feid,'error':str(exc)})
        d['status']='public_metadata_observed_schema_pending'
    except (ValueError,KeyError,TypeError) as exc:d['error']=str(exc)
    dump(path,d);return d

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--catalog-only',action='store_true');ap.add_argument('--limit',type=int);args=ap.parse_args()
    rows=catalog()
    if args.catalog_only:return
    rows=sorted(rows,key=lambda x:('A' not in x.get('source_service_types',''),'S' not in x.get('source_service_types',''),x['dataset_key']))
    run_queue('busan',rows[:args.limit] if args.limit else rows,collect_one,2,bool(args.limit))

if __name__=='__main__':main()
