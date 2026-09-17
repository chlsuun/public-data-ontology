"""Extract four documented FISIS API operations without calling keyed APIs."""
from common import *
from catalog_storage import row,store_catalog
from collect_grac import grid
from collections import Counter
import re


def main():
    eid='fisis-api-spec-20260914';url='https://fisis.fss.or.kr/page/api-spec.jsp'
    body,r=fetch(eid,url)
    if body is None:raise ValueError('Official API specification unavailable')
    soup=BeautifulSoup(body,'html.parser');all_tables=soup.select('table');records=[];reports=[]
    panels=soup.select('[role=tabpanel]')
    if len(panels)!=4:raise ValueError('Unexpected number of documented API operations')
    for panel in panels:
        d={'portal_id':'fisis','dataset_kind':'public_api_operation_definition','source_url':url,'evidence_id':eid,
            'collected_at':now(),'parser_version':1,'fields':[],'request_parameters':[],'configuration_rows':[],
            'definition_tables':[],'response_messages':[],'code_tables':[],'issues':[],
            'status':'response_definition_observed','source_panel_id':panel['id'],
            'sample_response_promoted_to_fields':False,'keyed_api_called':False,'human_approved':False,'all_columns_complete':False}
        title=panel.select_one('h4').get_text(' ',strip=True);service=None
        for t in panel.select('table'):
            tn=next(i for i,x in enumerate(all_tables) if x is t);caption=t.caption.get_text(' ',strip=True) if t.caption else ''
            headers=[x.get_text(' ',strip=True) for x in t.select('thead tr')]
            try:rows=grid(t,tn)
            except ValueError as exc:
                if not caption.startswith('금융권역 분류표:'):raise
                rows=[{'locator':f'table[{tn}].tbody.tr[{rn}]','source_cells':[
                    {'text':c.get_text(' ',strip=True),'rowspan':c.get('rowspan','1'),'colspan':c.get('colspan','1'),
                     'locator':f'table[{tn}].tbody.tr[{rn}].cell[{cn}]'}
                    for cn,c in enumerate(tr.find_all(['th','td'],recursive=False))],
                    'expanded_cells':None,'span_expansion_status':'unresolved'} for rn,tr in enumerate(t.select('tbody tr'))]
                d['issues'].append({'issue':'invalid_source_classification_span','table_index':tn,'reason':str(exc),'automatic_correction':False})
                d['status']='response_definition_observed_code_table_partial'
            table={'table_index':tn,'caption':caption,'headers':headers,'rows':rows};d['definition_tables'].append(table)
            if caption.startswith('요청변수 표:'):
                for rr in rows:
                    cs=rr['expanded_cells'];assert len(cs)==5
                    f={**rr,'name':cs[0],'name_en':cs[1] if cs[1]!='-' else None,'datatype':cs[2],'required_as_reported':cs[3],'description':cs[4]}
                    if cs[0]=='서비스명':service=cs[4]
                    (d['request_parameters'] if cs[1]!='-' else d['configuration_rows']).append(f)
            elif caption.startswith('결과변수 표:'):
                for rr in rows:
                    cs=rr['expanded_cells'];assert len(cs)==3 and bool(cs[0])!=bool(cs[1])
                    name=cs[0] or cs[1]
                    d['fields'].append({**rr,'name':name,'name_en':name,'description':cs[2],'datatype':None,'unit':None,
                        'role':'api_response_control' if name in ('err_cd','err_msg','total_count') else 'api_response_column',
                        'source_header_axis':'result' if cs[0] else 'list','nested_path_status':'not_inferred_from_example',
                        'dynamic_value_label':name in ('a','b','c','d')})
            elif caption.startswith('응답메시지 표:'):d['response_messages'].extend(rows)
            elif caption.startswith('금융권역 분류표:'):d['code_tables'].append(table)
            else:raise ValueError('Unrecognized documentation table: '+caption)
        if not service or not re.fullmatch('[A-Za-z]+Search',service):raise ValueError('Invalid explicit service identifier')
        d['dataset_key']='api-'+service
        # URL template appears as literal text, not a request to be executed.
        pattern=r'http://fisis\.fss\.or\.kr/openapi/'+service+r'\.\{[^}]+\}'
        match=re.search(pattern,panel.get_text(' ',strip=True))
        if not match:raise ValueError('Documented endpoint template absent')
        d['endpoint_template_as_reported']=match[0]
        record=row('fisis',d['dataset_key'],title,url+'#'+panel['id'],eid,kind=d['dataset_kind'],provider_name='금융감독원',
            provider_name_role='official API documentation publisher',locator='div#'+panel['id'],
            service_identifier=service,endpoint_template_as_reported=match[0],authentication='issued key required by official specification',
            identity_note='Operation definition, not a statistical report or financial company')
        records.append(record);dump(HERE/'definitions'/('fisis-api-schema-'+service+'.json'),d)
        reports.append({'service_identifier':service,'dataset_key':d['dataset_key'],'status':d['status'],'fields':len(d['fields']),
            'request_parameters':len(d['request_parameters']),'configuration_rows':len(d['configuration_rows']),
            'response_messages':len(d['response_messages']),'code_tables':len(d['code_tables'])})
    store_catalog('fisis',records);dump(HERE/'inventory/fisis-api-catalog.json',records)
    report={'generated_at':now(),'scope':'four explicitly documented FISIS API operation specifications',
        'target_count':4,'processed':4,'remaining':0,'status_counts':dict(Counter(x['status'] for x in reports)),
        'operations':reports,'documented_field_occurrences':sum(r['fields'] for r in reports),
        'request_parameter_occurrences':sum(r['request_parameters'] for r in reports),
        'queue_exhausted':True,'all_columns_complete':False,'keyed_api_called':False,
        'dynamic_columns_note':'a/b/c/d are documented placeholders; actual per-report column meanings require report-specific metadata.',
        'code_scope_note':'Open API sector codes and public UI sector codes are separate source namespaces; no identity mapping inferred.'}
    dump(HERE/'fisis-api-collection-report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
