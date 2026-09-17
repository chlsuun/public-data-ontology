"""KDI/KOCCA public HTML reference definitions, no service calls or keys."""
from common import *
from catalog_storage import row,store_catalog
from collect_grac import grid
from urllib.parse import urlsplit,parse_qs
from collections import Counter
import re
from copy import deepcopy

def cells(tr):return [x.get_text(' ',strip=True) for x in tr.find_all(['th','td'],recursive=False)]
def base(portal,key,url,eid):
    return {'portal_id':portal,'dataset_key':key,'source_url':url,'evidence_id':eid,'collected_at':now(),
        'fields':[],'request_parameters':[],'structural_elements':[],'issues':[],
        'status':'response_definition_observed','human_approved':False,'raw_values_checked':False,
        'observation_api_called':False,'all_columns_complete':False,'parser_version':1}
def save(portal,records,docs,extra):
    store_catalog(portal,records);dump(HERE/'inventory'/(portal+'-catalog.json'),records)
    for d in docs:dump(HERE/'definitions'/(portal+'-schema-'+d['dataset_key']+'.json'),d)
    report={'generated_at':now(),'scope':portal+'-public-reference','target_count':len(records),'processed':len(docs),
        'queue_exhausted':True,'status_counts':dict(Counter(d['status'] for d in docs)),
        'documented_field_occurrences':sum(len(d['fields']) for d in docs),'all_portal_catalogs_complete':False,'all_columns_complete':False}
    dump(HERE/(portal+'-collection-report.json'),report)
    qa={'generated_at':now(),'portal_id':portal,'scope':'Public documentation availability and consistency; not measured data quality',
        'records':len(records),'response_field_occurrences':sum(len(d['fields']) for d in docs),
        'request_parameter_occurrences':sum(len(d['request_parameters']) for d in docs),
        'structure_occurrences':sum(len(d['structural_elements']) for d in docs),
        'issues':[{'dataset_key':d['dataset_key'],**x} for d in docs for x in d['issues']],
        'quality_scores_assigned':False,'raw_values_checked':False,'all_columns_complete':False,**extra}
    dump(HERE/(portal+'-source-qa.json'),qa);print(json.dumps(report,ensure_ascii=False))

def kdi():
    portal='kdi-api';eid='kdi-api-public-guide-20260914';url='https://www.kdi.re.kr/share/openAPI'
    body,r=fetch(eid,url)
    if body is None:raise ValueError('KDI guide unresolved')
    s=BeautifulSoup(body,'html.parser');tables=s.select('table');options=s.select('option');records=[];docs=[]
    for n,opt in enumerate(options):
        code=opt['value'];container=s.select_one('#type_'+code);title=opt.get_text(' ',strip=True)
        if not re.fullmatch('[A-Z]',code) or container is None:raise ValueError('KDI documented category missing')
        ts=container.select('table')
        if [t.get('id') for t in ts]!=['tb_01','tb_02','tb_03']:raise ValueError('KDI guide tables changed')
        info=[cells(tr) for tr in ts[0].select('tbody tr')]
        if len(info)!=2 or any(x[1]!=title or parse_qs(urlsplit(x[2]).query).get('cd')!=[code] for x in info):raise ValueError('KDI category and documented URL mismatch')
        record=row(portal,code,title,url+'#type_'+code,eid,kind='public_api_category_definition',locator=f'option[{n}]',
            category_code_as_reported=code,source_api_urls_not_requested=[x[2] for x in info],
            registration_identity_basis='Documented cd category, not an individual research-publication record')
        records.append(record);d=base(portal,code,record['url'],eid)
        d.update(reference_container_id='type_'+code,basic_information_as_reported=info,source_qa_reference=portal+'-source-qa.json')
        if [x.get_text(' ',strip=True) for x in ts[1].select('thead th')]!=['요청변수','타입','기본 값','설명']:raise ValueError('KDI request header changed')
        for rn,tr in enumerate(ts[1].select('tbody tr')):
            v=cells(tr);loc=f'table[{tables.index(ts[1])}].tbody.tr[{rn}]'
            if len(v)!=4:raise ValueError('KDI input shape changed')
            d['request_parameters'].append({'name_en':v[0],'source_type_as_reported':v[1],'default_as_reported':v[2],
                'description':v[3],'source_cells':v,'locator':loc})
            if v[0]=='cd' and v[2]!=code:d['issues'].append({'issue':'request_default_cd_differs_from_category_and_URL','locator':loc,'value_as_reported':v[2],'category_code':code,'correction_applied':False})
        if [x.get_text(' ',strip=True) for x in ts[2].select('thead th')]!=['노드','타입','설명']:raise ValueError('KDI output header changed')
        for rn,tr in enumerate(ts[2].select('tbody tr')):
            v=cells(tr)
            if len(v)!=3:raise ValueError('KDI response shape changed')
            f={'name_en':v[0],'name':v[0],'datatype':v[1] if v[1]!='-' else None,'source_type_as_reported':v[1],
                'description':v[2],'unit':None,'source_cells':v,'locator':f'table[{tables.index(ts[2])}].tbody.tr[{rn}]'}
            if v==['ARCHIVES','-','전체 검색 결과 리스트']:f['role']='documented_structure_or_list_element';d['structural_elements'].append(f)
            else:f['role']='api_response_control' if v[0]=='TOTAL_COUNT' else 'api_response_column';d['fields'].append(f)
        d['example_only_container_names_not_promoted_to_fields']=True
        docs.append(d)
    save(portal,records,docs,{'all_select_options_and_reference_sections_reconciled':True,'national_or_institutional_catalog_complete':False,
        'remaining_scope':['Other KDI publicly listed datasets and research publication catalogs','Source default code discrepancy review']})

