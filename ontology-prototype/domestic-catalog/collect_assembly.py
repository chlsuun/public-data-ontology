"""Collect the public Assembly API catalog and every advertised API schema."""
from common import *
from queue_runner import run_queue
from catalog_storage import row,store_catalog
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
import re
BASE='https://open.assembly.go.kr'

def catalog_page(page):
    eid=f'assembly-catalog-name48-{page}'
    data,r=fetch(eid,BASE+'/portal/openapi/selectInfsOpenApiListPaging.do?'+urlencode({'page':page,'rows':48,'schVOrder':'N'}))
    if not data:raise ValueError('catalog_fetch_unresolved:'+eid)
    j=json.loads(data)
    if j.get('page')!=page or not isinstance(j.get('data'),list):raise ValueError('invalid_catalog_response')
    return j,eid

def collect_one(item):
    key=item['infaId'];eid='assembly-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    seqs=re.findall(r'(?:^|,)A-(\d+)',item.get('openSrv',''))
    result={'portal_id':'assembly','dataset_key':key,'source_url':BASE+'/portal/data/service/selectAPIServicePage.do/'+key,
        'evidence_id':item['catalog_evidence_id'],'status':'api_definition_route_unresolved','fields':[],
        'request_parameters':[],'services':[],'raw_values_checked':False,'human_approved':False,'collected_at':now()}
    for seq in seqs:
        se=eid+'-'+seq;url=BASE+'/portal/data/openapi/selectOpenApiMeta.do?'+urlencode({'infId':key,'infSeq':seq})
        data,receipt=fetch(se,url);cols=[];meta={}
        if data:
            try:meta=json.loads(data).get('data') or {};cols=meta.get('columns') or []
            except (ValueError,AttributeError):pass
        result['services'].append({'infSeq':seq,'evidence_id':se,'field_count':len(cols),'status':'definition_observed' if cols else 'definition_unresolved'})
        if cols:
            result.update(source_url=url,evidence_id=se,status='column_definition_observed')
            result['request_parameters'].append({'infSeq':seq,'variables':meta.get('variables',[])})
            for pos,col in enumerate(cols):
                result['fields'].append({'name':col.get('colNm'),'name_en':col.get('colId'),
                    'description':col.get('colExp'),'datatype':None,'unit':col.get('unitNm'),
                    'role':'output_column','evidence_id':se,'infSeq':seq,'locator':f'data.columns[{pos}]','definition':col})
    dump(path,result);return result

def main():
    first,eid=catalog_page(1);pages=first['pages'];observations=[(first,eid)]
    with ThreadPoolExecutor(max_workers=2) as ex:observations.extend(ex.map(catalog_page,range(2,pages+1)))
    entries={};received=0;totals=set()
    for j,e in observations:
        totals.add(j['total']);received+=len(j['data'])
        for item in j['data']:entries[item['infaId']]={**item,'catalog_evidence_id':e}
    report={'scope':'열린국회 Open API 목록; 일반 정보공개 목록 및 소속기관 별도 API는 추가 조사',
        'reported_totals':sorted(totals),'received_rows':received,'unique_dataset_ids':len(entries),
        'pages_received':len(observations),'pages_expected':pages,
        'snapshot_pagination_complete':len(totals)==1 and len(entries)==first['total'] and received==first['total'],
        'all_portal_catalogs_complete':False,'all_columns_complete':False,'generated_at':now()}
    dump(HERE/'assembly-catalog-report.json',report);dump(HERE/'inventory/assembly-catalog.json',list(entries.values()))
    rows=[]
    for key,item in entries.items():
        rows.append(row('assembly',key,item['infaNm'],BASE+'/portal/data/service/selectAPIServicePage.do/'+key,
            item['catalog_evidence_id'],provider_id='assembly:org:'+str(item['orgCd']) if item.get('orgCd') else None,
            provider_name=item.get('orgNm'),source_catalog_record=item))
    store_catalog('assembly',rows)
    print('CATALOG',report,flush=True);run_queue('assembly',entries.values(),collect_one,2)

if __name__=='__main__':main()
