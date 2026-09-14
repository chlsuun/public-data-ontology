"""Publish verified metadata scope, preserving historical collection reports."""
from common import *
from collections import Counter


def main():
    eid='kosis-schema-a338e7bb568ef8fd9507';receipt=read(HERE/'evidence'/(eid+'.json'))
    raw=gzip.decompress((HERE/receipt['raw_file']).read_bytes())
    assert sha256(raw).hexdigest()==receipt['sha256']
    message='통계표 정보가 없습니다.'
    html=raw.decode('utf-8');start=html.index(message)
    dump(HERE/'kosis-source-error-20260914.json',{
        'generated_at':now(),'portal_id':'kosis','dataset_key':'134/DT_13403','evidence_id':eid,
        'source_url':receipt['requested_url'],'retrieved_at':receipt['retrieved_at'],
        'http_status':200,'source_message':message,'locator':{'decoded_character_start':start,'decoded_character_end':start+len(message)},
        'source_sha256_verified':receipt['sha256'],'interpretation':'The observed page lacks the statistical table metadata and reports no table information. This does not prove permanent deletion or a parser defect.',
        'original_parse_unresolved_document_preserved':True,'automatic_retry_performed':False,'all_columns_complete':False})
    comparisons=[]
    primary=read(HERE/'inventory/bigdata-culture-catalog.json')
    for record in primary:
        doc=read(HERE/'definitions'/('bigdata-culture-schema-'+record['dataset_key']+'.json'))
        names=[f['name_en'] for f in doc['fields']]
        for ref in record['source_referrals']:
            secondary=read(HERE/'definitions'/('kspo-schema-'+ref['dataset_key']+'.json'))
            for preview in secondary['preview_headers']:
                reported=preview['values']
                comparisons.append({'source_dataset_key':ref['dataset_key'],'source_evidence_id':secondary['evidence_id'],
                    'source_preview_locator':preview['locator'],'source_header_names':reported,
                    'primary_dataset_key':record['dataset_key'],'primary_evidence_id':doc['evidence_id'],
                    'primary_dictionary_names':names,'exact_name_order_match':reported==names,
                    'only_in_preview':sorted(set(reported)-set(names)),
                    'only_in_dictionary':sorted(set(names)-set(reported)),
                    'same_file_version_or_full_schema_equivalence_verified':False,
                    'fields_added_or_removed':False})
    preview_qa={'generated_at':now(),'scope':'92 KSPO-referred primary dictionaries versus secondary preview column headers',
        'comparisons':comparisons,'pair_count':len(comparisons),
        'exact_name_order_matches':sum(x['exact_name_order_match'] for x in comparisons),
        'differences_observed':sum(not x['exact_name_order_match'] for x in comparisons),
        'does_not_replace_dictionary_cell_comparison':'inventory/kspo-culture-primary-definition-comparison.json',
        'interpretation':'Preview headers and dictionary columns may cover different representations or versions. Differences are preserved without changing formal columns or asserting missing data.',
        'raw_values_checked':False,'all_columns_complete':False}
    dump(HERE/'inventory/kspo-culture-preview-dictionary-comparison.json',preview_qa)
    checked=read(HERE/'busan-final-metadata-source-check.json')
    assert checked['passed'] and checked['catalog_records_reconciled']==12551
    issues=Counter(x['issue'] for x in checked['source_consistency_issues'])
    qa={'generated_at':now(),'portal_id':'busan','scope':checked['scope'],
        'source_check_ref':'busan-final-metadata-source-check.json',
        'catalog_records_reconciled':12551,'counts':checked['counts'],
        'connection_failures_recovered':9,'remaining_fetch_errors_in_this_metadata_queue':0,
        'source_document_observations':dict(issues),
        'file_count_interpretation':{
            'observed':'fileCnt is the literal string 0 while fileList contains one or more metadata rows in 12119 responses',
            'source_field_semantics_confirmed':False,
            'interpretation':'The two values are preserved. It is unverified whether fileCnt is intended to count this array. No missing files, bad observation values, or quality score is inferred.',
            'raw_count_or_array_repaired':False},
        'flattened_response_lists':{'names':7071,'labels':7071,
            'not_added_together':True,'position_alignment_or_schema_validity_approved':False},
        'html_detail_pages':{'tested_pages_returned_http_200_error_html':True,
            'working_public_json_metadata_does_not_resolve_html_detail_pages':True},
        'formal_column_definitions_from_this_queue':0,'quality_scores_assigned':False,
        'raw_values_checked':False,'all_columns_complete':False,'national_census_complete':False,
        'remaining_scope':['Other Busan catalog tabs and administrator file lists',
            'Original publisher column dictionaries and version-specific file headers',
            'Field meaning and units, source identifiers, reuse terms, and human relationship validation'],
        'initial_queue_report_ref':'busan-collection-report.json',
        'retry_report_ref':'busan-connection-retry-report.json'}
    dump(HERE/'busan-source-qa.json',qa)
    dump(HERE/'busan-final-metadata-collection-report.json',{
        'generated_at':checked['generated_at'],'scope':'busan-final-public-metadata-after-connection-retry',
        'target_count':12551,'processed':12551,'remaining':0,
        'status_counts':{'public_metadata_observed_schema_pending':12551},
        'documented_field_occurrences':0,'queue_exhausted':True,'all_columns_complete':False,
        'source_check_ref':qa['source_check_ref'],'qa_ref':'busan-source-qa.json',
        'supersedes_current_progress_only':'busan-collection-report.json',
        'original_report_preserved':True,'no_worker_restart':True})
    model=read(HERE/'model.json')
    model['instance_files'].update({
        'busan_source_qa':'busan-source-qa.json',
        'busan_final_metadata_source_check':'busan-final-metadata-source-check.json',
        'institutional_source_check':'institutional-source-check.json',
        'kosis_observed_source_error':'kosis-source-error-20260914.json',
        'kspo_culture_preview_dictionary_comparison':'inventory/kspo-culture-preview-dictionary-comparison.json',
        'institutional_columns_snapshot':'inventory/institutional-columns-snapshot.jsonl.gz',
        'institutional_headers_snapshot':'inventory/institutional-header-candidates-snapshot.jsonl.gz'})
    dump(HERE/'model.json',model)
    registry=read(HERE/'inventory/domestic-portals.json')
    for p in registry['portals']:
        if p['id']=='busan':
            p['qa_ref']='busan-source-qa.json'
            p['metadata_queue_reconciliation_ref']='busan-final-metadata-collection-report.json'
            p['all_columns_complete']=False
    dump(HERE/'inventory/domestic-portals.json',registry)
    browser=HERE/'browser.html';html=browser.read_text(encoding='utf-8')
    if "'busan-final-metadata-collection-report.json':" not in html:
        html=html.replace('const labels={',"const labels={'busan-final-metadata-collection-report.json':'부산 · 재조회 후 공개 메타데이터',",1)
        html=html.replace("'busan-collection-report.json':'부산 · 공개 미리보기 메타데이터'",
            "'busan-collection-report.json':'부산 · 재조회 이전 기록'")
        html=html.replace(".filter(([k,v])=>v.target_count!==undefined)",
            ".filter(([k,v])=>v.target_count!==undefined && !(k==='busan-collection-report.json' && p.reports['busan-final-metadata-collection-report.json']))")
        browser.write_text(html,encoding='utf-8')
    print(json.dumps({'reports_enriched':True,'preview_dictionary_pairs':preview_qa['pair_count'],
        'exact_name_order_matches':preview_qa['exact_name_order_matches'],
        'differences_observed':preview_qa['differences_observed']},ensure_ascii=False))


if __name__=='__main__':main()
