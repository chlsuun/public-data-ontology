"""Evidence and import checks; these do not validate statistical relationships."""
from common import *
from build_inventory import DB
from browse import query
from collections import Counter
import sqlite3

def main():
    db=sqlite3.connect(DB);checks=[]
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    summary=read(HERE/'coverage-report.json');report=read(HERE/'import-report.json')
    check('sqlite_integrity',db.execute('PRAGMA quick_check').fetchone()[0]=='ok')
    check('foreign_key_integrity',not db.execute('PRAGMA foreign_key_check').fetchall())
    registered={p['id'] for p in read(HERE/'inventory/domestic-portals.json')['portals']}
    check('domestic_portals_only',set(r[0] for r in db.execute('SELECT DISTINCT portal_id FROM records'))<=registered)
    check('no_false_full_coverage',summary['all_columns_complete'] is False and summary['all_domestic_portals_complete'] is False)
    check('catalog_count_reconciles',summary['total_catalog_records']==db.execute('SELECT count(*) FROM records').fetchone()[0])
    d=report['sources']['data-go']
    check('quarantine_not_silently_dropped',d['source_rows']==d['imported_records']+d['invalid_rows']+d['implicated_rows'])
    check('source_count_discrepancy_exposed',d['advertised_count_matches'] is False and d['source_rows']!=d['advertised_rows'])
    check('standard_provider_occurrences_preserved',db.execute("SELECT count(distinct provider_id) FROM records WHERE portal_id='data-go' AND dataset_key='15013117'").fetchone()[0]>1)
    check('seoul_department_not_guessed_as_agency',db.execute("SELECT count(*) FROM records WHERE portal_id='seoul' AND provider_id IS NOT NULL").fetchone()[0]==0)
    check('kosis_links_missing_identity_retained',db.execute("SELECT count(*) FROM records WHERE kind='catalog_entry_link_review'").fetchone()[0]==report['sources']['kosis']['entries_requiring_link_review'])
    for portal in ('neis','gyeonggi'):
        r=read(HERE/(portal+'-collection-report.json'))
        check(portal+'_pagination_reconciles',r['snapshot_pagination_complete'] and r['reported_total']==db.execute('SELECT count(*) FROM records WHERE portal_id=?',(portal,)).fetchone()[0])
    for portal in ('ecos','yeongdeungpo'):
        path=HERE/(portal+'-catalog-report.json')
        if path.exists():
            r=read(path)
            expected=r.get('unique_table_codes',r.get('unique_dataset_ids'))
            reconciles=r.get('snapshot_catalog_count_reconciles',r.get('snapshot_pagination_complete'))
            check(portal+'_catalog_reconciles',reconciles and expected==db.execute('SELECT count(*) FROM records WHERE portal_id=?',(portal,)).fetchone()[0])
    if db.execute("SELECT 1 FROM records WHERE portal_id='ecos' LIMIT 1").fetchone():
        check('ecos_classification_and_unit_preserved',db.execute("SELECT count(*) FROM documented_fields WHERE record_id='ecos-102Y004' AND json_extract(definition_json,'$.raw_definition.code')='ACC_ITEM' AND json_extract(definition_json,'$.raw_definition.observed_codes[0].untNm')='십억원'").fetchone()[0]==1)
    for portal in ('incheon','daegu'):
        path=HERE/(portal+'-catalog-report.json')
        if not path.exists():continue
        r=read(path)
        check(portal+'_pagination_accounting',r['received_rows']==r['unique_dataset_ids']+len(r['duplicate_observations']) and r['pages_received']<=r['pages_expected'])
        complete=r['pages_received']==r['pages_expected'] and len(r['reported_totals'])==1 and r['received_rows']==r['unique_dataset_ids']==r['reported_total'] and not r['failed_pages']
        check(portal+'_partial_catalog_not_marked_complete',r['snapshot_pagination_complete']==complete and r['all_columns_complete'] is False)
    check('incheon_source_namespace_preserved',db.execute("SELECT count(*) FROM records WHERE portal_id='incheon' AND dataset_key != json_extract(metadata_json,'$.source_catalog_record.srcSe') || '/' || json_extract(metadata_json,'$.source_catalog_record.dataId')").fetchone()[0]==0)
    check('daegu_monthly_resources_not_collapsed',db.execute("SELECT max(n) FROM (SELECT count(distinct dataset_key) n FROM records WHERE portal_id='daegu' GROUP BY json_extract(metadata_json,'$.parent_dataset_key'))").fetchone()[0]>1)
    rid='incheon-7661IVAWM27C61E190/15148225'
    detail=query({'id':[rid]})
    if 'error' not in detail:
        docs=detail.get('schema_documents',[])
        observed=[p for d in docs for p in d.get('declared_parameter_lists',[])]
        check('incheon_flattened_headers_remain_candidates',not detail['definitions'] and any(p['response_label_candidates']==['header','body'] for p in observed))
        from collect_incheon import declared_list
        check('quoted_parameter_commas_preserved',any(len(declared_list(p['request_raw']))==9 for p in observed))
        check('incheon_candidate_search_works',query({'portal':['incheon'],'field':['header']})['total']>=1)
        check('candidate_only_records_excluded_from_documented_filter',query({'portal':['incheon'],'q':['출국장 혼잡도 조회'],'documented':['yes']})['total']==0)
    check('declared_fields_remain_unverified',db.execute("SELECT count(*) FROM fields WHERE status!='declared_token_unverified'").fetchone()[0]==0)
    check('request_and_output_separated',set(x[0] for x in db.execute('SELECT DISTINCT role FROM fields'))=={'request','output'})
    check('actual_neis_school_definition',db.execute("SELECT count(*) FROM documented_fields WHERE record_id='neis-OPEN17020190531110010104913' AND name_en='SD_SCHUL_CODE' AND name='행정표준코드'").fetchone()[0]==1)
    check('actual_seoul_district_definition',db.execute("SELECT count(*) FROM documented_fields d JOIN records r ON r.id=d.record_id WHERE r.portal_id='seoul' AND r.dataset_key='OA-22172' AND d.name_en='ADSTRD_CD' AND d.name='행정동_코드'").fetchone()[0]>=1)
    check('kosis_structured_dimensions_acquired',db.execute("SELECT count(*) FROM documented_fields d JOIN records r ON r.id=d.record_id WHERE r.portal_id='kosis' AND json_extract(d.definition_json,'$.role')='statistical_dimension'").fetchone()[0]>0)
    if db.execute("SELECT 1 FROM records WHERE portal_id='library' LIMIT 1").fetchone():
        r=read(HERE/'library-catalog-report.json')
        check('library_manual_catalog_reconciles',r['snapshot_manual_catalog_reconciles'] and r['catalog_records']==19==db.execute("SELECT count(*) FROM records WHERE portal_id='library'").fetchone()[0] and not r['all_portal_catalogs_complete'])
        check('library_manual_response_fields_indexed',db.execute("SELECT count(*) FROM documented_fields d JOIN records r ON r.id=d.record_id WHERE r.portal_id='library'").fetchone()[0]==436)
        check('library_operator_not_guessed_as_data_provider',db.execute("SELECT count(*) FROM records WHERE portal_id='library' AND provider_name IS NOT NULL").fetchone()[0]==0)
        check('library_response_field_search',query({'portal':['library'],'field':['BookCount'],'documented':['yes']})['total']>=1)
    check('embedded_openapi_source_field_search',db.execute("SELECT count(*) FROM documented_fields d JOIN records r ON r.id=d.record_id WHERE r.portal_id='data-go' AND r.dataset_key='15000827' AND d.name_en='iso_code'").fetchone()[0]==1)
    for portal,count in (('opendart',85),('address',11)):
        check(portal+'_api_catalog_ids_indexed',db.execute("SELECT count(*) FROM records WHERE portal_id=? AND kind='documented_api_service'",(portal,)).fetchone()[0]==count)
    check('address_db_category_namespace_preserved',db.execute("SELECT count(*) FROM records WHERE portal_id='address' AND kind='download_dataset_category' AND dataset_key='db/' || json_extract(metadata_json,'$.source_catalog_record.RTL_DTA_DTL_SN')").fetchone()[0]==31)
    check('address_db_fields_indexed',db.execute("SELECT count(*) FROM documented_fields d JOIN records r ON d.record_id=r.id WHERE r.portal_id='address' AND r.kind='download_dataset_category'").fetchone()[0]==1117)
    check('seoul_statistics_reference_identity_preserved',db.execute("SELECT count(*) FROM documented_fields d JOIN records r ON d.record_id=r.id WHERE r.portal_id='seoul' AND r.dataset_key='OA-996' AND d.name='에너지종류별'").fetchone()[0]==1)
    check('kma_guide_navigation_and_catalog_reconcile',read(HERE/'kma-api-catalog-report.json')['snapshot_navigation_traversal_complete'] and db.execute("SELECT count(*) FROM records WHERE portal_id='kma-api'").fetchone()[0]==626)
    check('kma_output_table_fields_indexed',db.execute("SELECT count(*) FROM documented_fields d JOIN records r ON d.record_id=r.id WHERE r.portal_id='kma-api'").fetchone()[0]==4709)
    check('kma_auth_input_not_promoted_to_output',query({'portal':['kma-api'],'field':['authKey'],'documented':['yes']})['total']==0)
    check('mafra_catalog_source_totals_reconcile',read(HERE/'mafra-catalog-report.json')['snapshot_pagination_complete'] and db.execute("SELECT count(*) FROM records WHERE portal_id='mafra'").fetchone()[0]==2142)
    check('mafra_native_institution_code_namespace',db.execute("SELECT count(*) FROM records WHERE portal_id='mafra' AND provider_id IS NOT NULL AND provider_id NOT LIKE 'mafra:org:%'").fetchone()[0]==0)
    check('mafra_marketplace_listing_routes_preserved',db.execute("SELECT count(*) FROM records WHERE portal_id='mafra' AND json_extract(metadata_json,'$.source_listing_classification')='PRIVATE' AND url LIKE 'https://data.mafra.go.kr/privatedata/indexPrivateDataDetail.do?%'").fetchone()[0]==783)
    check('mafra_first_api_real_output_definition',db.execute("SELECT count(*) FROM documented_fields WHERE record_id='mafra-OPENAPI-20141014000000000030' AND name_en='PRMISN_NO' AND name='허가번호'").fetchone()[0]==1)
    check('opendart_catalog_mismatch_remains_visible',read(HERE/'opendart-catalog-report.json')['snapshot_api_catalog_reconciles'] is False)
    check('opendart_output_field_search',query({'portal':['opendart'],'field':['rcept_no'],'documented':['yes']})['total']>0)
    check('address_output_field_search',query({'portal':['address'],'field':['admCd'],'documented':['yes']})['total']>0)
    check('address_input_key_excluded_from_output_search',query({'portal':['address'],'field':['confmKey'],'documented':['yes']})['total']==0)
    check('keyword_lookup_finds_real_definition',query({'portal':['neis'],'field':['SD_SCHUL_CODE']})['total']>=1)
    check('sql_metacharacters_are_literal',query({'q':["' OR 1=1 --"]})['total']==0)
    check('unknown_record_handled','error' in query({'id':['missing']}))
    count=db.execute('SELECT count(*) FROM documented_fields').fetchone()[0]
    check('documented_count_reconciles',count==summary['documented_column_occurrences'])
    # Every source used by an imported record or definition must be retrievable
    # from a saved receipt and unchanged original bytes.
    evidence={x[0] for x in db.execute('SELECT DISTINCT evidence_id FROM records UNION SELECT DISTINCT evidence_id FROM documented_fields')}
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_documents'").fetchone():
        evidence.update(x[0] for x in db.execute("SELECT DISTINCT evidence_id FROM schema_documents WHERE status LIKE '%observed%'") if x[0])
        evidence.update(x[0] for x in db.execute("SELECT json_extract(metadata_json,'$.header_evidence_id') FROM schema_documents WHERE json_array_length(metadata_json,'$.header_candidates')>0"))
        evidence.update(x[0] for x in db.execute("SELECT DISTINCT json_extract(definition_json,'$.raw_definition.code_evidence_id') FROM documented_fields WHERE json_array_length(definition_json,'$.raw_definition.observed_codes')>0 AND json_extract(definition_json,'$.raw_definition.code_evidence_id') IS NOT NULL"))
        evidence.update(x[0] for x in db.execute("SELECT DISTINCT j.value FROM schema_documents s,json_each(s.metadata_json,'$.additional_evidence_ids') j"))
        evidence.update(x[0] for x in db.execute("SELECT DISTINCT json_extract(j.value,'$.evidence_id') FROM schema_documents s,json_each(s.metadata_json,'$.request_parameters') j WHERE json_extract(j.value,'$.evidence_id') IS NOT NULL"))
    dart=read(HERE/'opendart-catalog-report.json')
    evidence.update(p['evidence_id'] for p in dart['introduction_pages'])
    evidence.update(read(HERE/'address-catalog-report.json')['navigation_evidence_ids'])
    refs=HERE/'inventory/external-references.jsonl.gz'
    if refs.exists():
        with gzip.open(refs,'rt',encoding='utf-8') as f:relations=[json.loads(line) for line in f]
        evidence.update(x['evidence_id'] for x in relations)
        check('external_references_namespaced_and_not_identity_claims',all(x['id']==uid('external-ref',x['source_portal'],x['source_dataset_key'],x['target_url']) and not x['same_dataset_asserted'] and not x['joinability_asserted'] for x in relations))
    failures=[]
    for eid in sorted(evidence):
        try:
            receipt=read(HERE/'evidence'/(eid+'.json'))
            raw=gzip.decompress((HERE/receipt['raw_file']).read_bytes())
            if sha256(raw).hexdigest()!=receipt['sha256']:failures.append(eid)
        except Exception:failures.append(eid)
    check('all_imported_sources_have_matching_sha256',not failures,{'sources_checked':len(evidence),'failures':failures})
    check('no_semantic_or_statistical_approval_fabricated',summary['semantic_relationships_approved']==0 and summary['statistical_associations_verified']==0)
    result={'checked_at':now(),'passed':all(x['passed'] for x in checks),'checks':checks,
        'scope':'수집·참조·페이지 처리·원문 해시·검색 검증; 데이터 품질 점수나 상관관계 검증 아님'}
    dump(HERE/'validation-report.json',result)
    print(json.dumps({'passed':result['passed'],'checks':len(checks),'failed':[x for x in checks if not x['passed']]},ensure_ascii=False))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
