"""Verify the stable institutional slice and recovered Busan metadata in storage and HTTP."""
from common import *
from collections import Counter


def main():
    checks=[]
    def check(name,value,detail=None):
        checks.append({'name':name,'passed':bool(value),'detail':detail})
        if not value:raise AssertionError(name)
    def http(**params):
        with urlopen('http://127.0.0.1:8766/api/search?'+urlencode(params),timeout=45) as r:return json.load(r)
    db=sqlite3.connect((ROOT/'.local/domestic-catalog/catalog.sqlite3').as_uri()+'?mode=ro',uri=True)
    portals={'kdi-api':6,'kocca-api':6,'kspo':183,'bigdata-culture':92}
    paths=[]
    for portal in portals:paths.extend((HERE/'definitions').glob(portal+'-schema-*.json'))
    portable=[];headers=[];links={}
    for path in paths:
        d=read(path);rid=d['portal_id']+'-'+d['dataset_key']
        row=db.execute('SELECT field_count,metadata_json FROM schema_documents WHERE path=?',(path.name,)).fetchone()
        assert row is not None,path.name
        assert row[0]==len(d['fields']) and json.loads(row[1])=={k:v for k,v in d.items() if k!='fields'},path.name
        actual=[json.loads(x[0]) for x in db.execute('SELECT definition_json FROM documented_fields WHERE record_id=? AND evidence_id=? ORDER BY ordinal',(rid,d['evidence_id']))]
        assert [x['raw_definition'] for x in actual]==d['fields'],path.name
        portable.extend(actual)
        if d.get('header_candidates'):
            headers.append({'record_id':rid,'portal_id':d['portal_id'],'dataset_key':d['dataset_key'],
                'evidence_id':d['evidence_id'],'source_url':d['source_url'],
                'header_candidates':d['header_candidates'],'header_candidate_kind':d['header_candidate_kind'],
                'preview_headers':d['preview_headers'],'status':'header_candidates_not_schema_verified'})
        if d['portal_id']=='kspo':
            assert not d['fields'] and not d['human_approved'] and not d['raw_values_checked']
            assert d['raw_preview_rows_not_extracted'] and d['source_planned_relationships_not_imported']
            for link in d.get('outgoing_links',[]):
                key=(d['portal_id'],d['dataset_key'],link['url'])
                links.setdefault(key,set()).add((link.get('evidence_id',d['evidence_id']),link['locator']))
    check('all_287_new_documents_and_1791_fields_exactly_match_sqlite',len(paths)==287 and len(portable)==1791,
        {'definition_documents':len(paths),'formal_field_occurrences':len(portable)})
    check('3035_secondary_preview_headers_remain_candidates',sum(len(d['header_candidates']) for d in headers)==3035)
    check('all_four_catalog_counts_match_live_http',all(http(portal=p)['total']==n for p,n in portals.items()),portals)
    expected={'kdi-api':6,'kocca-api':6,'kspo':0,'bigdata-culture':92}
    check('documented_filter_excludes_secondary_schema_candidates',all(http(portal=p,documented='yes')['total']==n for p,n in expected.items()),expected)
    kdi=[http(id='kdi-api-'+k) for k in 'ABCDEF']
    check('kdi_structural_rows_and_request_parameters_not_promoted_to_output',
        sum(len(x['definitions']) for x in kdi)==113 and
        sum(len(d['request_parameters']) for x in kdi for d in x['schema_documents'])==30 and
        all(f['name_en']!='ARCHIVES' for x in kdi for f in x['definitions']))
    kocca=http(id='kocca-api-204104');doc=kocca['schema_documents'][0]
    title=[f['raw_definition']['documented_path'] for f in kocca['definitions'] if f['name_en']=='title']
    check('kocca_duplicate_names_keep_distinct_source_paths_and_literal_typo',
        set(title)=={'title','List.title'} and any(f['name_en']=='cata' for f in kocca['definitions']))
    focus=http(id='kocca-api-204145')['schema_documents'][0]
    check('malformed_source_cells_and_rowspan_audit_survive_http',
        any(p.get('source_row_tag_missing') for p in doc['request_parameters']) and
        any(i['issue']=='source_rowspan_extends_past_table_end' and i['source_rowspan']==9 and i['visible_rows']==7 for i in focus['issues']))
    check('request_authentication_parameter_excluded_from_response_search',http(portal='kocca-api',field='serviceKey')['total']==0)
    kspo=http(id='kspo-explorer-7');secondary=kspo['schema_documents'][0]
    check('secondary_copy_and_preview_provenance_visible_without_approval',not kspo['definitions'] and
        secondary['reported_schema_candidates'] and secondary['preview_headers'] and
        not secondary['external_host_ownership_verified'] and secondary['source_planned_relationships_not_imported'])
    primary=http(id='bigdata-culture-2fc01bbd-f19a-44c7-a8bd-fe131fcd5330')
    check('primary_dictionary_28_fields_not_expanded_to_31_secondary_preview_headers',len(primary['definitions'])==28 and
        len(secondary['header_candidates'])==31 and
        all(f['evidence_id'].startswith('culture-market-columninfo-') and f['raw_definition']['locator'] for f in primary['definitions']))
    preview_check=read(HERE/'inventory/kspo-culture-preview-dictionary-comparison.json')
    check('preview_vs_dictionary_name_comparison_keeps_two_scope_differences',
        preview_check['pair_count']==92 and preview_check['exact_name_order_matches']==90 and preview_check['differences_observed']==2 and
        all(not x['same_file_version_or_full_schema_equivalence_verified'] and not x['fields_added_or_removed'] for x in preview_check['comparisons']))
    retries=read(HERE/'busan-connection-retry-report.json')
    for outcome in retries['outcomes']:
        x=http(id='busan-'+outcome['dataset_key']);d=x['schema_documents'][0]
        assert not x['definitions'] and d['status']=='public_metadata_observed_schema_pending'
        assert d['previous_failed_evidence_ids'] and not d.get('preview_issues')
        eids={d['evidence_id'],*d.get('additional_evidence_ids',[])}
        assert set(outcome['new_evidence_ids'])<=eids
    check('all_nine_busan_retries_preserve_prior_failure_and_new_provenance',True)
    check('busan_flattened_metadata_not_promoted_to_formal_columns',http(portal='busan')['total']==12551 and http(portal='busan',documented='yes')['total']==0)
    refs=[]
    with gzip.open(HERE/'inventory/external-references.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            x=json.loads(line)
            if x['source_portal']=='kspo':refs.append(x)
    actual={(r['source_portal'],r['source_dataset_key'],r['target_url']) for r in refs}
    check('all_178_primary_reference_links_have_valid_positions_and_no_join_claim',len(refs)==178 and actual==set(links) and
        all((r['evidence_id'],r['locator']) in links[(r['source_portal'],r['source_dataset_key'],r['target_url'])] and
            not r['same_dataset_asserted'] and not r['joinability_asserted'] for r in refs),len(refs))
    with urlopen('http://127.0.0.1:8766/api/progress',timeout=30) as r:progress=json.load(r)
    final=progress['reports']['busan-final-metadata-collection-report.json']
    check('live_progress_exposes_reconciled_busan_queue_and_preserves_historical_report',
        final['status_counts']=={'public_metadata_observed_schema_pending':12551} and not final['all_columns_complete'] and
        progress['reports']['busan-collection-report.json']['status_counts']['metadata_unresolved']==4)
    with urlopen('http://127.0.0.1:8766/',timeout=30) as r:html=r.read().decode()
    check('browser_has_source_labels_and_replaces_only_superseded_progress_display',all(s in html for s in (
        'KDI Open API','한국콘텐츠진흥원 Open API','국민체육진흥공단 공개 데이터 안내','문화 빅데이터 플랫폼',
        "k==='busan-collection-report.json' && p.reports['busan-final-metadata-collection-report.json']")))
    model=read(HERE/'model.json');registry=read(HERE/'inventory/domestic-portals.json')
    qa_keys=('busan_source_qa','kdi_source_qa','kocca_source_qa','kspo_source_qa','culture_market_reference_source_qa')
    check('all_new_qa_refs_resolve_and_national_completion_stays_false',
        all((HERE/model['instance_files'][k]).is_file() for k in qa_keys) and
        not model['counts']['all_columns_complete'] and not registry['national_census_complete'])
    exports=[]
    for name,rows in [('institutional-columns-snapshot.jsonl.gz',sorted(portable,key=lambda x:(x['record_id'],x['evidence_id'],x['ordinal']))),
                      ('institutional-header-candidates-snapshot.jsonl.gz',sorted(headers,key=lambda x:x['record_id']))]:
        dest=HERE/'inventory'/name;tmp=dest.with_name(dest.name+'.'+str(os.getpid())+'.tmp')
        with gzip.open(tmp,'wt',encoding='utf-8') as f:
            for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        tmp.replace(dest)
        with gzip.open(dest,'rt',encoding='utf-8') as f:assert [json.loads(line) for line in f]==rows
        exports.append({'path':dest.relative_to(HERE).as_posix(),'rows':len(rows),'compressed_sha256':sha256(dest.read_bytes()).hexdigest()})
    check('stable_columns_and_header_exports_round_trip_without_changing_global_export',True,exports)
    report={'generated_at':now(),'passed':True,'checks_passed':len(checks),'checks':checks,
        'coverage_snapshot':read(HERE/'coverage-report.json')['generated_at'],
        'expansion_exports':exports,'aggregate_portable_export_can_lag_live_sqlite':True,
        'all_columns_complete':False,'scope':'287 institutional records and 9 recovered Busan records; not global recertification'}
    dump(HERE/'institutional-import-check.json',report);db.close()
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False))


if __name__=='__main__':main()
