"""HRFCO's public API reference; schema metadata only, no API tests or keys."""
from common import *
from catalog_storage import row,store_catalog
from collect_grac import grid
from collections import Counter
import re

URL='https://www.hrfco.go.kr/web/openapiPage/reference.do'
EID='hrfco-open-api-reference'

def main():
    body,r=fetch(EID,URL)
    if body is None:raise ValueError('public_reference_unresolved')
    soup=BeautifulSoup(body,'html.parser');tables=soup.select('table');records=[];docs=[]
    containers=soup.select('.includeContainer')
    for container in containers:
        cid=container['id'];parts=container.select('.partBox')
        if len(parts)%3:raise ValueError('request_example_response_groups_changed')
        for pn in range(0,len(parts),3):
            request,examples,response=parts[pn:pn+3]
            rt=request.select('table');ot=response.select('table')
            if len(rt)!=1 or len(ot)!=1:raise ValueError('operation_tables_missing')
            rt,ot=rt[0],ot[0];rn=tables.index(rt);on=tables.index(ot)
            if [x.get_text(' ',strip=True) for x in rt.select('thead th')]!=['변수명','필수여부','사용예','설명']:raise ValueError('request_header_changed')
            if [x.get_text(' ',strip=True) for x in ot.select('thead th')]!=['No','출력명','출력설명']:raise ValueError('response_header_changed')
            request_rows=grid(rt,rn);constants={}
            for field in ['HydroType','DataType']:
                values={x['expanded_cells'][2] for x in request_rows if x['expanded_cells'][0]==field}
                if len(values)!=1:raise ValueError('operation_identity_constants_missing')
                constants[field]=values.pop()
            key=constants['HydroType']+'-'+constants['DataType']
            if not re.fullmatch(r'[a-z]+-(?:list|info)',key):raise ValueError('unexpected_reference_operation_key')
            title=request.select_one('h3').get_text(' ',strip=True)
            item=row('hrfco',key,title,URL+'#'+cid,EID,kind='public_api_operation_definition',locator=f'#{cid} .partBox[{pn}]',
                operation_constants_as_reported=constants,local_id_basis='Project key from explicitly documented HydroType and DataType constants; not a native catalog registration ID',
                catalog_scope='All request/example/response groups in this public reference page')
            records.append(item)
            d={'portal_id':'hrfco','dataset_key':key,'source_url':item['url'],'evidence_id':EID,'fields':[],
                'status':'response_definition_observed','collected_at':now(),'human_approved':False,'raw_values_checked':False,
                'all_columns_complete':False,'observation_api_called':False,'request_parameter_rows':request_rows,
                'request_heading':title,'request_table_index':rn,'response_table_index':on,'container_id':cid,
                'source_operation_constants':constants,'request_notes_as_reported':request.get_text(' ',strip=True),
                'example_urls_as_reported':examples.get_text(' ',strip=True),'example_locator':f'#{cid} .partBox[{pn+1}]',
                'example_urls_not_requested':True,'source_qa_reference':'hrfco-source-qa.json','parser_version':1}
            for n,tr in enumerate(ot.select('tbody tr')):
                cells=tr.find_all(['th','td'],recursive=False);values=[x.get_text(' ',strip=True) for x in cells]
                if len(values)!=3 or not values[0].isdigit() or int(values[0])!=n+1:raise ValueError('output_sequence_or_shape_changed')
                if any(c.has_attr('rowspan') or c.has_attr('colspan') for c in cells):raise ValueError('output_span_requires_review')
                unit=re.search(r'\(단위\s*:\s*([^)]*)\)',values[2])
                d['fields'].append({'name_en':values[1],'name':values[1],'description':values[2],'datatype':None,
                    'unit':unit[1] if unit else None,'unit_extraction_basis':'literal 단위: text in source description' if unit else None,
                    'role':'api_response_column','source_cells':values,'table_index':on,'row_index':n,
                    'locator':f'table[{on}].tbody.tr[{n}]','unit_normalization_performed':False})
            docs.append(d)
    if not records or len({r['dataset_key'] for r in records})!=len(records):raise ValueError('duplicate_or_empty_operation_registry')
    store_catalog('hrfco',records);dump(HERE/'inventory/hrfco-catalog.json',records)
    for d in docs:dump(HERE/'definitions'/('hrfco-schema-'+d['dataset_key']+'.json'),d)
    error_tables=[]
    for n,t in enumerate(tables):
        if [c.get_text(' ',strip=True) for c in t.select('thead th')]==['오류코드','설명']:
            error_tables.append({'table_index':n,'rows':[{'locator':f'table[{n}].tbody.tr[{rn}]',
                'source_cells':[x.get_text(' ',strip=True) for x in tr.find_all(['th','td'],recursive=False)]} for rn,tr in enumerate(t.select('tbody tr'))]})
    dump(HERE/'inventory/hrfco-error-code-tables.json',{'evidence_id':EID,'tables':error_tables,'codes_are_not_response_fields':True})
    warning=soup.select_one('p.cauTitle.red')
    notice=warning.parent if warning else None
    if notice is None:raise ValueError('source_data_caution_missing')
    qa={'generated_at':now(),'portal_id':'hrfco','qa_scope':'Definition availability, literal units and source cautions; not raw-value quality or relationship validation',
        'catalog_operations':len(records),'documented_fields':sum(len(d['fields']) for d in docs),
        'fields_with_literal_units':sum(bool(f['unit']) for d in docs for f in d['fields']),
        'request_table_row_occurrences':sum(len(d['request_parameter_rows']) for d in docs),
        'source_caution':{'evidence_id':EID,'locator':'p.cauTitle.red parent','text_as_reported':notice.get_text(' ',strip=True)},
        'source_description_review_candidates':[{'dataset_key':d['dataset_key'],'evidence_id':EID,'locator':f['locator'],
            'name_as_reported':f['name_en'],'description_as_reported':f['description'],'issue':'dam_or_weir_section_description_mentions_rainfall','correction_applied':False}
            for d in docs if d['source_operation_constants']['HydroType'] in ('dam','bo') for f in d['fields'] if '강수량' in f['description']],
        'datatype_inferred_from_values':False,'unit_spellings_normalized':False,'quality_scores_assigned':False,
        'raw_value_quality_measured':False,'all_columns_complete':False,
        'remaining_scope':['Other public API documents beyond this reference','Radar-service referral scope reconciliation','Live responses and observation station code lists']}
    dump(HERE/'hrfco-source-qa.json',qa)
    report={'generated_at':now(),'scope':'hrfco-public-reference','target_count':len(records),'processed':len(docs),
        'status_counts':dict(Counter(d['status'] for d in docs)),'queue_exhausted':True,
        'documented_field_occurrences':sum(len(d['fields']) for d in docs),'source_document_body_groups':len(records),
        'all_portal_catalogs_complete':False,'all_columns_complete':False}
    dump(HERE/'hrfco-collection-report.json',report)
    registry=read(HERE/'inventory/domestic-portals.json')
    if not any(p['id']=='hrfco' for p in registry['portals']):
        registry['portals'].append({'id':'hrfco','research_name':'한강홍수통제소 Open API','observed_title':soup.title.get_text(' ',strip=True),
            'requested_url':URL,'observed_final_url':r['final_url'],'group':'기관','topics':['수자원','홍수','환경'],'region':'전국',
            'classification_status':'public_document_observed_with_official_referral','operator':None,
            'responsible_organization_candidate':{'name':'한강홍수통제소','basis':'공식 도메인 공개 레퍼런스 제목','evidence_id':EID,'status':'candidate'},
            'official_referrals':[{'source_evidence_id':'water-api-main','source_url':'https://www.wamis.go.kr:8444/wamisweb/main/mainPage.do',
                'link_url':URL,'link_label':'오픈API 바로가기','scope':'WAMIS radar-service replacement referral; not all service identity mapping'}],
            'observation_status':'public_api_reference_observed','entry_kind':'data_service_candidate','evidence_ids':[EID,'water-api-main'],
            'data_api_tested':False,'catalog_collected':True,'operational_status':'public_document_accessible_data_services_not_tested',
            'license_review':'not_reviewed','notes':['공개 레퍼런스의 9개 연산만 수집; WAMIS 강우레이더 대체 안내와 문서 범위가 같은지는 추가 확인 필요.'],
            'next_action':'다른 공식 API 문서·강우레이더 명세·관측소 코드와 범위 대조','scope':'domestic_portal',
            'current_collection':None,'collection_status':'catalog_acquired_columns_partial','all_portal_datasets_collected':False,'all_portal_columns_collected':False})
        dump(HERE/'inventory/domestic-portals.json',registry)
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
