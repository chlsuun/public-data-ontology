"""Food Safety Korea's public catalog and HTML definitions; no observation API calls."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from urllib.parse import urlencode,urljoin
from collections import Counter
import math,re

BASE='https://www.foodsafetykorea.go.kr'
PARAMS={'menu_no':'661','menu_grp':'MENU_GRP31','start_idx':'1','svc_no':'','p_svcTypeCd':'','svc_type_cd':'',
 'cl_cd':'','provd_instt':'','svcChkArr':'','svc_nm':'','search_clCdCode':'','search_provdInsttCode':'','search_svcTypeCode':'','search_keyword':'','show_cnt':'50'}

def catalog():
    dest=HERE/'inventory/foodsafety-catalog.json';rp=HERE/'foodsafety-catalog-report.json'
    if dest.exists() and rp.exists() and read(rp).get('snapshot_pagination_complete'):return read(dest)
    b,r=fetch('foodsafety-public-catalog-page1',BASE+'/api/datasetList.do?menu_grp=MENU_GRP31&menu_no=661')
    if not b or b'/api/searchDatasetList.do' not in b:raise ValueError('public_catalog_navigation_missing')
    records=[];pages=[];totals=[];page=1;expected=None
    while expected is None or page<=math.ceil(expected/50):
        eid=f'foodsafety-list-size50-page{page}';b,r=fetch(eid,BASE+'/api/searchDatasetList.do',form={**PARAMS,'start_idx':str(page)})
        if b is None:raise ValueError('catalog_fetch_unresolved:'+eid)
        x=json.loads(b);total=int(x['total_cnt']);lst=x['list'];expected=total if expected is None else expected
        if total!=expected or not isinstance(lst,list) or len(lst)!=min(50,total-(page-1)*50):raise ValueError('catalog_count_changed_or_incomplete')
        totals.append(total);pages.append({'page':page,'rows':len(lst),'evidence_id':eid,'total':total})
        for pos,s in enumerate(lst):
            key=s['svc_no']
            if not re.fullmatch('[A-Za-z0-9_-]+',key) or int(s['no'])!=(page-1)*50+pos+1:raise ValueError('catalog_identity_or_order_invalid')
            types=[code for code,prop in [('FILE','file_yn'),('LINK','link_yn'),('API','openapi_yn')] if s.get(prop)=='Y']
            records.append(row('foodsafety',key,s['svc_nm'],BASE+'/api/newDatasetDetail.do?'+urlencode({'svc_no':key}),eid,
                provider_id='foodsafety:org:'+s['provd_instt'] if s.get('provd_instt') else None,provider_name=s.get('provd_instt_nm') or None,
                locator=f'list[{pos}]',source_page=page,source_catalog_record=s,source_service_types=types,
                source_classification_code=s.get('cl_cd') or None,source_classification_label=s.get('cl_cd_nm'),
                portal_identifier_namespace='Food Safety Korea svc_no; not data.go publicDataPk',
                catalog_scope='All public types/categories/providers with blank search conditions'))
        page+=1
    if not len({r['id'] for r in records})==len(records)==expected:raise ValueError('catalog_duplicate_or_missing_id')
    store_catalog('foodsafety',records);dump(dest,records)
    dump(rp,{'generated_at':now(),'catalog_records':len(records),'source_reported_total':expected,'page_receipts':pages,
        'service_type_combinations':dict(Counter('+'.join(r['source_service_types']) for r in records)),
        'snapshot_pagination_complete':True,'all_portal_catalogs_complete':False,'all_columns_complete':False,
        'source_form_parameters':PARAMS,'navigation_evidence_id':'foodsafety-public-catalog-page1',
        'scope':'Public unfiltered data catalog; separate dictionaries/notices and full agency information are not presumed included.'})
    return records

def parse(body,key):
    soup=BeautifulSoup(body,'html.parser');identity=soup.select_one('input#svc_no')
    if not identity or identity.get('value')!=key:raise ValueError('detail_service_id_mismatch')
    result={'fields':[],'request_parameters':[],'metadata_tables':[],'response_message_tables':[],
        'response_table_occurrences':[],'request_table_occurrences':[],'file_link_candidates':[],
        'file_metadata_tables':[],'issues':[],'sample_rows_not_promoted_to_fields':True}
    output_groups={};request_groups={}
    for tn,t in enumerate(soup.select('table')):
        caption=t.caption.get_text(' ',strip=True) if t.caption else ''
        head=[c.get_text(' ',strip=True) for c in t.select('thead th')]
        rows=[]
        for rn,tr in enumerate(t.select('tbody tr')):
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]
            rows.append({'source_cells':cells,'locator':f'table[{tn}].tbody.tr[{rn}]','table_index':tn,'row_index':rn})
        if caption=='변수 목록':
            if head!=['번호','항목','설명']:raise ValueError('response_table_header_changed')
            sig=json.dumps([r['source_cells'] for r in rows],ensure_ascii=False)
            result['response_table_occurrences'].append({'table_index':tn,'caption':caption,'headers':head,'rows':rows,
                'same_table_as_index':output_groups.get(sig),'exact_duplicate_table':sig in output_groups})
            if sig in output_groups:continue
            output_groups[sig]=tn
            for r in rows:
                c=r['source_cells']
                if len(c)!=3 or not c[0].isdigit() or not c[1]:result['issues'].append({'issue':'unexpected_response_row',**r});continue
                result['fields'].append({**r,'name_en':c[1],'name':c[2] or c[1],'description':c[2],
                    'datatype':None,'unit':None,'role':'api_response_column','source_sequence_as_reported':c[0]})
        elif caption=='요청인자':
            if head!=['번호','변수명','타입','변수설명','값설명']:raise ValueError('request_table_header_changed')
            sig=json.dumps([r['source_cells'] for r in rows],ensure_ascii=False)
            result['request_table_occurrences'].append({'table_index':tn,'caption':caption,'headers':head,'rows':rows,
                'same_table_as_index':request_groups.get(sig),'exact_duplicate_table':sig in request_groups})
            if sig in request_groups:continue
            request_groups[sig]=tn
            for r in rows:
                c=r['source_cells']
                if len(c)!=5 or not c[0].isdigit():result['issues'].append({'issue':'unexpected_request_row',**r});continue
                result['request_parameters'].append({**r,'name':c[1],'source_type_and_requirement':c[2],'description':c[3],'value_description':c[4]})
        elif caption in ('메타정보','요청주소'):
            result['metadata_tables'].append({'table_index':tn,'caption':caption,'headers':head,'rows':rows})
        elif caption=='openAPI 파일 목록':
            result['file_metadata_tables'].append({'table_index':tn,'caption':caption,'headers':head,'rows':rows,
                'download_controls':[{'locator':f'table[{tn}] a[{an}]','text':a.get_text(' ',strip=True),
                    'href_as_reported':a.get('href'),'onclick_as_reported':a.get('onclick')}
                    for an,a in enumerate(t.select('a'))],
                'file_contents_downloaded':False,'size_unit_kept_as_reported':True})
        elif '메세지코드' in head:
            result['response_message_tables'].append({'table_index':tn,'caption':caption,'headers':head,'rows':rows})
    for n,a in enumerate(soup.select('a[href]')):
        label=a.get_text(' ',strip=True)
        if re.search(r'\.(csv|xlsx?|zip|pdf|hwp|txt)(?:\s|$)',label,re.I):
            result['file_link_candidates'].append({'label':label,'href_as_reported':a['href'],'locator':f'a[href][{n}]','file_downloaded':False})
    return result

def collect(item):
    key=item['dataset_key'];p=HERE/'definitions'/('foodsafety-schema-'+key+'.json')
    if p.exists():return read(p)
    eid='foodsafety-detail-'+key;d={'portal_id':'foodsafety','dataset_key':key,'evidence_id':eid,'source_url':item['url'],
        'additional_evidence_ids':[item['evidence_id'],'foodsafety-public-catalog-page1'],'fields':[],
        'status':'fetch_unresolved','human_approved':False,'raw_values_checked':False,'all_columns_complete':False,
        'collected_at':now(),'observation_api_called':False,'parser_version':1}
    if key=='I2791':
        # The live public catalog renderer explicitly routes this service externally.
        d.update(evidence_id='foodsafety-public-catalog-page1',status='external_reference_observed_schema_pending',
            outgoing_links=[{'url':'https://www.data.go.kr/data/15127578/openapi.do','label':item['title'],
                'locator':'fn_drawList: explicit svc_no == I2791 branch','same_dataset_asserted':False}])
        dump(p,d);return d
    typecode={'FILE':'API_TYPE03','LINK':'API_TYPE05','API':'API_TYPE06'}.get(next(iter(item['source_service_types']),''),'')
    params={**PARAMS,'svc_no':key,'p_svcTypeCd':typecode,'svc_nm':item['title']}
    body,r=fetch(eid,BASE+'/api/newDatasetDetail.do',form=params)
    if body:
        try:
            d.update(parse(body,key))
            d['status']='response_definition_observed_partial' if d['fields'] and d['issues'] else ('response_definition_observed' if d['fields'] else 'public_metadata_observed_schema_pending')
        except (ValueError,TypeError,KeyError) as e:d.update(status='parse_unresolved',error=str(e),fields=[])
    dump(p,d);return d

if __name__=='__main__':run_queue('foodsafety',catalog(),collect,2)
