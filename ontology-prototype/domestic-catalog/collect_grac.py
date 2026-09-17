"""Read the two officially linked GRAC API guides; never call their data services."""
from common import *
from catalog_storage import row,store_catalog
from urllib.parse import urljoin
from collections import Counter
import re
import xml.etree.ElementTree as ET

BASE='https://www.grac.or.kr'
GUIDES=[('game','게임 API','grac-public-api-guide-20260914','/OpenBook/OpenAPI.aspx',
         'grac-game-guide','/OpenBook/OpenAPIGuide.aspx'),
        ('recruit','채용 API','grac-recruit-guide','/OpenBook/RecruitAPI.aspx',
         'grac-recruit-usage','/OpenBook/RecruitAPIGuide.aspx')]

def grid(table,tn):
    """Expand only explicit HTML spans and retain every physical source cell."""
    held={};rows=[];trs=table.select('tbody tr')
    for rn,tr in enumerate(trs):
        cells={};physical=[];col=0
        for (rr,cc),v in held.items():
            if rr==rn:cells[cc]=v
        for cn,c in enumerate(tr.find_all(['th','td'],recursive=False)):
            while col in cells:col+=1
            width=int(c.get('colspan',1));height=int(c.get('rowspan',1))
            if width<1 or height<1 or rn+height>len(trs):raise ValueError('invalid_explicit_table_span')
            value={'text':c.get_text(' ',strip=True),'locator':f'table[{tn}].tbody.tr[{rn}].cell[{cn}]',
                'source_row':rn,'source_cell':cn,'rowspan':height,'colspan':width}
            physical.append(value)
            for rr in range(rn,rn+height):
                for cc in range(col,col+width):
                    if (rr,cc) in held or (rr==rn and cc in cells):raise ValueError('overlapping_table_spans')
                    if rr==rn:cells[cc]=value
                    else:held[(rr,cc)]=value
            col+=width
        if set(cells)!=set(range(len(cells))):raise ValueError('table_grid_gap')
        rows.append({'locator':f'table[{tn}].tbody.tr[{rn}]','source_cells':physical,
            'expanded_cells':[cells[n]['text'] for n in range(len(cells))],
            'expanded_cell_sources':[cells[n] for n in range(len(cells))]})
    return rows

def parse(body):
    soup=BeautifulSoup(body,'html.parser')
    d={'fields':[],'request_parameters':[],'structural_elements':[],
       'definition_tables':[],'error_code_tables':[],'documentation_examples':[],'issues':[]}
    for tn,t in enumerate(soup.select('table')):
        prev=t.find_previous(['h2','h3','h4']);heading=prev.get_text(' ',strip=True) if prev else ''
        head=[c.get_text(' ',strip=True) for c in t.select('thead th')]
        caption=t.caption.get_text(' ',strip=True) if t.caption else ''
        rows=grid(t,tn);table={'table_index':tn,'heading':heading,'headers':head,'caption':caption,'rows':rows}
        if heading=='오류 메세지':d['error_code_tables'].append(table);continue
        if heading not in ('요청 변수','출력 변수'):raise ValueError('unknown_guide_table_role')
        role='request' if heading=='요청 변수' else 'response'
        if head[1:]!=['형식','필수','설명']:raise ValueError('guide_header_changed')
        if head[0]!=('요청변수' if role=='request' else '출력변수'):
            d['issues'].append({'issue':'heading_header_role_mismatch','table_index':tn,'heading':heading,'headers':head})
        if role=='response' and '요청변수' in caption:
            d['issues'].append({'issue':'response_table_caption_says_request','table_index':tn,'caption':caption})
        table['role_from_heading']=role;d['definition_tables'].append(table)
        for r in rows:
            c=r['expanded_cells']
            if len(c)!=4 or not c[0]:raise ValueError('guide_row_shape_changed')
            v={**r,'name_en':c[0],'name':c[0],'datatype':c[1] if c[1]!='-' else None,
               'source_type_as_reported':c[1],'requirement_as_reported':c[2],'description':c[3],'unit':None}
            if role=='request':d['request_parameters'].append(v)
            elif 'root 요소' in c[3] or c[3]=='채용 목록':
                v['role']='documented_structure_or_list_element';d['structural_elements'].append(v)
            else:v['role']='api_response_column';d['fields'].append(v)
    names={v['name_en'] for v in d['fields']+d['structural_elements']}
    for pn,p in enumerate(soup.select('pre')):
        text=p.get_text().strip();ex={'locator':f'pre[{pn}]','text_as_reported':text,'source_kind':'embedded_documentation_example',
            'sample_data_requested':False,'example_only_names_promoted_to_columns':False}
        try:
            root=ET.fromstring(text);ex.update(xml_parse_status='valid_documentation_xml',root_name=root.tag,
                element_names=sorted({e.tag for e in root.iter()}))
        except ET.ParseError as exc:
            ex.update(xml_parse_status='malformed_documentation_xml',parse_error=str(exc),
                lexical_tag_names=sorted(set(re.findall(r'</?([A-Za-z_][\w.-]*)\b',text))))
            d['issues'].append({'issue':'malformed_documentation_xml','locator':ex['locator'],'error':str(exc)})
        if pn==0:
            observed=set(ex.get('element_names',ex.get('lexical_tag_names',[])))
            ex['names_not_in_output_table']=sorted(observed-names)
            ex['output_table_names_not_in_example']=sorted(names-observed)
            if observed!=names:d['issues'].append({'issue':'output_table_example_name_difference','locator':ex['locator'],
                'names_not_in_table':ex['names_not_in_output_table'],'table_names_not_in_example':ex['output_table_names_not_in_example'],
                'comparison_method':'parsed_xml_tags' if 'element_names' in ex else 'lexical_tags_only_xml_invalid'})
        d['documentation_examples'].append(ex)
    output_names=[v['name_en'] for v in d['fields']+d['structural_elements']]
    repeated={k:v for k,v in Counter(output_names).items() if v>1}
    if repeated:d['issues'].append({'issue':'repeated_output_name_with_distinct_source_rows','names':repeated})
    return d

