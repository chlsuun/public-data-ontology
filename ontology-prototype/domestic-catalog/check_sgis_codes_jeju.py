"""Source QA for SGIS code-reference semantics and complete Jeju public catalog."""
from common import *
from collect_sgis_codes import parse_table
from collections import Counter
from urllib.parse import urlsplit,parse_qs

def main():
    checks=[];sources={}
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    def source(eid):
        if eid not in sources:
            r=read(HERE/'evidence'/(eid+'.json'));raw=gzip.decompress((HERE/r['raw_file']).read_bytes())
            if sha256(raw).hexdigest()!=r['sha256']:raise ValueError('source_hash_mismatch:'+eid)
            sources[eid]=(raw,r)
        return sources[eid]
    lists=read(HERE/'inventory/sgis-code-lists.json');by_name={c['source_name']:c for c in lists['code_tables']};errors=[];merged=0
    for c in lists['code_tables']:
        raw,_=source(c['evidence_id']);s=BeautifulSoup(raw,'html.parser');trs=s.select('table tbody tr')
        if len(trs)!=len(c['rows']):errors.append(c['id'])
        for r in c['rows']:
            for cell in r['logical_cells']:
                original=trs[cell['source_row']].find_all(['td','th'],recursive=False)[cell['source_cell']]
                if original.get_text(' ',strip=True)!=cell['text'] or not (cell['source_row']<=r['source_row']<cell['source_row']+int(original.get('rowspan',1))):errors.append(c['id'])
                merged+=cell['source_row']!=r['source_row']
            if r['values']!=[cell['text'] for cell in r['logical_cells']]:errors.append(c['id'])
    check('all_14_code_tables_and_461_rows_match_originals',not errors and len(by_name)==14 and lists['total_source_rows']==461,{'inherited_cells_checked':merged,'errors':errors})
    age=by_name['PplAgeCode'];check('code_leading_zeros_and_overlapping_age_groups_preserved',age['rows'][0]['values']==['0~4세','01'] and any(r['values']==['15세미만','22'] for r in age['rows']) and len(age['rows'])==41)
    years=by_name['ConstYearCode'];check('year_context_retained_for_reused_codes',len(years['rows'])==165 and len({r['values'][0] for r in years['rows']})>1 and len({r['values'][-1] for r in years['rows']})<len(years['rows']))
    coords=by_name['CoordCode'];check('multiple_coordinate_codes_not_silently_split_or_equated',coords['rows'][0]['values']==['BESSEL 경/위도','EPSG:4004, EPSG:4162'])
    raw,_=source('sgis-data-api-guide');s=BeautifulSoup(raw,'html.parser');anchors=s.select('a[onclick]');refs=read(HERE/'inventory/sgis-code-list-references.json')['references'];errors=[]
    for b in refs:
        n=int(b['locator'].split('[')[-1].split(']')[0]);a=anchors[n];section=a.find_parent(class_='apiItem');tr=a.find_parent('tr');table=a.find_parent('table')
        if a['onclick']!=b['source_onclick'] or section.select_one('dt.guide_title')['id']!=b['source_guide_anchor'] or tr.find_all(['th','td'],recursive=False)[0].get_text(' ',strip=True)!=b['source_parameter_label'] or table.caption.get_text(' ',strip=True)!=b['source_direction_caption'] or b['same_code_system_as_other_portal_asserted']:errors.append(b['locator'])
    check('35_parameter_code_references_grounded_without_cross_portal_equivalence',len(refs)==35 and not errors,{'errors':errors})
    raw,_=source('sgis-code-table-ThemeCode');rejected=False
    try:parse_table(raw.replace(b'rowspan="3"',b'rowspan="9999"',1),'ThemeCode','test')
    except ValueError:rejected=True
    check('out_of_bounds_merged_cell_rejected',rejected)
    check('code_rows_not_added_to_sgis_output_field_count',sum(len(read(p)['fields']) for p in (HERE/'definitions').glob('sgis-schema-*.json'))==618)
    report=read(HERE/'jeju-catalog-report.json');items=read(HERE/'inventory/jeju-catalog.json');raw,_=source('jeju-public-count-page1')
    check('jeju_126_pages_unique_ids_and_independent_count_reconcile',len(items)==len({r['dataset_key'] for r in items})==json.loads(raw)==1259 and report['pages_received']==report['pages_expected']==126 and report['snapshot_pagination_complete'] and not report['errors'] and not report['duplicate_observations'])
    errors=[];directions=Counter();files=0;api_parents=set();auth=Counter()
    for item in items:
        raw,receipt=source(item['evidence_id']);obj=json.loads(raw);n=int(item['locator'].split('[')[-1].split(']')[0]);original=obj['data'][n];query=parse_qs(urlsplit(receipt['requested_url']).query)
        if original!=item['source_catalog_record'] or str(original['id'])!=item['dataset_key'] or query['pageNumber']!=[str(item['source_page'])] or query['start']!=[str((item['source_page']-1)*10)]:errors.append(item['id'])
        if item['provider_id'] is not None or item['provider_name'] is not None or item['source_owner_as_reported']!=original['owner']:errors.append(item['id'])
        auth[original['authYn']]+=1
        d=read(HERE/'definitions'/('jeju-schema-'+item['dataset_key']+'.json'))
        for f in d['fields']:
            api_parents.add(item['id']);idx=int(f['locator'].split('[')[-1].split(']')[0]);field=original['dataApi']['dataApiElements'][idx]
            if field!=f['source_parameter_record'] or field['type']!='response' or field['apiId']!=original['dataApi']['id'] or field['name']!=f['name']:errors.append(item['id'])
            directions['response']+=1
        for f in d['request_parameters']:
            if f['source_parameter_record']['type']!='request':errors.append(item['id'])
            directions['request']+=1
        for f in d['file_versions']:
            obj=original['dataFile'] if f['source_role']=='dataset_file' else original['file'] if f['source_role']=='dataset_preview' else original['dataApi']['file']
            idx=int(f['locator'].split('[')[-1].split(']')[0])
            if f['source_file_record']!=obj['fileInfos'][idx] or f['parent_file_id']!=obj['id'] or f['file_content_or_header_fetched']:errors.append(item['id'])
            files+=1
    check('jeju_all_catalog_parameter_and_file_metadata_trace_to_source',not errors,{'response_fields':directions['response'],'request_parameters':directions['request'],'api_registrations':len(api_parents),'file_metadata_occurrences':files,'errors':errors})
    check('jeju_all_api_directions_and_file_roles_preserved',directions==Counter(response=686,request=331) and len(api_parents)==93 and files==2240)
    check('default_anonymous_catalog_includes_auth_flagged_records',auth==Counter({True:926,False:333}))
    check('no_full_national_or_column_completion_claim',not lists['all_sgis_code_lists_complete'] and not report['all_columns_complete'] and not report['all_portal_catalogs_complete'])
    result={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,'source_receipts_checked':len(sources),
        'scope':'SGIS referenced code tables and Jeju anonymous public catalog snapshot. No observation quality, institution identity or statistical relationships validated.'}
    dump(HERE/'sgis-codes-jeju-source-check.json',result);print(json.dumps({'passed':result['passed'],'checks':len(checks),'source_receipts':len(sources),'failures':[c for c in checks if not c['passed']]},ensure_ascii=False),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
