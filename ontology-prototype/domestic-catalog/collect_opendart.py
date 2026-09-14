"""Collect OpenDART's public service guides without calling data APIs."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from urllib.parse import urljoin,urlparse,parse_qs,urlencode
from collections import Counter
import argparse,re

BASE='https://opendart.fss.or.kr'

def soup_for(eid,url):
    body,receipt=fetch(eid,url)
    if not body:raise ValueError('fetch_unresolved:'+eid)
    return BeautifulSoup(body,'html.parser'),receipt

def text(node):return node.get_text(' ',strip=True)

def read_catalog():
    home,receipt=soup_for('opendart-main-20260913',BASE+'/')
    groups={}
    for a in home.select('a[href]'):
        url=urljoin(BASE,a['href']);parts=urlparse(url)
        if parts.netloc!='opendart.fss.or.kr' or parts.path!='/guide/main.do':continue
        group=parse_qs(parts.query).get('apiGrpCd',[''])[0]
        if group and text(a)!='개발가이드':groups[group]={'name':text(a),'url':url}
    records={};duplicates=[];errors=[];group_reports=[]
    for group,info in groups.items():
        eid='opendart-guide-'+group
        try:
            soup,_=soup_for(eid,info['url']);count=0
            for tn,table in enumerate(soup.select('table')):
                if 'API명' not in text(table):continue
                for rn,tr in enumerate(table.select('tbody tr')):
                    cells=tr.find_all('td',recursive=False);a=tr.select_one('a[href*="/guide/detail.do?"]')
                    if not a:continue
                    if len(cells)!=4:raise ValueError('unexpected_catalog_row_shape')
                    url=urljoin(BASE,a['href']);params=parse_qs(urlparse(url).query)
                    key=params.get('apiId',[''])[0]
                    if not key or params.get('apiGrpCd',[''])[0]!=group:raise ValueError('guide_identifier_missing_or_group_mismatch')
                    if key in records:duplicates.append({'apiId':key,'group':group})
                    records[key]=row('opendart',key,text(cells[1]),url,eid,kind='documented_api_service',
                        locator=f'table[{tn}].tbody.tr[{rn}]',api_group_code=group,api_group_label=info['name'],
                        description_as_reported=text(cells[2]),source_catalog_cells=[text(c) for c in cells],
                        portal_operator_as_displayed='financial supervisory service',
                        portal_operator_evidence_id='opendart-main-20260913')
                    count+=1
            if not count:raise ValueError('empty_guide_group')
            group_reports.append({'code':group,**info,'evidence_id':eid,'guide_count':count})
        except (ValueError,KeyError,TypeError) as exc:errors.append({'group':group,'error':str(exc)})
    # Independently reconcile the public API introduction board (not observations).
    introductions=[];page_reports=[];pages=1;page=1
    while page<=pages:
        eid='opendart-api-list' if page==1 else 'opendart-api-list-page-'+str(page)
        url=BASE+'/intro/infoApiList.do'+('' if page==1 else '?'+urlencode({'pageIndex':page,'searchCnd':'0','searchWrd':'','bbsId':'A0000000000000000001'}))
        try:
            soup,_=soup_for(eid,url);label=text(soup)
            pagination=re.search(r'\[(\d+)\s*/\s*(\d+)\]\s*\[총\s*([\d,]+)건\]',label)
            if not pagination or int(pagination[1])!=page:raise ValueError('introduction_pagination_not_observed')
            pages=int(pagination[2]);total=int(pagination[3].replace(',',''));before=len(introductions)
            for pos,form in enumerate(soup.select('form[name=subForm]')):
                ident=form.select_one('input[name=nttId]');a=form.select_one('a')
                if not ident or not a:raise ValueError('introduction_identity_missing')
                introductions.append({'nttId':ident['value'],'title':text(a),'evidence_id':eid,
                    'locator':f'form[name=subForm][{pos}]','source_url':url})
            page_reports.append({'page':page,'reported_total':total,'reported_pages':pages,'received':len(introductions)-before,'evidence_id':eid})
        except (ValueError,KeyError,TypeError) as exc:errors.append({'page':page,'error':str(exc)});break
        page+=1
    totals={p['reported_total'] for p in page_reports}
    ids={x['nttId'] for x in introductions};titles=Counter(x['title'] for x in introductions)
    guide_titles=Counter(x['title'] for x in records.values())
    reconciles=bool(groups) and len(group_reports)==len(groups) and not errors and not duplicates and len(page_reports)==pages and len(totals)==1 and len(records)==len(introductions)==len(ids)==next(iter(totals)) and titles==guide_titles
    store_catalog('opendart',records.values())
    dump(HERE/'inventory/opendart-catalog.json',list(records.values()))
    dump(HERE/'inventory/opendart-api-introductions.json',introductions)
    report={'generated_at':now(),'scope':'공개 개발가이드의 API 서비스 6개 분류와 별도 API 소개 게시판 대조; 공시 개별 보고서 목록은 아님',
        'groups_discovered':groups,'groups_received':group_reports,'catalog_records':len(records),'unique_api_ids':len(records),
        'introduction_pages':page_reports,'introduction_records':len(introductions),'introduction_unique_ids':len(ids),
        'advertised_introduction_totals':sorted(totals),'guide_and_introduction_titles_match':titles==guide_titles,
        'guide_only_titles':list((guide_titles-titles).elements()),'introduction_only_titles':list((titles-guide_titles).elements()),
        'duplicate_guide_ids':duplicates,'errors':errors,'snapshot_api_catalog_reconciles':reconciles,
        'all_discovered_guide_groups_read':bool(groups) and len(group_reports)==len(groups) and not duplicates and not errors,
        'introduction_pagination_reconciles':len(page_reports)==pages and len(totals)==1 and len(introductions)==len(ids)==next(iter(totals)),
        'all_portal_catalogs_complete':False,'all_columns_complete':False,
        'identity_note':'apiId는 개발가이드 식별자다. 소개 게시판은 건수와 제목 다중집합만 대조하며 nttId와 apiId를 동일 식별자로 선언하지 않는다.',
        'remaining':'재무정보·XBRL·주석 일괄 다운로드의 별도 목록 및 파일 내부 명세는 추가 조사'}
    dump(HERE/'opendart-catalog-report.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return list(records.values())

def parse_definition(body,eid):
    soup=BeautifulSoup(body,'html.parser');fields=[];requests=[];structure=[];tables=[];endpoints=[];rejected=[]
    for tn,table in enumerate(soup.select('table')):
        caption=table.find('caption');label=text(caption) if caption else ''
        headers=[text(h) for h in table.select('thead th')]
        rows=table.select('tbody tr')
        if label=='基本情報':continue
        if label=='기본 정보':
            for rn,tr in enumerate(rows):
                values=[text(c) for c in tr.find_all('td',recursive=False)]
                if len(values)==4 and values[1].startswith(BASE+'/api/'):
                    endpoints.append(dict(zip(['method','url','encoding','format'],values))|
                        {'evidence_id':eid,'locator':f'table[{tn}].tbody.tr[{rn}]'})
        elif label=='요청 인자':
            for rn,tr in enumerate(rows):
                values=[text(c) for c in tr.find_all('td',recursive=False)]
                if len(values)!=5:rejected.append({'table':tn,'row':rn,'kind':'request','cells':values});continue
                requests.append(dict(zip(['name','description','datatype','required_as_reported','value_description'],values))|
                    {'role':'request_parameter','evidence_id':eid,'locator':f'table[{tn}].tbody.tr[{rn}]'})
        elif label=='응답 결과':
            for rn,tr in enumerate(rows):
                cells=tr.find_all('td',recursive=False);values=[text(c) for c in cells]
                if len(values)!=3 or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',values[0]):
                    rejected.append({'table':tn,'row':rn,'kind':'response','cells':values});continue
                icon=cells[0].find('i');indent=cells[0].find('span');icon_classes=icon.get('class',[]) if icon else []
                item={'name_en':values[0],'name':values[1] or values[0],'description':values[2] or None,
                    'datatype':None,'unit':None,'evidence_id':eid,'locator':f'table[{tn}].tbody.tr[{rn}]',
                    'source_cells':values,'source_icon_classes':icon_classes,
                    'source_indent_classes':indent.get('class',[]) if indent else [],
                    'hierarchy_status':'source_indentation_preserved_not_inferred'}
                if 'iconArrow' in icon_classes:item['role']='response_structure_node';structure.append(item)
                elif 'iconFile' in icon_classes:item['role']='output_column';fields.append(item)
                else:rejected.append({'table':tn,'row':rn,'kind':'response_role_unresolved','cells':values})
        elif label and label not in ('OpenAPI 테스트',):
            tables.append({'caption':label,'headers':headers,'evidence_id':eid,'locator':f'table[{tn}]',
                'rows':[[text(c) for c in tr.find_all(['th','td'],recursive=False)] for tr in rows],
                'rowspans':[[c.get('rowspan','1') for c in tr.find_all(['th','td'],recursive=False)] for tr in rows]})
    binary=any('binary' in e['format'].lower() or 'zip' in e['format'].lower() for e in endpoints)
    payload=[f for f in fields if f['name_en'] not in ('status','message')]
    return {'fields':fields,'request_parameters':requests,'response_structure':structure,'documented_endpoints':endpoints,
        'supporting_definition_tables':tables,'rejected_rows':rejected,
        'payload_schema_status':'file_payload_schema_unresolved' if binary and not payload else 'named_response_fields_observed' if payload else 'payload_definition_unresolved',
        'file_payload_downloaded':False,'data_api_called':False}

def collect_one(item):
    eid='opendart-detail-'+item['dataset_key'];path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    body,receipt=fetch(eid,item['url'])
    result={'portal_id':'opendart','dataset_key':item['dataset_key'],'dataset_kind':'documented_api_service',
        'evidence_id':eid,'source_url':item['url'],'fields':[],'request_parameters':[],
        'human_approved':False,'raw_values_checked':False,'collected_at':now(),'status':'fetch_unresolved'}
    if body:
        try:
            parsed=parse_definition(body,eid);result.update(parsed)
            if parsed['rejected_rows'] or not parsed['documented_endpoints']:result['status']='public_definition_partial'
            elif parsed['payload_schema_status']=='file_payload_schema_unresolved':result['status']='response_control_observed_payload_unresolved'
            else:result['status']='column_definition_observed' if parsed['fields'] else 'public_definition_unresolved'
        except (ValueError,KeyError,TypeError) as exc:result.update(status='public_definition_unresolved',error=str(exc)[:300])
    dump(path,result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--catalog-only',action='store_true');args=ap.parse_args()
    items=read_catalog()
    if not args.catalog_only:run_queue('opendart',items,collect_one,2)

if __name__=='__main__':main()
