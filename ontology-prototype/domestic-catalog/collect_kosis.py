"""Collect public KOSIS statistical dimensions and measures, without observations."""
from common import *
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from urllib.parse import urlencode
import argparse,re,sqlite3

DB=ROOT/'.local/domestic-catalog/catalog.sqlite3'

def embedded_info(data):
    html=data.decode('utf-8-sig')
    match=re.search(r"var\s+g_jsonStatInfo\s*=\s*'",html)
    if not match:raise ValueError('g_jsonStatInfo_not_observed')
    # Some official labels contain literal apostrophes. JSON syntax, rather than
    # the outer JS quote, determines the object boundary. Never execute JS.
    encoded=html[match.end():]
    try:obj,end=json.JSONDecoder().raw_decode(encoded)
    except json.JSONDecodeError:
        encoded=encoded.replace("\\'", "'")
        obj,end=json.JSONDecoder().raw_decode(encoded)
    if not encoded[end:].lstrip().startswith("';"):
        raise ValueError('unexpected_stat_info_assignment_boundary')
    if not isinstance(obj,dict):raise ValueError('stat_info_not_object')
    return obj

def parse(data,org,tbl):
    obj=embedded_info(data)
    if str(obj.get('orgId'))!=org or obj.get('tblId')!=tbl:
        raise ValueError('response_table_identity_mismatch')
    fields=[];code_coverage=[]
    for i,dim in enumerate(obj.get('classInfoList',[])):
        codes=dim.get('itmList',[])
        fields.append({'name':dim.get('classNm'),'name_en':dim.get('classEngNm'),
            'code':dim.get('classId'),'role':'statistical_dimension','datatype':None,'unit':None,
            'description':None,'locator':f'g_jsonStatInfo.classInfoList[{i}]',
            'declared_code_count':dim.get('itmCnt'),'observed_codes':codes,
            'code_list_complete':len(codes)==dim.get('itmCnt')})
        code_coverage.append({'dimension_code':dim.get('classId'),'declared':dim.get('itmCnt'),
            'observed':len(codes),'complete':len(codes)==dim.get('itmCnt')})
    info=obj.get('itemInfo') or {};items=info.get('itmList') or []
    for i,item in enumerate(items):
        fields.append({'name':item.get('scrKor'),'name_en':item.get('scrEng'),
            'code':item.get('itmId'),'role':'statistical_measure','datatype':None,
            'unit':item.get('unitNm'), 'description':None,
            'locator':f'g_jsonStatInfo.itemInfo.itmList[{i}]','definition':item,
            'unit_note':'항목 단위가 없으면 통계표 단위는 dataset_metadata에서 별도 확인'})
    period=obj.get('periodInfo') or {}
    periods=[]
    for code in (obj.get('periodStr') or '').split('#'):
        if code and period.get('code'+code):
            periods.append({'code':code,'name':period.get('name'+code),
                'start':period.get('start'+code),'end':period.get('end'+code)})
    if periods:
        fields.append({'name':period.get('periodNm'),'name_en':None,'role':'statistical_period',
            'code':'period','datatype':None,'unit':None,'periods':periods,
            'locator':'g_jsonStatInfo.periodInfo'})
    meta={k:obj.get(k) for k in ('orgId','orgNm','tblId','tblNm','tblEngNm','unitId','unitNm','unitNmEng','renewalDate','containPeriod','statId')}
    meta.update(periods=periods,dimension_code_coverage=code_coverage,
        declared_measure_count=info.get('itmCnt'),observed_measure_count=len(items),
        measure_list_complete=len(items)==info.get('itmCnt'))
    return fields,meta

def collect_one(row):
    key,_=row;org,tbl=key.split('/',1)
    eid=uid('kosis-schema',org,tbl);path=HERE/'definitions'/(eid+'.json')
    previous=read(path) if path.exists() else None
    if previous and not (previous['status']=='parse_unresolved' and previous.get('parser_version',1)<2):return previous
    url='https://kosis.kr/statHtml/statHtmlContent.do?'+urlencode({
        'orgId':org,'tblId':tbl,'vwCd':'MT_ZTITLE','dbUser':'NSI.','language':'ko'})
    data,receipt=fetch(eid,url)
    result={'dataset_key':key,'dataset_kind':'statistical_table','portal_id':'kosis',
        'source_url':url,'evidence_id':eid,'fields':[],'raw_values_checked':False,
        'human_approved':False,'status':'fetch_unresolved','collected_at':now(),'parser_version':2}
    if previous:result['previous_parser_attempt']={'status':previous['status'],'error':previous.get('error'),'collected_at':previous.get('collected_at')}
    if data:
        try:
            fields,meta=parse(data,org,tbl)
            result.update(fields=fields,dataset_metadata=meta,
                status='statistical_definition_observed' if fields else 'no_statistical_definition_observed')
        except (ValueError,KeyError,TypeError) as exc:
            result.update(status='parse_unresolved',error=str(exc)[:300])
    dump(path,result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);ap.add_argument('--workers',type=int,default=2);args=ap.parse_args()
    db=sqlite3.connect(DB)
    targets=db.execute("SELECT dataset_key,min(url) FROM records WHERE portal_id='kosis' AND kind='statistical_table' GROUP BY dataset_key ORDER BY dataset_key").fetchall();db.close()
    if args.limit:targets=targets[:args.limit]
    counts={};processed=0;field_count=0;started=now();workers=min(3,max(1,args.workers))
    stop=ROOT/'.local/domestic-catalog/kosis.stop'
    report=HERE/('kosis-collection-report.json' if not args.limit else 'kosis-adapter-check.json')
    def progress(exhausted=False):
        dump(report,{'scope':'all_acquired_identified_kosis_domestic_tables' if not args.limit else 'adapter_check',
            'target_count':len(targets),'processed':processed,'remaining':len(targets)-processed,
            'status_counts':counts,'documented_field_occurrences':field_count,'queue_exhausted':exhausted,
            'all_columns_complete':False,'started_at':started,'generated_at':now(),'pid':os.getpid()})
    progress();iterator=iter(targets)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending=set()
        while True:
            while len(pending)<workers*2 and not stop.exists():
                row=next(iterator,None)
                if row is None:break
                pending.add(pool.submit(collect_one,row))
            if not pending:break
            done,pending=wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                item=future.result();processed+=1;field_count+=len(item.get('fields',[]))
                st=item['status'];counts[st]=counts.get(st,0)+1
            if processed%25==0:
                progress();print('KOSIS',processed,'/',len(targets),counts,flush=True)
    progress(processed==len(targets));print('QUEUE_END',processed,counts,flush=True)

if __name__=='__main__':main()
