"""Final source reconciliation for the finite Busan metadata queue and nine retries."""
from common import *
from collections import Counter
from urllib.parse import urlsplit
import csv,io

def main():
    hashes={};stats=Counter();issues=[]
    def obj(eid):
        r=read(HERE/'evidence'/(eid+'.json'))
        assert r['status']=='fetched',eid
        b=gzip.decompress((HERE/r['raw_file']).read_bytes())
        assert len(b)==r['bytes'] and sha256(b).hexdigest()==r['sha256'],eid
        hashes[eid]=r['sha256'];return json.loads(b)
    catalog=read(HERE/'inventory/busan-catalog.json');raw=obj('busan-public-catalog-export')
    first=obj('busan-catalog-first')
    assert raw['total']==len(catalog)==len(raw['result'])==int(first['result']['total_count'])==12551
    assert len({r['dataset_key'] for r in catalog})==12551
    for n,(r,x) in enumerate(zip(catalog,raw['result'])):
        assert r['source_catalog_record']==x and r['locator']==f'result[{n}]' and r['dataset_key']==str(x['PUBLICDATAPK'])
        key=r['dataset_key'];d=read(HERE/'definitions'/('busan-schema-'+key+'.json'));detail=obj(d['evidence_id'])
        assert d['dataset_metadata']==detail['detail'] and str(detail['detail']['publicdatapk'])==key
        assert d['additional_metadata_as_reported']==detail.get('dataSetMeta',[])
        assert d['status']=='public_metadata_observed_schema_pending' and not d['fields'] and not d['preview_issues']
        assert d['human_approved'] is False and d['raw_values_checked'] is False
        if 'operation_metadata_as_reported' in d:
            oeid=next(e for e in d['additional_evidence_ids'] if e.startswith('busan-selectOpenData-'))
            operations=obj(oeid)['opendata'];assert operations==d['operation_metadata_as_reported']
            assert len(operations)==len(d['declared_parameter_lists'])
            stats['api_metadata_registrations']+=1
            for i,(op,decl) in enumerate(zip(operations,d['declared_parameter_lists'])):
                assert str(op['listId'])==key and decl['locator']==f'opendata[{i}]' and decl['evidence_id']==oeid
                for source_key,candidate_key in [('responseParamNm','response_label_candidates'),('responseParamNmEn','response_name_candidates')]:
                    rawtext=op.get(source_key);expected=[]
                    if rawtext:
                        try:
                            rows=list(csv.reader(io.StringIO(rawtext),strict=True,skipinitialspace=True))
                            if len(rows)==1:expected=rows[0]
                        except csv.Error:pass
                    assert expected==decl[candidate_key]
                    stats[candidate_key]+=len(expected)
                if len(decl['response_label_candidates'])!=len(decl['response_name_candidates']):
                    issues.append({'issue':'flattened_response_name_label_count_mismatch','dataset_key':key,'evidence_id':oeid,'locator':decl['locator'],
                        'name_count':len(decl['response_name_candidates']),'label_count':len(decl['response_label_candidates']),'automatic_alignment_applied':False})
                stats['operation_metadata_rows']+=1
        if 'file_metadata' in d:
            feid=next(e for e in d['additional_evidence_ids'] if e.startswith('busan-selectFileData-'))
            file=obj(feid);assert file['fileList']==d['file_metadata'] and file.get('fileCnt')==d['file_count_as_reported']
            assert all(str(f['listId'])==key for f in file['fileList'])
            stats['file_list_registrations']+=1;stats['file_metadata_rows']+=len(file['fileList'])
            if str(file.get('fileCnt'))!=str(len(file['fileList'])):
                issues.append({'issue':'source_file_count_differs_from_returned_array','dataset_key':key,'evidence_id':feid,
                    'count_as_reported':file.get('fileCnt'),'observed_rows':len(file['fileList'])})
        for link in d['outgoing_links']:
            parsed=urlsplit(link['url'])
            if not parsed.hostname:stats['source_links_without_host']+=1
            stats['outgoing_link_occurrences']+=1
        stats['public_metadata_registrations']+=1
        if (n+1)%2500==0:print('BUSAN_SOURCE_CHECK',n+1,'/ 12551',flush=True)
    retries=read(HERE/'busan-connection-retry-report.json')
    original=read(HERE/'inventory/busan-retry-original-documents.json')
    assert len(retries['outcomes'])==len(original)==9
    retry_receipts=[]
    for o in retries['outcomes']:
        assert o['new_status']=='public_metadata_observed_schema_pending' and not o['remaining_preview_issues']
        for eid in o['new_evidence_ids']:
            previous=eid.removesuffix('-connection-retry-20260914');r=read(HERE/'evidence'/(previous+'.json'));new=read(HERE/'evidence'/(eid+'.json'))
            assert r['status']=='fetch_unresolved' and new['status']=='fetched' and r['requested_url']==new['requested_url'] and r['public_json_parameters']==new['public_json_parameters']
            retry_receipts.append({'previous':previous,'replacement':eid,'previous_error':r['error']})
    report={'generated_at':now(),'passed':True,'catalog_records_reconciled':12551,'source_receipts_and_hashes_verified':len(hashes),
        'counts':dict(stats),'source_consistency_issues':issues,'connection_failures_recovered':9,'retry_receipts':retry_receipts,
        'remaining_fetch_errors_in_this_metadata_queue':0,'formal_column_definitions_from_this_queue':0,
        'all_columns_complete':False,'other_busan_catalog_tabs_complete':False,'raw_values_checked':False,'quality_scores_assigned':False,
        'scope':'Current finite public catalog export, detail/API/file-list metadata; no live API response or file-column verification',
        'verified_source_hashes':hashes}
    dump(HERE/'busan-final-metadata-source-check.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('verified_source_hashes','source_consistency_issues')},ensure_ascii=False))

if __name__=='__main__':main()