def kocca():
    portal='kocca-api';eid='kocca-api-usage-guide';url='https://www.kocca.kr/kocca/subPage.do?menuNo=204796'
    b,r=fetch(eid,url)
    if b is None:raise ValueError('KOCCA public guide unresolved')
    s=BeautifulSoup(b,'html.parser');tables=s.select('table');records=[];docs=[]
    for n,c in enumerate(s.select('div.tab_view')):
        link=c.select_one('a[href*="userOpenApiRegist.do"]')
        if link is None:raise ValueError('KOCCA API identity link missing')
        query=parse_qs(urlsplit(link['href']).query);aid=query['apiId'][0];title=query['apiNm'][0];cid=c['id']
        if not aid.isdigit():raise ValueError('KOCCA API id changed')
        boxes=c.select('div.code')
        if len(boxes)!=3:raise ValueError('KOCCA documented URL/sample blocks changed')
        endpoint=boxes[0].get_text(' ',strip=True);sample_url=boxes[1].get_text(' ',strip=True)
        ts=c.select('table')
        if len(ts)!=3:raise ValueError('KOCCA request/response/error tables changed')
        record=row(portal,aid,title,url+'#'+cid,eid,kind='public_api_operation_definition',locator=f'#{cid} a[href*="userOpenApiRegist.do"]@href apiId',
            source_application_link_not_requested=link['href'],source_endpoint_not_requested=endpoint,
            registration_identity_basis='API identifier as explicitly reported in the public application-link URL')
        records.append(record);d=base(portal,aid,record['url'],eid)
        d.update(reference_container_id=cid,request_url_as_reported=endpoint,sample_url_as_reported=sample_url,
            error_code_tables=[],source_qa_reference=portal+'-source-qa.json')
        tn=tables.index(ts[0])
        if [x.get_text(' ',strip=True) for x in ts[0].select('thead th')]!=['항목명','타입','항목구분','항목설명']:raise ValueError('KOCCA request header changed')
        for rn,tr in enumerate(ts[0].select('tbody tr')):
            v=cells(tr)
            if len(v)!=4:raise ValueError('KOCCA request row changed')
            d['request_parameters'].append({'name_en':v[0],'datatype':v[1],'requirement_as_reported':v[2],'description':v[3],
                'source_cells':v,'locator':f'table[{tn}].tbody.tr[{rn}]'})
        orphan=ts[0].tbody.find_all(['th','td'],recursive=False)
        if orphan:
            v=[x.get_text(' ',strip=True) for x in orphan]
            if len(v)!=4 or v[0]!='numOfRows':raise ValueError('Unreviewed orphan input cells')
            d['request_parameters'].append({'name_en':v[0],'datatype':v[1],'requirement_as_reported':v[2],'description':v[3],
                'source_cells':v,'locator':f'table[{tn}].tbody.direct_cells[0:4]','source_row_tag_missing':True})
            d['issues'].append({'issue':'request_parameter_td_cells_without_tr','locator':f'table[{tn}].tbody.direct_cells[0:4]','parameter':'numOfRows','source_html_repaired':False})
        tn=tables.index(ts[1]);output_table=ts[1];physical_rows=output_table.select('tbody tr');overruns={}
        for rn,tr in enumerate(physical_rows):
            for cn,cell in enumerate(tr.find_all(['th','td'],recursive=False)):
                height=int(cell.get('rowspan',1))
                if rn+height>len(physical_rows):
                    if cell.get_text(' ',strip=True)!='List':raise ValueError('Unreviewed overflowing span')
                    overruns[(rn,cn)]=height
                    d['issues'].append({'issue':'source_rowspan_extends_past_table_end','locator':f'table[{tn}].tbody.tr[{rn}].cell[{cn}]',
                        'source_rowspan':height,'visible_rows':len(physical_rows)-rn,'nonexistent_rows_not_created':True})
        if overruns:
            # Bound expansion to visible rows while keeping original spans in every source cell.
            output_table=deepcopy(output_table);bounded=output_table.select('tbody tr')
            for (rn,cn),height in overruns.items():bounded[rn].find_all(['th','td'],recursive=False)[cn]['rowspan']=str(len(bounded)-rn)
        rows=grid(output_table,tn)
        for rr in rows:
            for cell in rr['source_cells']+rr['expanded_cell_sources']:
                if (cell['source_row'],cell['source_cell']) in overruns:cell['rowspan']=overruns[(cell['source_row'],cell['source_cell'])]
        if [x.get_text(' ',strip=True) for x in ts[1].select('thead th')]!=['항목명','타입','항목설명']:raise ValueError('KOCCA output header changed')
        for rr in rows:
            v=rr['expanded_cells'];first=rr['expanded_cell_sources'][0];second=rr['expanded_cell_sources'][1]
            if len(v)!=4:raise ValueError('KOCCA output grid changed')
            group='response' if first['locator']==second['locator'] else v[0]
            if group not in ('response','List'):raise ValueError('KOCCA unreviewed structure group')
            f={**rr,'name_en':v[1],'name':v[1],'datatype':v[2],'description':v[3],'unit':None,
                'schema_group_id':group,'documented_path':v[1] if group=='response' else group+'.'+v[1],
                'role':'api_response_column'}
            d['fields'].append(f)
            if group=='List' and first['source_row']==int(re.search(r'tr\[(\d+)\]',rr['locator'])[1]):
                d['structural_elements'].append({'name':'List','role':'documented_structure_or_list_element','locator':first['locator'],'rowspan':first['rowspan']})
        tn=tables.index(ts[2]);heads=[x.get_text(' ',strip=True) for x in ts[2].select('thead th')]
        d['error_code_tables'].append({'table_index':tn,'headers':heads,'rows':[{'source_cells':cells(tr),'locator':f'table[{tn}].tbody.tr[{rn}]'} for rn,tr in enumerate(ts[2].select('tbody tr'))]})
        if heads[1]!='오류 메세지 (resultMsg)':d['issues'].append({'issue':'error_table_resultMgs_differs_from_response_resultMsg','table_index':tn,'source_header':heads[1],'correction_applied':False})
        example={'locator':f'#{cid} div.code[2]','sample_data_requested':False,'names_not_promoted_to_columns':True}
        try:
            payload=json.loads(boxes[2].get_text().strip());info=payload['INFO'];items=info.get('list',[])
            example.update(parse_status='valid_documentation_json',top_container='INFO',root_keys=list(info),list_item_keys=sorted({k for x in items for k in x}))
        except (ValueError,TypeError,KeyError) as exc:example.update(parse_status='malformed_or_changed_documentation_json',error=str(exc))
        d['documentation_example']=example
        d['issues'].append({'issue':'table_example_naming_requires_review','table_names':[f['documented_path'] for f in d['fields']],
            'sample_container_keys':example.get('root_keys'),'sample_item_keys':example.get('list_item_keys'),'sample_url_not_requested':sample_url,'automatic_alignment_applied':False})
        docs.append(d)
    b,_=fetch('kocca-api-public-guide-20260914','https://www.kocca.kr/kocca/subPage.do?menuNo=204795')
    listing=BeautifulSoup(b,'html.parser');source_table=listing.select('table')[0]
    listing_rows=[{'source_cells':cells(tr),'locator':f'table[0].tbody.tr[{rn}]'} for rn,tr in enumerate(source_table.select('tbody tr'))]
    if len(records)!=len(listing_rows):raise ValueError('KOCCA introduction and guide count mismatch')
    dump(HERE/'inventory/kocca-api-introduction-groups.json',{'evidence_id':'kocca-api-public-guide-20260914','rows':listing_rows,
        'name_differences_preserved':'국내산업정보/국내통계정보, 해외산업정보/해외통계정보, 정기간행물/정기간행물_KOCCA포커스',
        'row_order_alone_is_not_entity_identity_proof':True})
    save(portal,records,docs,{'intro_rows':len(listing_rows),'guide_operations':len(records),
        'remaining_scope':['Other publicly disclosed KOCCA data catalogs','Sample/definition naming and malformed input row review'],
        'source_samples_not_live_service_responses':True})

if __name__=='__main__':
    kdi();kocca()
