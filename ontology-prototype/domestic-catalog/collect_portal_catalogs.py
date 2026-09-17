"""Public catalog and API-definition adapters for NEIS and Gyeonggi."""
from common import *
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlencode
from collections import Counter

PORTALS={'neis':'https://open.neis.go.kr','gyeonggi':'https://data.gg.go.kr'}

def page_data(portal,page):
    prefix='gg' if portal=='gyeonggi' else portal
    eid=f'{prefix}-catalog-name20-{page}' if portal=='gyeonggi' else f'{prefix}-catalog-{page}'
    params={'page':page,'sort':'name','size':20} if portal=='gyeonggi' else {'page':page}
    b,r=fetch(eid,PORTALS[portal]+'/portal/data/dataset/searchDataset.do?'+urlencode(params))
    if not b:raise RuntimeError(str(r))
    data=json.loads(b)
    if portal=='gyeonggi':
        rows=data['result']['contents'];info=data['result']['pageInfo']
        assert info['currentPage']==page
        total,pages=info['totalElements'],info['totalPages']
    else:
        rows=data['data'];assert data['page']==page
        total,pages=data['total'],data['pages']
    time.sleep(.25)
    return rows,total,pages,eid

def schema(portal,item):
    prefix='gg' if portal=='gyeonggi' else portal
    key=item['infId'];eid=f'{prefix}-api-schema-{key}'
    cached=HERE/'definitions'/(eid+'.json')
    if cached.exists() and read(cached).get('status')=='column_definition_observed':
        return 'column_definition_observed'
    u=PORTALS[portal]+'/portal/data/openapi/selectOpenApiMeta.do?'+urlencode({'infId':key,'infSeq':item['acolInfSeq']})
    b,r=fetch(eid,u)
    try:
        d=json.loads(b) if b else {}
        if portal=='neis':d=d.get('data',{})
        cols=d.get('columns') or []
        fields=[{'name':x.get('colNm'),'name_en':x.get('colId'),'description':x.get('colExp'),
                 'unit':x.get('unitNm'),'datatype':None,'source_definition':x} for x in cols]
        result={'portal_id':portal,'dataset_key':key,'evidence_id':eid,'source_url':u,
            'status':'column_definition_observed' if fields else 'no_definition_observed',
            'fields':fields,'request_parameters':d.get('variables') or [],
            'api_endpoint':d.get('apiEp'),'api_resource':d.get('apiRes'),
            'human_approved':False,'raw_values_checked':False,
            'note':'응답 봉투의 코드·메시지 항목도 원문대로 보존; 분석변수 여부 미분류'}
    except Exception as e:
        result={'portal_id':portal,'dataset_key':key,'evidence_id':eid,'source_url':u,
            'status':'parse_or_fetch_unresolved','fields':[],'error':str(e)[:150]}
    dump(HERE/'definitions'/(eid+'.json'),result);time.sleep(.25)
    return result['status']

def collect(portal):
    rows,total,pages,eid=page_data(portal,1)
    entries=[{**r,'catalog_evidence_id':eid} for r in rows]
    totals={total}
    with ThreadPoolExecutor(max_workers=3) as ex:
        fs=[ex.submit(page_data,portal,p) for p in range(2,pages+1)]
        for i,f in enumerate(as_completed(fs),1):
            rr,t,_,e=f.result();totals.add(t);entries.extend({**r,'catalog_evidence_id':e} for r in rr)
            if i%50==0:print(portal,'PAGES',i+1,'/',pages,flush=True)
    unique={r['infId']:r for r in entries}
    previous=HERE/'inventory'/(portal+'-catalog.json')
    previous_entries=read(previous) if previous.exists() else []
    current_unique=len(unique)
    # Preserve earlier evidence, then prefer the explicitly sorted observation.
    unique={**{r['infId']:r for r in previous_entries},**unique}
    report={'portal_id':portal,'reported_total':total,'reported_totals_seen':sorted(totals),
        'pages_requested':pages,'received_rows':len(entries),'unique_dataset_ids':len(unique),
        'unique_ids_in_sorted_pass':current_unique,'prior_observed_ids':len(previous_entries),
        'sort':'name' if portal=='gyeonggi' else 'portal_default',
        'snapshot_pagination_complete':len(totals)==1 and len(unique)==total,
        'all_columns_complete':False,'generated_at':now()}
    dump(HERE/'inventory'/(portal+'-catalog.json'),sorted(unique.values(),key=lambda r:r['infId']))
    targets=[r for r in unique.values() if r.get('acolInfSeq')]
    status=Counter()
    with ThreadPoolExecutor(max_workers=3) as ex:
        fs=[ex.submit(schema,portal,r) for r in targets]
        for i,f in enumerate(as_completed(fs),1):
            status[f.result()]+=1
            if i%100==0:print(portal,'API_DEFINITIONS',i,'/',len(targets),dict(status),flush=True)
    report.update(api_definition_targets=len(targets),api_definition_status_counts=dict(status),
        datasets_without_api_definition_route=len(unique)-len(targets))
    dump(HERE/(portal+'-collection-report.json'),report)
    print('DONE',portal,report,flush=True)

if __name__=='__main__':
    for portal in ('neis','gyeonggi'):collect(portal)
