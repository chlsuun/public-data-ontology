"""Collect file/layer attribute dictionaries from the agency's linked usage tabs."""
from common import *
from queue_runner import run_queue
from urllib.parse import urljoin,urlsplit,parse_qs
from collections import Counter
import re

def collect(t):
    key=t['dataset_key'];eid='forest-usage-'+key;p=HERE/'definitions'/('forest-schema-'+key+'-usage.json')
    if p.exists():return read(p)
    d={'portal_id':'forest','dataset_key':key,'evidence_id':eid,'source_url':t['url'],
        'additional_evidence_ids':[t['evidence_id']],'navigation_source':t,'fields':[],
        'status':'fetch_unresolved','human_approved':False,'raw_values_checked':False,'all_columns_complete':False,
        'collected_at':now(),'parser_version':1,'observation_api_called':False,'file_downloaded':False,
        'scope':'File and layer schema documented on this usage page; not all versions or live file validation'}
    b,r=fetch(eid,t['url']);d['source_url']=r['requested_url']
    if b:
        try:
            s=BeautifulSoup(b,'html.parser');content=s.select_one('#txt')
            if content is None or b'</html>' not in b.lower():raise ValueError('usage_content_incomplete')
            d.update(schema_groups=[],issues=[],outgoing_links=[],source_context_blocks=[],declared_epsg_code=None,
                documentation_text=content.get_text(' ',strip=True),geometry_or_crs_normalization_performed=False,
                units_assigned_to_individual_columns=False)
            for n,node in enumerate(content.select('ul,p,h3,h4,h5')):
                text=node.get_text(' ',strip=True)
                if text and any(term in text for term in ('파일 형식','파일 타입','좌표계','단위정보','최종수정일')):
                    d['source_context_blocks'].append({'text_as_reported':text,'locator':f'#txt ul,p,h3,h4,h5[{n}]'})
            for tn,table in enumerate(s.select('table')):
                headers=[c.get_text(' ',strip=True) for c in table.select('thead th')]
                caption=table.caption.get_text(' ',strip=True) if table.caption else ''
                before=table.find_previous_sibling()
                group={'schema_group_id':eid+':table:'+str(tn),'table_index':tn,'headers':headers,'caption':caption,
                    'immediate_preceding_element':{'tag':before.name,'text_as_reported':before.get_text(' ',strip=True),
                        'locator':f'table[{tn}] immediate previous element sibling'} if before else None,'rows':[]}
                d['schema_groups'].append(group)
                if headers!=['컬럼명','컬럼설명','타입','길이']:
                    d['issues'].append({'issue':'unrecognized_usage_table_header','table_index':tn,'headers':headers});continue
                for rn,tr in enumerate(table.select('tbody tr')):
                    cells=tr.find_all(['th','td'],recursive=False);values=[c.get_text(' ',strip=True) for c in cells]
                    row={'locator':f'table[{tn}].tbody.tr[{rn}]','table_index':tn,'row_index':rn,'source_cells':values}
                    group['rows'].append(row)
                    if len(values)!=4 or not values[0] or any(c.has_attr('rowspan') or c.has_attr('colspan') for c in cells):
                        d['issues'].append({'issue':'unrecognized_attribute_row',**row});continue
                    d['fields'].append({**row,'name_en':values[0],'name':values[0],'description':values[1],
                        'datatype':values[2] or None,'source_type_as_reported':values[2],
                        'length_as_reported':values[3],'length_numeric_interpretation':None,'unit':None,
                        'role':'documented_file_layer_attribute','schema_group_id':group['schema_group_id'],
                        'source_file_or_layer_context':group['caption'],'latest_file_version_applicability_verified':False})
                    if values[3] in ('?','-',''):
                        d['issues'].append({'issue':'attribute_length_unspecified_in_source','name':values[0],
                            'value_as_reported':values[3],'locator':row['locator']+'.cell[3]'})
            for n,a in enumerate(content.select('a[href]')):
                url=urljoin(d['source_url'],re.sub(r';jsessionid=[^?&#/]+','',a['href']))
                if urlsplit(url).scheme in ('http','https') and urlsplit(url).hostname not in ('www.forest.go.kr','api.forest.go.kr'):
                    d['outgoing_links'].append({'url':url,'label':a.get_text(' ',strip=True),'locator':f'#txt a[href][{n}]',
                        'same_dataset_asserted':False})
            d['status']='file_attribute_definition_observed_with_source_issues' if d['fields'] and d['issues'] else ('file_attribute_definition_observed' if d['fields'] else 'public_usage_metadata_observed_schema_pending')
        except (ValueError,KeyError,TypeError) as exc:d.update(status='parse_unresolved',error=str(exc),fields=[])
    dump(p,d);return d

def summarize():
    targets=read(HERE/'inventory/forest-usage-targets.json')['targets']
    docs=[read(HERE/'definitions'/('forest-schema-'+t['dataset_key']+'-usage.json')) for t in targets]
    report={'generated_at':now(),'usage_documents':len(docs),'with_attribute_definitions':sum(bool(d['fields']) for d in docs),
        'attribute_fields':sum(len(d['fields']) for d in docs),'schema_groups':sum(len(d.get('schema_groups',[])) for d in docs),
        'status_counts':dict(Counter(d['status'] for d in docs)),
        'source_issues':[{'dataset_key':d['dataset_key'],'evidence_id':d['evidence_id'],'issues':d['issues']} for d in docs if d.get('issues')],
        'scope':'Only the 19 explicitly linked usage documents, not all current map files or layer versions',
        'all_columns_complete':False,'file_downloads_performed':False,'coordinate_codes_inferred':False}
    dump(HERE/'forest-attribute-summary.json',report)
    qa=read(HERE/'forest-source-qa.json');qa['additional_file_attribute_summary']=report
    qa['documented_response_fields']=156;qa['documented_file_attribute_fields']=report['attribute_fields']
    qa['file_layer_dictionary_scope_note']='Do not add API output fields and file-layer attributes as if all describe a single table.'
    dump(HERE/'forest-source-qa.json',qa)
    model=read(HERE/'model.json');model['instance_files']['forest_file_attribute_summary']='forest-attribute-summary.json'
    dump(HERE/'model.json',model)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    run_queue('forest-attributes',read(HERE/'inventory/forest-usage-targets.json')['targets'],collect,2)
    summarize()
