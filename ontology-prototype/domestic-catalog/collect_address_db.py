"""Collect Juso's public dataset categories and published schema components."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from static_js_data import literal_value
from urllib.parse import urljoin
import re

BASE='https://business.juso.go.kr'
CATALOG_EID='address-db-catalog-public'
MAPPING_EID='address-JspAddrInfoExperience-14b37ad8'

def catalog():
    body,receipt=fetch(CATALOG_EID,BASE+'/api/jst/selectBabsRtlDtaDtlList',json_body={})
    if not body:raise ValueError('catalog_fetch_unresolved')
    data=json.loads(body)
    if data.get('status')!=200 or not isinstance(data.get('results'),list):raise ValueError('catalog_response_invalid')
    raw,mr=fetch(MAPPING_EID,BASE+'/assets/JspAddrInfoExperience-14b37ad8.js')
    if not raw:raise ValueError('schema_mapping_source_unresolved')
    source=raw.decode('utf-8');mapping={}
    for m in re.finditer(r'RTL_DTA_DTL_SN\)===\"(\d+)\"\)return[^;]+?import\(\"(\./Schema_[^\"]+\.js)\"\)',source):
        mapping[m[1]]={'url':urljoin(BASE+'/assets/',m[2]),'evidence_id':mr['id'],
            'locator':f'JavaScript characters {m.start()}:{m.end()}','source_condition':m[0]}
    rows=data['results'];records=[];seen=set();issues=[]
    for pos,item in enumerate(rows):
        key=str(item.get('RTL_DTA_DTL_SN',''))
        if not key or key in seen:raise ValueError('catalog_identity_missing_or_duplicate')
        seen.add(key)
        if key not in mapping:issues.append({'category_id':key,'issue':'public_schema_component_not_mapped'})
        records.append(row('address','db/'+key,item.get('RTL_DTA_DTL_NM'),BASE+'/jst/jstAddressDownload?menu='+key,
            receipt['id'],kind='download_dataset_category',locator=f'results[{pos}]',
            source_catalog_record=item,release_flag_as_reported=item.get('RLS_YN'),source_data_type_code=item.get('DTA_TYPE_CD'),
            schema_component=mapping.get(key),identifier_basis='db/ prefix separates source RTL_DTA_DTL_SN from API service uniqKey',
            catalog_scope='publicly listed downloadable dataset categories; individual dated files not enumerated',
            download_access_review='not_inferred_from_metadata_visibility'))
    store_catalog('address',records);dump(HERE/'inventory/address-db-catalog.json',records)
    report={'generated_at':now(),'source_evidence_id':receipt['id'],'mapping_evidence_id':mr['id'],
        'catalog_rows':len(rows),'unique_category_ids':len(seen),'mapped_schema_components':len([k for k in seen if k in mapping]),
        'source_release_flag_counts':{v:sum(r.get('RLS_YN')==v for r in rows) for v in sorted({r.get('RLS_YN') for r in rows})},
        'snapshot_category_list_reconciles':bool(rows) and len(rows)==len(seen) and not issues,
        'reconciliation_basis':'public UI unpaginated metadata response; source category IDs matched to component dispatch conditions',
        'issues':issues,'all_portal_catalogs_complete':False,'all_columns_complete':False,
        'remaining':'See address-db-collection-report.json for schema progress; individually dated file catalogs and applicable public documentation remain; protected file access not attempted'}
    dump(HERE/'address-db-catalog-report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
    return records

def parse_schema(source,eid):
    fields=[];arrays=[];choices=[];supporting=[];issues=[];last=0
    if '스키마' not in source or 'field:"column"' not in source:raise ValueError('published_schema_ui_not_observed')
    for match in re.finditer(r'\[\s*\{\s*(?:number|no|rowSpan|column|label)\s*:',source):
        start=match.start()
        if start<last:continue
        try:items,end=literal_value(source,start);last=end
        except ValueError as exc:issues.append({'locator':f'JavaScript characters {start}', 'issue':str(exc)});continue
        if not isinstance(items,list) or not items:continue
        if all(isinstance(v,dict) and 'label' in v and 'value' in v for v in items):
            choices.append({'locator':f'JavaScript characters {start}:{end}','items':items});continue
        if not any(isinstance(v,dict) and 'column' in v for v in items):
            supporting.append({'locator':f'JavaScript characters {start}:{end}','items':items,'role':'supporting_metadata_not_columns'});continue
        grouped=all(isinstance(v,dict) and {'rowSpan','type','comment','column'}<=set(v) for v in items) and '"group-rows-by":"rowSpan"' in source
        if not grouped and not all(isinstance(v,dict) and {'column','size','format','note'}<=set(v) and ('number' in v or 'no' in v) for v in items):
            issues.append({'locator':f'JavaScript characters {start}:{end}','issue':'schema_array_keys_unexpected'});continue
        before=source[max(0,start-100):start]
        binding=re.search(r'([A-Za-z_$][A-Za-z0-9_$]*)=[A-Za-z_$][A-Za-z0-9_$]*\($',before)
        variable=binding[1] if binding else None
        numbers=[str(v.get('number',v.get('no'))) for v in items]
        if not grouped and numbers!=[str(n) for n in range(1,len(items)+1)]:issues.append({'locator':f'JavaScript characters {start}:{end}','issue':'schema_ordinals_not_contiguous','ordinals':numbers})
        group_labels={v['rowSpan']:v['type'] for v in items if grouped and v.get('type')}
        arrays.append({'source_variable':variable,'literal_start':start,'literal_end':end,'field_count':len(items),
            'schema_variant_locator':f'JavaScript characters {start}:{end}','radio_labels_not_automatically_assigned':True,
            'source_group_field':'rowSpan' if grouped else None,'source_group_labels':group_labels})
        for n,item in enumerate(items):
            fields.append({'name':item.get('comment') or item['column'],'name_en':item['column'] if item['column'].isascii() else None,'datatype':item.get('format'),'unit':None,
                'description':BeautifulSoup(item.get('note') or '','html.parser').get_text(' ',strip=True) or None,
                'size_as_reported':item.get('size'),'primary_key_annotation_as_reported':item.get('pk'),
                'role':'documented_file_column','evidence_id':eid,'locator':f'JavaScript characters {start}:{end} / array[{n}]',
                'schema_variant_locator':f'JavaScript characters {start}:{end}'+('/group/'+item['rowSpan'] if grouped else ''),'source_variable':variable,
                'source_row_group':item.get('rowSpan') if grouped else None,'source_group_label':group_labels.get(item.get('rowSpan')),
                'literal_start':start,'literal_end':end,'array_ordinal':n,'source_definition':item})
    if not fields:issues.append({'issue':'no_literal_schema_columns_observed'})
    return {'fields':fields,'schema_arrays':arrays,'source_layout_choices':choices,'supporting_metadata_arrays':supporting,'issues':issues,
        'javascript_executed':False,'raw_observation_file_downloaded':False,
        'field_count_note':'Separate schema arrays and repeated names are retained; not a single flat physical table.'}

def collect_one(item):
    key=item['dataset_key'];eid=uid('address-db-schema',key);path=HERE/'definitions'/(eid+'.json')
    previous=read(path) if path.exists() else None
    if previous and previous.get('parser_version',1)>=3:return previous
    component=item.get('schema_component')
    result={'portal_id':'address','dataset_key':key,'dataset_kind':'download_dataset_category','evidence_id':eid,
        'source_url':component['url'] if component else item['url'],'documentation_page_url':item['url'],
        'additional_evidence_ids':[CATALOG_EID,MAPPING_EID],'fields':[],'request_parameters':[],
        'status':'schema_source_unresolved','human_approved':False,'raw_values_checked':False,'collected_at':now(),
        'release_flag_as_reported':item['release_flag_as_reported'],'parser_version':3}
    if previous:result['previous_parser_status']=previous['status']
    if component:
        body,receipt=fetch(eid,component['url'])
        if body:
            try:
                result.update(parse_schema(body.decode('utf-8'),eid))
                result['status']='column_definition_observed' if result['fields'] and not result['issues'] else 'schema_definition_observed_partial'
            except (ValueError,KeyError,TypeError) as exc:result.update(status='schema_parse_unresolved',error=str(exc))
    dump(path,result);return result

def main():run_queue('address-db',catalog(),collect_one,2)

if __name__=='__main__':main()
