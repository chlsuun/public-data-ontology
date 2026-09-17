"""Expressway public catalog, JSON schema metadata and HTML sample headers."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from urllib.parse import urljoin,urlsplit,parse_qs
from collections import Counter
import re

BASE='https://data.ex.co.kr'
PARAMS={'CATEGORY':'','GROUP_TR':'','serviceType':'','keyWord':'','searchDayFrom':'','searchDayTo':'','orderType':'','pn':'1'}
TYPE_PROPS={'FILE':'file','OPENAPI':'openapi','ORG':'org','LOD':'link'}

def catalog():
    b,r=fetch('expressway-dataset-unfiltered-list',BASE+'/dataset/datasetList/getList',form=PARAMS)
    if b is None:raise ValueError('public_catalog_unresolved')
    source=json.loads(b)
    if not isinstance(source,list) or not source:raise ValueError('public_catalog_shape_changed')
    b,_=fetch('expressway-unfiltered-counts',BASE+'/dataset/datasetList/getDataListCnt',form={})
    if b is None:raise ValueError('independent_catalog_count_unresolved')
    counts=json.loads(b)[0]
    b,_=fetch('expressway-open-api-intro-json-default0',BASE+'/openapi/basicinfo/openApiIntro',form={'apiCnt':'0'},accept='application/json')
    if b is None:raise ValueError('api_catalog_unresolved')
    api_source=json.loads(b)['openApiInfoVOList'];apis={x['apiId']:(n,x) for n,x in enumerate(api_source)}
    if len(apis)!=len(api_source):raise ValueError('api_catalog_repeated_id')
    records=[]
    for n,x in enumerate(source):
        key=str(x['service_ID']);types=[t for t,p in TYPE_PROPS.items() if x.get(p+'_YN')=='Y']
        if not key.isdigit() or len(types)!=1:raise ValueError('service_identity_or_type_changed')
        typ=types[0];prop=TYPE_PROPS[typ]+'_URL';href=x[prop]
        url=urljoin(BASE,href);parsed=urlsplit(url)
        if parsed.hostname!='data.ex.co.kr' or parsed.path not in ('/portal/fdwn/view','/openapi/basicinfo/openApiInfoM','/portal/docu/docuList','/link/linkList'):
            raise ValueError('unreviewed_catalog_destination')
        item=row('expressway',key,x['service_NAME'],url,'expressway-dataset-unfiltered-list',kind=typ,
            locator=f'[{n}]',source_catalog_record=x,description=x.get('meta_CONTENTS'),
            source_category=x.get('category'),source_registration_date=x.get('regist_DATE'),
            portal_identifier_namespace='Expressway service_ID, distinct from apiId and all other portal IDs',
            source_recommended_service_id_as_reported=x.get('recom_SERVICE_ID_1'),
            source_recommendation_is_not_approved_semantic_relation=True)
        if typ=='OPENAPI':
            api_id=parse_qs(parsed.query).get('apiId',[None])[0]
            if not api_id or api_id not in apis:raise ValueError('catalog_api_id_not_in_separate_api_list')
            item.update(api_id=api_id,api_catalog_row=apis[api_id][1],api_catalog_locator=f'openApiInfoVOList[{apis[api_id][0]}]',
                api_catalog_evidence_id='expressway-open-api-intro-json-default0')
        records.append(item)
    assert len({x['dataset_key'] for x in records})==len(records)
    actual=Counter(x['kind'] for x in records)
    expected={t:int(counts[p]) for t,p in [('FILE','file_CNT'),('OPENAPI','openapi_CNT'),('ORG','org_CNT'),('LOD','lod_CNT')]}
    if actual!=expected or sum(expected.values())!=len(records):raise ValueError('catalog_type_count_mismatch')
    category=Counter(x['source_category'] for x in records)
    expected_category={k:int(counts[v]) for k,v in [('TR','tr_CNT'),('CO','co_CNT'),('RO','ro_CNT'),('MA','ma_CNT'),('TO','to_CNT'),('BU','bu_CNT'),('FU','fu_CNT'),('AI','ai_CNT')]}
    if category!=expected_category:raise ValueError('catalog_category_count_mismatch')
    if {x['api_id'] for x in records if x['kind']=='OPENAPI'}!=set(apis):raise ValueError('separate_api_id_set_mismatch')
    store_catalog('expressway',records);dump(HERE/'inventory/expressway-catalog.json',records)
    dump(HERE/'expressway-catalog-report.json',{'generated_at':now(),'catalog_records':len(records),'distinct_service_ids':len(records),
        'source_reported_type_counts':expected,'source_reported_category_counts':expected_category,'actual_type_counts':dict(actual),
        'separate_api_catalog_rows':len(api_source),'api_identifier_sets_match':True,'public_filters':PARAMS,
        'client_pagination_entire_array_observed':True,'snapshot_catalog_counts_reconciled':True,
        'source_count_evidence_id':'expressway-unfiltered-counts','api_list_evidence_id':'expressway-open-api-intro-json-default0',
        'scope':'Unfiltered data-search catalog and separate API list; original observation files and all file versions are not included',
        'all_portal_catalogs_complete':False,'all_columns_complete':False})
    return sorted(records,key=lambda x:({'OPENAPI':0,'FILE':1,'ORG':2,'LOD':3}[x['kind']],x['dataset_key']))

def api_metadata(item,d):
    aid=item['api_id'];eid='expressway-api-schema-json-'+aid
    d.update(evidence_id=eid,api_id=aid,api_metadata_evidence_id='expressway-api-metadata-json-'+aid,
        additional_evidence_ids=['expressway-api-info-script','expressway-dataset-unfiltered-list','expressway-open-api-intro-json-default0'])
    b,r=fetch(eid,BASE+'/openapi/basicinfo/openApiInfoDetail',form={'apiId':aid},accept='application/json')
    if b is None:return d
    payload=json.loads(b)
    if payload['OpenApiInfoVO']['apiId']!=aid:raise ValueError('schema_api_request_identity_mismatch')
    rows=payload['openApiInfoVOList'];d.update(request_parameters=[],unclassified_schema_rows=[],schema_row_count=len(rows),issues=[])
    for n,x in enumerate(rows):
        if x['apiId']!=aid or not x['columeCode']:raise ValueError('schema_row_identity_mismatch')
        f={'name_en':x['columeCode'],'name':x['columeName'] or x['columeCode'],'description':x['columeName'],
            'source_value_token':x['value'],'datatype':x['value'] or None,'datatype_source_label':'value property rendered under 값; retained as documented',
            'unit':None,'requirement_as_reported':x['isEssential'],'locator':f'openApiInfoVOList[{n}]','source_definition':x,
            'role':'api_response_column' if x['isInput']=='N' else 'request_parameter'}
        if x['isInput']=='Y':d['request_parameters'].append(f)
        elif x['isInput']=='N':d['fields'].append(f)
        else:
            f.update(role='unclassified_schema_row',source_input_output_flag=x['isInput'],
                rendered_role_as_observed='The official renderer appends non-Y rows to OpenAPI 출력결과',
                renderer_evidence_id='expressway-api-info-script',renderer_locator='v.drawTable final if(row.isInput==Y) / else tbody3.append(tr)')
            d['unclassified_schema_rows'].append(f)
            d['issues'].append({'issue':'unrecognized_input_output_flag','locator':f['locator'],'value':x['isInput'],
                'row_preserved_in':'unclassified_schema_rows','rendered_output_but_flag_not_repaired':True})
    # These two common input rows are literal UI declarations, separate from JSON rows.
    d['common_ui_request_parameters']=[{'name':'key','datatype':'string','requirement':'필수','description':'발급받은 인증키',
        'evidence_id':'expressway-api-info-script','locator':'v.drawTable i==0 first literal request row'},
        {'name':'type','datatype':'string','requirement':'필수','description':'검색결과 포맷',
        'evidence_id':'expressway-api-info-script','locator':'v.drawTable i==0 second literal request row'}] if rows else []
    b,r=fetch(d['api_metadata_evidence_id'],BASE+'/openapi/basicinfo/openApiInfo',form={'apiId':aid},accept='application/json')
    if b:
        x=json.loads(b)
        if x['OpenApiInfoVO']['apiId']!=aid:raise ValueError('api_metadata_identity_mismatch')
        d['api_metadata_rows']=x['openApiInfoVOList'];d['api_metadata_status']='observed'
    else:d['api_metadata_status']='fetch_unresolved'
    d['status']='response_definition_observed_partial' if d['issues'] else ('response_definition_observed' if d['fields'] else 'api_metadata_observed_schema_pending')
    return d

def html_metadata(body,d):
    s=BeautifulSoup(body,'html.parser')
    if b'</html>' not in body.lower():raise ValueError('html_document_incomplete')
    d.update(header_candidates=[],header_candidate_kind='public_html_sample_header',preview_headers=[],
        metadata_tables=[],other_table_headers=[],outgoing_links=[],issues=[])
    for tn,t in enumerate(s.select('table')):
        caption=t.caption.get_text(' ',strip=True) if t.caption else ''
        headers=[c.get_text(' ',strip=True) for c in t.select('thead th')]
        if caption=='샘플 데이터 입니다.':
            if not headers:d['issues'].append({'issue':'sample_table_has_no_static_header','table_index':tn});continue
            d['header_candidates'].extend(headers)
            d['preview_headers'].append({'evidence_id':d['evidence_id'],'source_url':d['source_url'],
                'locator':f'table[{tn}].thead th','values':headers,'caption':caption,'sample_observation_rows_not_extracted':True,
                'all_file_versions_share_this_header_verified':False})
        elif d['source_kind']=='LOD' and caption in ('출입시설 현황 리스트','휴게소별 편의시설 현황 리스트'):
            if not headers:raise ValueError('public_listing_header_missing')
            d['header_candidate_kind']='public_html_listing_header'
            d['header_candidates'].extend(headers)
            d['preview_headers'].append({'evidence_id':d['evidence_id'],'source_url':d['source_url'],
                'locator':f'table[{tn}].thead th','values':headers,'caption':caption,
                'listing_controls_may_be_included':True,'observation_rows_not_extracted':True,
                'underlying_dataset_columns_verified':False})
        elif caption=='컬럼 설명':
            if headers!=['컬럼명','컬럼 설명']:raise ValueError('column_description_header_changed')
            for rn,tr in enumerate(t.select('tbody tr')):
                cells=tr.find_all(['th','td'],recursive=False);values=[c.get_text(' ',strip=True) for c in cells]
                if len(values)!=2 or any(c.has_attr('rowspan') or c.has_attr('colspan') for c in cells):raise ValueError('column_description_shape_changed')
                if not values[0]:raise ValueError('column_description_name_missing')
                d['fields'].append({'name':values[0],'description':values[1],'datatype':None,'unit':None,
                    'role':'file_column_definition','source_cells':values,'table_index':tn,'row_index':rn,
                    'locator':f'table[{tn}].tbody.tr[{rn}]','all_file_versions_share_this_definition_verified':False})
        elif '기본 상세 정보' in caption:
            d['metadata_tables'].append({'table_index':tn,'caption':caption,'rows':[{'locator':f'table[{tn}].tbody.tr[{rn}]',
                'source_cells':[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]} for rn,tr in enumerate(t.select('tbody tr'))]})
        else:d['other_table_headers'].append({'table_index':tn,'caption':caption,'headers':headers,'not_promoted_to_columns':True})
    for n,a in enumerate(s.select('a[href]')):
        url=urljoin(d['source_url'],re.sub(r';jsessionid=[^?&#/]+','',a['href']))
        p=urlsplit(url)
        if p.scheme in ('http','https') and p.hostname!='data.ex.co.kr' and re.search(r'/(?:data|dataset)/[0-9]+/',p.path):
            d['outgoing_links'].append({'url':url,'label':a.get_text(' ',strip=True),'locator':f'a[href][{n}]','same_dataset_asserted':False})
    d['status']='file_column_definition_observed' if d['fields'] else ('sample_header_candidates_observed' if d['header_candidates'] else 'public_metadata_observed_schema_pending')
    return d

def collect(item):
    key=item['dataset_key'];p=HERE/'definitions'/('expressway-schema-'+key+'.json')
    if p.exists() and (read(p).get('parser_version',1)>=3 or '--reparse-cached' not in sys.argv):return read(p)
    d={'portal_id':'expressway','dataset_key':key,'source_url':item['url'],'evidence_id':'expressway-detail-'+key,
        'fields':[],'status':'fetch_unresolved','collected_at':now(),'human_approved':False,'raw_values_checked':False,
        'all_columns_complete':False,'observation_api_called':False,'source_kind':item['kind'],'parser_version':3,
        'source_catalog_evidence_id':item['evidence_id'],'source_catalog_locator':item['locator']}
    try:
        if item['kind']=='OPENAPI':d=api_metadata(item,d)
        else:
            b,r=fetch(d['evidence_id'],item['url'])
            if b:d=html_metadata(b,d)
    except (ValueError,KeyError,TypeError) as exc:d.update(status='parse_unresolved',error=str(exc),fields=[])
    dump(p,d);return d

if __name__=='__main__':run_queue('expressway',catalog(),collect,2)
