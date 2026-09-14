"""Collect the public Library Data API manual's service catalog and definitions."""
from common import *
from catalog_storage import row,store_catalog
import io,re
import pdfplumber
from pypdf import PdfReader

MANUAL='https://www.data4library.kr/downloadApiManual'
EID='library-api-manual'

def compact(value):return re.sub(r'\s+',' ',value or '').strip()

def parse_manual(data):
    texts=[page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages]
    version=re.search(r'v\d{8}',texts[0]).group()
    if version!='v20260210':raise ValueError('new_manual_version_requires_catalog_boundary_review:'+version)
    services={};section=None;raw_tables=[];code_tables=[];rejected=[]
    with pdfplumber.open(io.BytesIO(data)) as doc:
        for page_no,(page,text) in enumerate(zip(doc.pages,texts),1):
            if page_no<=2:continue  # Contents pages are not service definitions.
            title=re.search(r'^\s*(\d{1,2})\.\s+([^\n]+)',text,re.M)
            if title:
                section=int(title[1])
                if section<20:services[section]={'number':section,'title':compact(title[2]),
                    'page_start':page_no,'page_end':page_no,'fields':[],'request_parameters':[],
                    'endpoint_urls':[],'endpoint_sources':[],'notes_as_reported':[]}
            service=services.get(section)
            if service:
                service['page_end']=page_no
                # Keep conditions and caveats in the manual with page provenance.
                for note in re.findall(r'⚫\s*([^⚫]+?)(?=⚫|\n\s*|\Z)',text,re.S):
                    service['notes_as_reported'].append({'page':page_no,'text':compact(note)})
            for table_no,table in enumerate(page.find_tables(),1):
                rows=table.extract();clean=[[compact(c) for c in r if compact(c)] for r in rows]
                info={'page':page_no,'table':table_no,'bbox':list(table.bbox),'rows':rows}
                raw_tables.append(info)
                first=clean[0] if clean else []
                if section==20:
                    if first and first[0]=='파라미터명':code_tables.append(info)
                    continue
                if service is None:continue
                if first==['항목명(영문)','항목설명']:
                    for pos,cells in enumerate(clean[1:],1):
                        if len(cells)!=2:
                            rejected.append({'page':page_no,'table':table_no,'row':pos+1,'cells':cells});continue
                        name=re.sub(r'\s+','',cells[0])
                        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name):
                            rejected.append({'page':page_no,'table':table_no,'row':pos+1,'cells':cells});continue
                        original=rows[pos];col=next(i for i,c in enumerate(original) if compact(c))
                        cell_bbox=table.rows[pos].cells[col]
                        service['fields'].append({'name':cells[1],'name_en':name,'description':cells[1],
                            'datatype':None,'unit':None,'role':'documented_response_element',
                            'evidence_id':EID,'locator':f'PDF page {page_no}, table {table_no}, row {pos+1}',
                            'pdf_page':page_no,'pdf_table':table_no,'pdf_row':pos+1,
                            'printed_name':cells[0],'printed_cell_bbox':list(cell_bbox) if cell_bbox else None,
                            'hierarchy_status':'printed_cell_position_preserved; nested_path_not_inferred',
                            'source_row':original})
                elif any('호출 URL' in cells for cells in clean) or any(cells[:2]==['코드','코드설명'] for cells in clean):
                    for pos,cells in enumerate(clean,1):
                        if cells and cells[0]=='호출 URL':
                            # PDF geometry can split a single URL across cells.
                            url=re.sub(r'\s+','',''.join(cells[1:]))
                            if re.fullmatch(r'https?://data4library\.kr/api/[A-Za-z0-9_/]+',url):
                                service['endpoint_urls'].append(url)
                                service['endpoint_sources'].append({'url':url,'evidence_id':EID,
                                    'locator':f'PDF page {page_no}, table {table_no}, row {pos}','source_cells':rows[pos-1]})
                        elif len(cells)==4 and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',cells[0]):
                            service['request_parameters'].append(dict(zip(['name','description','required_as_reported','input_type_as_reported'],cells))|
                                {'evidence_id':EID,'locator':f'PDF page {page_no}, table {table_no}, row {pos}'})
    for service in services.values():service['endpoint_urls']=list(dict.fromkeys(service['endpoint_urls']))
    return version,services,raw_tables,code_tables,rejected,len(texts)

def main():
    data,receipt=fetch(EID,MANUAL,limit=30_000_000)
    if not data or not data.startswith(b'%PDF-'):raise ValueError('public_pdf_manual_not_observed')
    version,services,tables,codes,rejected,pages=parse_manual(data)
    records=[];statuses={};field_count=0
    for number,service in sorted(services.items()):
        key=version+'/service-'+str(number).zfill(2)
        source=MANUAL+'#page='+str(service['page_start'])
        records.append(row('library',key,service['title'],source,EID,kind='documented_api_service',
            locator=f'PDF service {number}, pages {service["page_start"]}-{service["page_end"]}',
            identifier_basis='project identifier for the manual version and numbered service; not a database table ID',
            endpoint_urls_as_documented=service['endpoint_urls'],manual_version=version,
            portal_operator_as_displayed='국립중앙도서관',catalog_scope='public API manual service variants'))
        rejected_here=[r for r in rejected if service['page_start']<=r['page']<=service['page_end']]
        status='column_definition_observed' if service['fields'] and not rejected_here else 'manual_definition_partial'
        definition={'portal_id':'library','dataset_key':key,'dataset_kind':'documented_api_service',
            'evidence_id':EID,'source_url':MANUAL,'fields':service['fields'],
            'request_parameters':service['request_parameters'],'dataset_metadata':{k:v for k,v in service.items() if k not in ('fields','request_parameters')},
            'status':status,'rejected_rows':rejected_here,'manual_version':version,
            'human_approved':False,'raw_values_checked':False,'collected_at':now()}
        dump(HERE/'definitions'/(uid('library-schema',key)+'.json'),definition)
        statuses[status]=statuses.get(status,0)+1;field_count+=len(service['fields'])
    store_catalog('library',records)
    dump(HERE/'inventory/library-catalog.json',records)
    dump(HERE/'inventory/library-manual-tables.json',{'evidence_id':EID,'version':version,'tables':tables})
    dump(HERE/'inventory/library-code-tables.json',{'evidence_id':EID,'version':version,'tables':codes,
        'code_system_identity_not_reconciled':True,'code_values_not_counted_as_fields':True})
    catalog={'generated_at':now(),'source_evidence_id':EID,'manual_version':version,'pdf_pages':pages,
        'scope':'공개 API 매뉴얼의 번호가 붙은 서비스; 도서관별 다운로드 파일 및 테마자료는 별도 조사',
        'expected_numbered_services':19,'received_service_numbers':sorted(services),
        'catalog_records':len(records),'distinct_endpoint_urls':len({u for s in services.values() for u in s['endpoint_urls']}),
        'snapshot_manual_catalog_reconciles':set(services)==set(range(1,20)),
        'all_portal_catalogs_complete':False,'all_columns_complete':False,'rejected_response_rows':rejected,
        'services_missing_endpoint_url':[s['number'] for s in services.values() if not s['endpoint_urls']]}
    dump(HERE/'library-catalog-report.json',catalog)
    report={'scope':'library public API manual','generated_at':now(),'target_count':len(services),'processed':len(services),
        'queue_exhausted':True,'all_columns_complete':False,'status_counts':statuses,
        'documented_field_occurrences':field_count,'manual_sha256':receipt['sha256']}
    dump(HERE/'library-collection-report.json',report);print(json.dumps(catalog,ensure_ascii=False));print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
