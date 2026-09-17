"""Read public Juso API catalog and literal guide tables; never execute JavaScript."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from openapi_schema import javascript_literal
from urllib.parse import urljoin
import re

BASE='https://business.juso.go.kr'

def script_text(eid,url):
    body,receipt=fetch(eid,url)
    if not body:raise ValueError('public_source_unresolved:'+eid)
    return body.decode('utf-8-sig'),receipt

def flat_catalog_objects(source):
    records=[]
    for m in re.finditer(r'\{id:(\d+),',source):
        start=m.start();i=start;depth=0
        while i<len(source):
            ch=source[i]
            if ch in ('"',"'",'`'):
                _,i=javascript_literal(source,i);continue
            if ch=='{':depth+=1
            elif ch=='}':
                depth-=1
                if depth==0:break
            i+=1
        if depth:raise ValueError('catalog_object_boundary_unresolved')
        fragment=source[start:i+1];item={'id':int(m[1]),'source_char_start':start,'source_char_end':i+1}
        for name in ('title','contentTitle','contentText','uniqKey','router'):
            found=re.search(r'\b'+name+r':',fragment)
            if not found:raise ValueError('catalog_property_missing:'+name)
            item[name],_=javascript_literal(fragment,found.end())
        types=re.search(r'\btypes:(\[[^\]]+\])',fragment)
        item['types']=json.loads(types[1]) if types else None
        records.append(item)
    return records

def catalog():
    body,r=fetch('address-main-20260913',BASE+'/')
    soup=BeautifulSoup(body or b'','html.parser');script=soup.select_one('script[type=module][src]')
    if not script:raise ValueError('public_module_entry_missing')
    main_url=urljoin(BASE,script['src']);main,mr=script_text('address-main-js-20260913',main_url)
    assets=set(re.findall(r'assets/[A-Za-z0-9_-]+\.js',main))
    stores=[a for a in assets if a.startswith('assets/apiListStore-')]
    if len(stores)!=1:raise ValueError('catalog_store_not_uniquely_observed')
    store_url=urljoin(BASE,stores[0]);source,sr=script_text('address-api-store',store_url)
    items=flat_catalog_objects(source);records=[];issues=[]
    for item in items:
        component=item['router'].rsplit('/',1)[-1]
        matches=[a for a in assets if a.startswith('assets/'+component+'-')]
        if len(matches)!=1:issues.append({'service':item['uniqKey'],'issue':'guide_component_not_unique','candidates':matches})
        records.append(row('address',item['uniqKey'],item['contentTitle']+' '+item['title'],BASE+item['router'],sr['id'],
            kind='documented_api_service',locator=f'JavaScript characters {item["source_char_start"]}:{item["source_char_end"]}',
            source_catalog_object=item,guide_component_url=urljoin(BASE,matches[0]) if len(matches)==1 else None,
            public_catalog_url=BASE+'/jst/jstAddressApiList',catalog_scope='public API integration service variants',
            supported_types_as_reported=item['types']))
    keys=[r['dataset_key'] for r in records]
    report={'generated_at':now(),'scope':'주소정보 API 연계 목록의 공개 서비스 변형; 주소 DB 다운로드 목록은 별도',
        'catalog_records':len(records),'unique_service_keys':len(set(keys)),
        'source_ui_list_length':len(items),'source_display_order_ids':[x['id'] for x in items],
        'source_evidence_id':sr['id'],'navigation_evidence_ids':[r['id'],mr['id']],
        'snapshot_api_list_reconciles':bool(records) and len(set(keys))==len(items) and not issues,
        'reconciliation_basis':'공개 UI getApiList()에 사용된 정적 배열 전체의 객체 수·고유 uniqKey·가이드 경로 대조',
        'issues':issues,'all_portal_catalogs_complete':False,'all_columns_complete':False,
        'remaining':'지도 API 등 다운로드 가이드, 주소 DB·공간정보·코드 자료의 별도 목록 및 명세'}
    store_catalog('address',records);dump(HERE/'inventory/address-catalog.json',records)
    dump(HERE/'address-catalog-report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
    return records

def static_html_literals(source):
    end=0
    for m in re.finditer(r'["\'`]<',source):
        if m.start()<end:continue
        try:value,end=javascript_literal(source,m.start())
        except ValueError:continue
        if '<table' in value:yield m.start(),end,value

def expanded_rows(table):
    carry={}
    for rn,tr in enumerate(table.select('tbody tr')):
        cells=tr.find_all(['th','td'],recursive=False);values={};next_carry={}
        for col,(value,left) in carry.items():
            values[col]=value
            if left>1:next_carry[col]=(value,left-1)
        col=0
        for cell in cells:
            while col in values:col+=1
            value=cell.get_text(' ',strip=True);width=int(cell.get('colspan',1));height=int(cell.get('rowspan',1))
            for offset in range(width):
                values[col+offset]=value
                if height>1:next_carry[col+offset]=(value,height-1)
            col+=width
        carry=next_carry
        yield rn,[values[k] for k in sorted(values)],[c.get_text(' ',strip=True) for c in cells]

def parse_guide(source,eid):
    fields=[];requests=[];supporting=[];rejected=[];tables_seen=0
    for start,end,html in static_html_literals(source):
        soup=BeautifulSoup(html,'html.parser')
        for tn,table in enumerate(soup.select('table')):
            tables_seen+=1;headers=[]
            for cell in table.select('thead th'):headers.extend([cell.get_text(' ',strip=True)]*int(cell.get('colspan',1)))
            role='output_column' if '출력변수명' in headers else 'request_parameter' if '요청변수명' in headers else None
            label=table.find('caption');caption=label.get_text(' ',strip=True) if label else None
            if role is None:
                supporting.append({'caption':caption,'headers':headers,'evidence_id':eid,
                    'locator':f'JavaScript literal at {start}:{end} / table[{tn}]',
                    'rows':[{'row':rn,'cells':cells,'expanded_cells':values} for rn,values,cells in expanded_rows(table)]});continue
            target='출력변수명' if role=='output_column' else '요청변수명'
            name_indexes=[n for n,h in enumerate(headers) if h==target];name_index=name_indexes[-1]
            for rn,values,original in expanded_rows(table):
                loc=f'JavaScript literal at {start}:{end} / table[{tn}].tbody.tr[{rn}]'
                name=values[name_index] if len(values)>name_index else ''
                printed_name=name
                if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',name):
                    for cell in table.select('tbody tr')[rn].find_all(['th','td'],recursive=False):
                        if cell.find('br') and cell.get_text(' ',strip=True)==name:
                            joined=cell.get_text('',strip=True)
                            if re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',joined):name=joined
                if len(values)!=len(headers) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',name):
                    rejected.append({'locator':loc,'headers':headers,'expanded_cells':values,'role':role});continue
                def value(label):return values[headers.index(label)] if label in headers else None
                item={'name':name,'name_en':name,'description':value('설명'),'datatype':value('타입'),'unit':None,
                    'printed_identifier':printed_name,'identifier_text_handling':'HTML br layout break removed' if name!=printed_name else 'as_printed',
                    'required_as_reported':value('필수여부'),'default_as_reported':value('기본값'),
                    'role':role,'evidence_id':eid,'locator':loc,'literal_start':start,'literal_end':end,
                    'table_index':tn,'row_index':rn,'source_headers':headers,'source_cells':original,'expanded_source_cells':values,
                    'response_group_as_reported':values[name_indexes[0]] if role=='output_column' and len(name_indexes)>1 else None}
                (fields if role=='output_column' else requests).append(item)
    return {'fields':fields,'request_parameters':requests,'supporting_definition_tables':supporting,'rejected_rows':rejected,
        'literal_tables_observed':tables_seen,'javascript_executed':False,'data_api_called':False}

def collect_one(item):
    eid=uid('address-schema',item['dataset_key']);path=HERE/'definitions'/(eid+'.json')
    if path.exists() and read(path).get('parser_version',1)>=2:return read(path)
    url=item['guide_component_url']
    result={'portal_id':'address','dataset_key':item['dataset_key'],'dataset_kind':'documented_api_service',
        'source_url':url or item['url'],'documentation_page_url':item['url'],'evidence_id':eid,
        'fields':[],'request_parameters':[],'collected_at':now(),'human_approved':False,'raw_values_checked':False,'status':'fetch_unresolved','parser_version':2}
    if url:
        try:
            source,_=script_text(eid,url);result.update(parse_guide(source,eid))
            result['guide_download_links_as_reported']=[urljoin(BASE,x) for x in re.findall(r'"(/api/jst/download\?[^"\s]+)"',source)]
            result['status']='column_definition_observed' if result['fields'] and not result['rejected_rows'] else 'public_guide_observed_schema_partial' if result['fields'] else 'public_guide_observed_schema_pending'
        except (ValueError,KeyError,TypeError) as exc:result.update(error=str(exc)[:300],status='guide_parse_unresolved')
    dump(path,result);return result

def main():run_queue('address',catalog(),collect_one,2)

if __name__=='__main__':main()
