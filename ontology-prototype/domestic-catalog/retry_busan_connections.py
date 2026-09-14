"""One bounded retry of nine transport failures, preserving earlier evidence."""
from common import *
from collect_busan import collect_one

def main():
    report=HERE/'busan-connection-retry-report.json'
    if report.exists():print(json.dumps(read(report),ensure_ascii=False));return
    catalog={r['dataset_key']:r for r in read(HERE/'inventory/busan-catalog.json')}
    keys=['15100355','BT_13266','BT_4815','BT_5472','BT_10010','BT_10381','BT_4623','K1031_430','K1042_249']
    original_path=HERE/'inventory/busan-retry-original-documents.json'
    originals=read(original_path) if original_path.exists() else [read(HERE/'definitions'/('busan-schema-'+key+'.json')) for key in keys]
    if not original_path.exists():dump(original_path,originals)
    replacements={}
    for d in originals:
        ids=[d['evidence_id']] if d['status']=='metadata_unresolved' else [x['evidence_id'] for x in d.get('preview_issues',[])]
        for eid in ids:
            r=read(HERE/'evidence'/(eid+'.json'))
            if r['status']!='fetch_unresolved' or r.get('http_status') or not any(s in r.get('error','') for s in ('10054','Remote end closed connection')):
                raise ValueError('Only previously observed transport disconnects are eligible')
            replacements[eid]=eid+'-connection-retry-20260914'
    outcomes=[]
    for d in originals:
        assert not d.get('fields') and d.get('human_approved') is False
        key=d['dataset_key'];new=collect_one(catalog[key],force=True,evidence_replacements=replacements)
        new['previous_attempt_snapshot']='inventory/busan-retry-original-documents.json'
        new['previous_failed_evidence_ids']=[e for e in replacements if e.endswith('-'+key)]
        dump(HERE/'definitions'/('busan-schema-'+key+'.json'),new)
        outcomes.append({'dataset_key':key,'previous_status':d['status'],'new_status':new['status'],
            'remaining_preview_issues':new.get('preview_issues',[]),'new_evidence_ids':[replacements[e] for e in new['previous_failed_evidence_ids']]})
    value={'generated_at':now(),'scope':'One retry of 9 observed transport disconnects; all prior receipts retained',
        'outcomes':outcomes,'attempt_count':len(replacements),'all_columns_complete':False,
        'initial_queue_report_preserved':'busan-collection-report.json','raw_observation_requests':0}
    dump(report,value);print(json.dumps(value,ensure_ascii=False))

if __name__=='__main__':main()
