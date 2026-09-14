"""Acquire public download-calendar metadata without requesting data files."""
from common import *
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import argparse,re

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--period',required=True);args=ap.parse_args()
    if not re.fullmatch(r'\d{4}(0[1-9]|1[0-2])',args.period):raise ValueError('expected_YYYYMM')
    catalog=read(HERE/'inventory/address-db-catalog.json')
    def one(category):
        key=category['dataset_key'].split('/',1)[1];eid=f'address-db-files-probe-{key}-{args.period}'
        params={'rtlDtaDtlSn':key,'year':int(args.period[:4]),'month':int(args.period[4:]),'expand':'Y'}
        body,receipt=fetch(eid,'https://business.juso.go.kr/api/jst/selectAttrbDBDwldList',json_body=params)
        item={'category_key':category['dataset_key'],'evidence_id':eid,'request':params,
            'source_release_flag':category['release_flag_as_reported'],'status':'fetch_unresolved',
            'source_request_definition_evidence_id':'address-JstAddressDownload-c5f05456',
            'data_files_downloaded':False,'all_historical_file_lists_complete':False}
        if body:
            try:
                data=json.loads(body)
                if data.get('status')!=200 or not isinstance(data.get('results'),dict):raise ValueError('public_metadata_response_unresolved')
                result=data['results'];item.update(status='calendar_metadata_observed',source_metadata=result)
                item['calendar_arrays']={k:{'rows':len(v),'existence_flags':dict(Counter(str(x.get('isExist')) for x in v)),
                    'existing_named_file_occurrences':sum(x.get('isExist')=='Y' and bool(x.get('fileNm')) for x in v)}
                    for k,v in result.items() if k.endswith('FileList') and isinstance(v,list)}
                item['source_valid_date_range']=result.get('vaildDate')
                item['identity_note']='List row occurrences retain array names and positions; filenames or calendar placeholders are not global dataset IDs.'
            except (ValueError,TypeError) as exc:item.update(status='metadata_unresolved',error=str(exc))
        return item
    with ThreadPoolExecutor(max_workers=2) as pool:items=list(pool.map(one,catalog))
    dest=f'inventory/address-db-file-calendar-{args.period}.json';dump(HERE/dest,items)
    report={'generated_at':now(),'scope':'public download-calendar metadata for each known category at one UI request period',
        'request_period':args.period,'categories_requested':len(items),'status_counts':dict(Counter(x['status'] for x in items)),
        'existing_named_file_occurrences':sum(v['existing_named_file_occurrences'] for x in items for v in x.get('calendar_arrays',{}).values()),
        'categories_with_source_valid_date_range':sum(bool(x.get('source_valid_date_range')) for x in items),
        'inventory':dest,'all_historical_file_lists_complete':False,'catalog_records_imported':False,
        'data_files_downloaded':False,'notes':['isExist=N rows are calendar placeholders, not acquired datasets.',
            'One request can return annual monthly lists and multiple daily months; it does not establish historical exhaustion.',
            'No download, basket, application or authentication endpoint was called.'],
        'next_action':'Inspect public UI historical calendar bounds and source IDs, enumerate supported periods, reconcile overlapping calendars before importing dated resource metadata.'}
    dump(HERE/'address-db-file-calendar-discovery-report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