def main():
    records=[];definitions=[]
    for key,title,menu_eid,menu_path,eid,path in GUIDES:
        b,r=fetch(menu_eid,BASE+menu_path)
        if b is None:raise ValueError('guide_menu_unresolved')
        soup=BeautifulSoup(b,'html.parser')
        links=[{'locator':f'a[href][{n}]','label':a.get_text(' ',strip=True)} for n,a in enumerate(soup.select('a[href]'))
               if urljoin(BASE+menu_path,a['href'])==BASE+path]
        if not links:raise ValueError('explicit_usage_guide_link_missing')
        item=row('grac',key,title,BASE+path,menu_eid,kind='public_api_guide_registration',
            locator=links[0]['locator'],guide_link_occurrences=links,
            local_id_basis='Project key for an explicitly linked guide; not an agency dataset identifier.',
            source_guide_title=title,catalog_scope='Two public OPEN API menu guides only')
        records.append(item)
    store_catalog('grac',records);dump(HERE/'inventory/grac-catalog.json',records)
    for item in records:
        key=item['dataset_key'];eid=next(x[4] for x in GUIDES if x[0]==key)
        b,r=fetch(eid,item['url'])
        d={'portal_id':'grac','dataset_key':key,'evidence_id':eid,'source_url':item['url'],
           'additional_evidence_ids':[item['evidence_id']],'fields':[],'status':'fetch_unresolved',
           'collected_at':now(),'parser_version':1,'human_approved':False,'raw_values_checked':False,
           'all_columns_complete':False,'observation_api_called':False}
        if b:
            try:
                d.update(parse(b));d['status']='response_definition_observed_with_source_issues' if d['issues'] else 'response_definition_observed'
            except (ValueError,TypeError,KeyError) as exc:d.update(status='parse_unresolved',error=str(exc),fields=[])
        dump(HERE/'definitions'/('grac-schema-'+key+'.json'),d);definitions.append(d)
    report={'generated_at':now(),'scope':'grac-public-api-guides','target_count':2,'processed':len(definitions),
        'status_counts':dict(Counter(d['status'] for d in definitions)),'queue_exhausted':True,
        'catalog_records':len(records),'documented_field_occurrences':sum(len(d['fields']) for d in definitions),
        'request_parameter_occurrences':sum(len(d.get('request_parameters',[])) for d in definitions),
        'structural_element_occurrences':sum(len(d.get('structural_elements',[])) for d in definitions),
        'all_portal_catalogs_complete':False,'all_columns_complete':False,'observation_api_called':False}
    dump(HERE/'grac-collection-report.json',report)
    dump(HERE/'grac-source-qa.json',{'generated_at':now(),'portal_id':'grac',
        'qa_scope':'Public definition consistency; not actual API response validity or data quality scores',
        'services':[{'dataset_key':d['dataset_key'],'evidence_id':d['evidence_id'],'issues':d.get('issues',[])} for d in definitions],
        'structural_elements_excluded_from_scalar_field_counts':True,'repeated_names_not_merged':True,
        'source_typos_not_silently_corrected':True,'quality_scores_assigned':False,'raw_values_checked':False,
        'remaining_scope':['Public data disclosure menu and non-API catalogs','Runtime schema vs documentation validation','File column definitions']})
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
