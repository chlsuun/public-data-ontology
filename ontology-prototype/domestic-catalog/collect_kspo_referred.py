"""KSPO's explicitly linked external data map; preserve its secondary-source status."""
from common import *
from catalog_storage import row,store_catalog
from collect_grac import grid
from urllib.parse import urlsplit
from collections import Counter
import re,sqlite3

PORTAL='kspo';EID='kspo-referred-explorer-data';URL='https://pinkshark1.github.io/kspo_data_explorer/'

def main():
    guide_eid='kspo-disclosure-catalog';r=read(HERE/'evidence'/(guide_eid+'.json'))
    s=BeautifulSoup(gzip.decompress((HERE/r['raw_file']).read_bytes()),'html.parser')
    referrals=[{'locator':f'a[href][{n}]','url':a['href'],'label':a.get_text(' ',strip=True)} for n,a in enumerate(s.select('a[href]')) if a['href'].strip()==URL]
    if not referrals:raise ValueError('Explicit KSPO referral missing')
    groups=[]
    for tn,t in enumerate(s.select('table')):
        h=t.find_previous('h3').get_text(' ',strip=True)
        groups.append({'heading':h,'table_index':tn,'rows':grid(t,tn)})
    dump(HERE/'inventory/kspo-disclosure-groups.json',{'evidence_id':guide_eid,'groups':groups,'referrals':referrals,
        'rows_are_broad_disclosure_groups_not_individual_dataset_registrations':True})
    b,r=fetch(EID,URL+'data/explorer-data.json');payload=json.loads(b)
    data=payload['payloads']
    if len(data)!=6 or not isinstance(data[0],list):raise ValueError('Referred map payload structure changed')
    source_records=data[0];keys={str(x['no']) for x in source_records}
    if len(keys)!=len(source_records):raise ValueError('Referred catalog repeated local number')
    records=[];docs=[];orphan_keys={str(n):sorted(set(data[n])-keys) for n in range(1,6)}
    for pos,x in enumerate(source_records):
        no=str(x['no']);key='explorer-'+no
        record=row(PORTAL,key,x['name'],URL,EID,kind='officially_referred_external_catalog_entry',locator=f'payloads[0][{pos}]',
            source_record=x,source_generated_date_as_reported=payload.get('generatedAt'),
            catalog_identity_basis='External map local no; not a native public-data-portal ID',
            official_referral_evidence_id=guide_eid,external_host_ownership_verified=False,
            source_channel_as_reported=x['ch'],source_access_status_as_reported=x['status'],
            source_basis_code_as_reported=x['basis'],source_basis_code_not_a_quality_score=True)
        records.append(record)
        d={'portal_id':PORTAL,'dataset_key':key,'source_url':URL+'data/explorer-data.json','evidence_id':EID,
            'fields':[],'status':'referred_metadata_observed_primary_schema_pending','collected_at':now(),
            'human_approved':False,'raw_values_checked':False,'all_columns_complete':False,'observation_api_called':False,
            'source_kind':'officially_referred_external_data_map','external_host_ownership_verified':False,
            'source_catalog_locator':record['locator'],'official_referral_evidence_id':guide_eid,
            'reported_schema_candidates':[],'header_candidates':[],'header_candidate_kind':'referred_public_preview_header',
            'preview_headers':[],'outgoing_links':[],'source_qa_reference':'kspo-source-qa.json',
            'raw_preview_rows_not_extracted':True,'source_planned_relationships_not_imported':True}
        # Only records visibly registered in payload 0 are imported. Detached hidden-scope entries stay out.
        for pi in (1,3):
            source=data[pi].get(no)
            if source is None:continue
            allowed=('datasetName','sourceUrl','portalType','columns','operations','columnDefinitionFiles')
            d['reported_schema_candidates'].append({'locator':f'payloads[{pi}]["{no}"]',
                'source_copy':{k:source[k] for k in allowed if k in source},'primary_document_reconciled':False})
            link=source.get('sourceUrl')
            if link:
                parsed=urlsplit(link)
                if parsed.scheme in ('http','https') and parsed.hostname:d['outgoing_links'].append({'url':link,
                    'locator':f'payloads[{pi}]["{no}"].sourceUrl','evidence_id':EID,'same_dataset_asserted':False,
                    'source_referral_claim_only':True,'target_not_requested_by_this_collector':True})
        for pi in (2,4,5):
            source=data[pi].get(no)
            if source is None:continue
            entries=source if pi==5 else [source]
            for oi,entry in enumerate(entries):
                columns=entry.get('columns',[]);values=[c['name'] if isinstance(c,dict) else c for c in columns]
                if not all(isinstance(c,str) for c in values):raise ValueError('Referred preview header structure changed')
                locator=f'payloads[{pi}]["{no}"]'+(f'[{oi}]' if pi==5 else '')+'.columns'
                d['header_candidates'].extend(values)
                d['preview_headers'].append({'evidence_id':EID,'locator':locator,'values':values,
                    'source_column_labels_as_reported':columns,'source_file_names_as_reported':entry.get('sourceFiles',entry.get('sourceFile')),
                    'operation_name_as_reported':entry.get('operationName'),'operation_path_as_reported':entry.get('path'),
                    'source_preview_rows_not_extracted':True,'original_files_and_services_not_requested':True,
                    'primary_schema_or_actual_values_verified':False})
        docs.append(d)
    store_catalog(PORTAL,records);dump(HERE/'inventory/kspo-catalog.json',records)
    for d in docs:dump(HERE/'definitions'/('kspo-schema-'+d['dataset_key']+'.json'),d)
    # Resolve only source-asserted URL identifiers against already stored registrations, without copying fields.
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3');resolved=[]
    for d in docs:
        for link in d['outgoing_links']:
            p=urlsplit(link['url']);m=re.match(r'/data/(\d+)/(openapi|fileData)\.do',p.path)
            if p.hostname not in ('www.data.go.kr','data.go.kr') or not m:continue
            kind='API' if m[2]=='openapi' else 'FILE'
            rows=db.execute('SELECT id,kind,title FROM records WHERE portal_id=? AND dataset_key=?',('data-go',m[1])).fetchall()
            resolved.append({'source_dataset_key':d['dataset_key'],'source_url':link['url'],'evidence_id':EID,'locator':link['locator'],
                'target_portal_id':'data-go','target_dataset_key':m[1],'source_target_kind_hint':kind,
                'stored_registration_matches':[{'id':r[0],'kind':r[1],'title':r[2]} for r in rows],
                'existing_field_count':sum(db.execute('SELECT count(*) FROM documented_fields WHERE record_id=?',(r[0],)).fetchone()[0] for r in rows),
                'native_id_match_is_not_human_approved_semantic_identity':True,'target_columns_copied':False})
    db.close();dump(HERE/'inventory/kspo-data-go-reference-resolution.json',{'generated_at':now(),'references':resolved})
    report={'generated_at':now(),'scope':'kspo-officially-referred-external-map','target_count':len(records),'processed':len(docs),
        'queue_exhausted':True,'status_counts':dict(Counter(d['status'] for d in docs)),'documented_field_occurrences':0,
        'header_candidate_occurrences':sum(len(d['header_candidates']) for d in docs),'all_columns_complete':False,
        'external_host_ownership_verified':False,'official_institution_census_complete':False}
    dump(HERE/'kspo-collection-report.json',report)
    qa={'generated_at':now(),'portal_id':PORTAL,'scope':'Official referral plus externally hosted public catalog/preview metadata; primary schemas pending',
        'catalog_records':len(records),'channels_as_reported':dict(Counter(x['ch'] for x in source_records)),
        'access_status_as_reported':dict(Counter(x['status'] for x in source_records)),
        'source_generated_date_as_reported':payload.get('generatedAt'),'source_label_as_reported':payload.get('source'),
        'official_referral_evidence_id':guide_eid,'catalog_evidence_id':EID,
        'disclosure_table_group_rows':[len(g['rows']) for g in groups],
        'detached_payload_keys_not_imported':orphan_keys,'detached_metadata_not_promoted_to_catalog_entries':True,
        'reported_schema_candidate_groups':sum(len(d['reported_schema_candidates']) for d in docs),
        'preview_header_candidate_occurrences':report['header_candidate_occurrences'],
        'source_overall_schema_totals_not_assumed_to_match_masked_catalog':True,
        'basis_letters_not_converted_to_quality_scores':True,'source_relationship_scenarios_not_imported':True,
        'external_host_ownership_verified':False,'data_go_url_references':len(resolved),
        'quality_scores_assigned':False,'raw_values_checked':False,'all_columns_complete':False,
        'remaining_scope':['Reconcile source-copied schema columns with primary publishers','Collect full official institution catalogs beyond this referred snapshot',
                           'Clarify source masking and missing primary URLs without importing detached entries or observation rows']}
    dump(HERE/'kspo-source-qa.json',qa);print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
