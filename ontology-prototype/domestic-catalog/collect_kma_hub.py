"""Collect KMA API Hub navigation and public guide schemas; never call data APIs."""
from common import *
from catalog_storage import row,store_catalog
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin,urlparse,parse_qs
import re

BASE='https://apihub.kma.go.kr'
HOME_EID='kma-api-discovery-20260913'

def clean_heading(element):
    clone=BeautifulSoup(str(element),'html.parser')
    for node in clone.select('button,span'):node.decompose()
    return clone.get_text(' ',strip=True)

def parse_guide(body,guide):
    soup=BeautifulSoup(body,'html.parser');table_ids={id(t):n for n,t in enumerate(soup.select('table'))}
    operations=[];current=None;parent=None;h4_index=-1;unassigned=[];ignored=[]
    metadata=[]
    for el in soup.find_all(['h3','h4','a','table']):
        if el.name=='h3':parent=clean_heading(el);current=None
        elif el.name=='h4':
            h4_index+=1;label=clean_heading(el)
            if label in ('요청인자','출력결과'):
                ignored.append({'h4_index':h4_index,'label':label,'reason':'parameter_or_output_heading_not_operation'});continue
            current={'title':label or parent,'section_title':parent,'h4_index':h4_index,'api_url_examples_as_reported':[],
                'fields':[],'request_parameters':[],'issues':[],'output_table_count':0,'request_table_count':0}
            operations.append(current)
        elif el.name=='a' and 'url-link' in el.get('class',[]):
            if current is None:unassigned.append({'issue':'api_url_without_operation_heading','url':el.get('href')})
            else:current['api_url_examples_as_reported'].append(el.get('href'))
        elif el.name=='table':
            tn=table_ids[id(el)];caption=el.caption.get_text(' ',strip=True) if el.caption else ''
            headers=[x.get_text(' ',strip=True) for x in el.select('thead th')]
            if caption=='api 상세':
                metadata.append({'table_index':tn,'rows':[[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)] for tr in el.select('tbody tr')]});continue
            if caption not in ('출력결과','데이터 기본 정보'):continue
            if current is None:
                unassigned.append({'issue':'schema_table_without_operation_heading','table_index':tn,'caption':caption,
                    'section_heading':parent,'headers':headers,
                    'source_rows':[[c.get_text(' ',strip=True) for c in tr.find_all('td',recursive=False)] for tr in el.select('tbody tr')],
                    'status':'observed_at_section_scope_not_automatically_assigned_to_operations'});continue
            is_output=caption=='출력결과';expected=['변수명','의미(단위)','변수명','의미(단위)'] if is_output else ['인자명','의미','설명']
            if headers!=expected:
                current['issues'].append({'issue':'unrecognized_schema_headers','table_index':tn,'headers':headers});continue
            current['output_table_count' if is_output else 'request_table_count']+=1
            for rn,tr in enumerate(el.select('tbody tr')):
                cells=[c.get_text(' ',strip=True) for c in tr.find_all('td',recursive=False)]
                if len(cells)!=len(expected):
                    current['issues'].append({'issue':'unexpected_schema_row_width','table_index':tn,'row_index':rn,'cells':cells});continue
                if is_output:
                    for start in (0,2):
                        code,meaning=cells[start:start+2]
                        if not code and not meaning:continue
                        if not code:
                            current['issues'].append({'issue':'missing_output_variable_name','table_index':tn,'row_index':rn,'cell_start':start});continue
                        current['fields'].append({'name_en':code,'name':meaning or code,'description':meaning,
                            'datatype':None,'unit':None,'meaning_and_unit_as_reported':meaning,
                            'role':'output_column','locator':f'table[{tn}].tbody.tr[{rn}].td[{start}:{start+2}]',
                            'table_index':tn,'row_index':rn,'cell_start':start,'source_cells':cells,
                            'unit_note':'The source combines meaning, units, code systems and timezones; no automatic unit split.'})
                else:
                    current['request_parameters'].append({'name':cells[0],'meaning_as_reported':cells[1],'description':cells[2],
                        'locator':f'table[{tn}].tbody.tr[{rn}]','table_index':tn,'row_index':rn,'source_cells':cells})
    references=[{'url':urljoin(guide['url'],a['href']),'label':a.get_text(' ',strip=True),
        'status':'reference_document_link_observed_not_yet_read'} for a in soup.select('a[href]') if '/getAttachFile.do?' in a['href'] or a['href'].startswith('https://data.kma.go.kr/tmeta/')]
    return operations,metadata,references,unassigned,ignored

def navigation():
    body,receipt=fetch(HOME_EID,BASE+'/')
    if not body:raise ValueError('public_home_unresolved')
    soup=BeautifulSoup(body,'html.parser');roots={}
    for a in soup.select('a[href]'):
        if re.fullmatch(r'/apiList.do\?seqApi=\d+',a['href']) or a['href']=='/specialApiList.do':roots[a['href']]=a.get_text(' ',strip=True)
    if not roots:raise ValueError('public_navigation_not_observed')
    groups=[];guides={};issues=[]
    for path,name in roots.items():
        special=path=='/specialApiList.do';group='special' if special else parse_qs(urlparse(path).query)['seqApi'][0]
        eid='kma-api-group-'+group;url=urljoin(BASE,path);raw,r=fetch(eid,url)
        info={'group_id':group,'name':name,'url':url,'evidence_id':eid,'subcategories':[],'status':r['status']};groups.append(info)
        if not raw:issues.append({'group_id':group,'issue':'group_fetch_unresolved'});continue
        page=BeautifulSoup(raw,'html.parser')
        if special:
            guides[url]={'url':url,'name':name,'group_id':group,'subcategory_id':'special','evidence_id':eid,'parent_evidence_id':HOME_EID};continue
        for li in page.select('li[onclick]'):
            match=re.fullmatch(r"location.href='(/apiList.do\?[^']+)'",li['onclick'])
            if not match:continue
            q=parse_qs(urlparse(match[1]).query)
            if q.get('seqApi')!=[group] or len(q.get('seqApiSub',[]))!=1:raise ValueError('subcategory_parent_mismatch')
            sub=q['seqApiSub'][0];url=urljoin(BASE,match[1]);item={'name':li.get_text(' ',strip=True),'url':url,
                'group_id':group,'subcategory_id':sub,'evidence_id':f'kma-api-guide-{group}-{sub}','parent_evidence_id':eid}
            info['subcategories'].append(item);guides[url]=item
        if not info['subcategories']:issues.append({'group_id':group,'issue':'subcategory_navigation_unresolved'})
    return groups,list(guides.values()),issues

def main():
    groups,guides,issues=navigation();records=[];status_counts={};field_count=0;guide_reports=[];schema_association_issues=[]
    def get(guide):
        body,receipt=fetch(guide['evidence_id'],guide['url']);return guide,body,receipt
    with ThreadPoolExecutor(max_workers=2) as pool:
        for guide,body,receipt in pool.map(get,guides):
            if not body:issues.append({'url':guide['url'],'issue':'guide_fetch_unresolved'});continue
            operations,metadata,refs,unassigned,ignored=parse_guide(body,guide)
            guide_reports.append(dict(guide,operation_sections=len(operations),unassigned=unassigned,ignored_headings=ignored))
            schema_association_issues.extend(dict(guide_url=guide['url'],**x) for x in unassigned)
            for op in operations:
                key=f"guide/{guide['group_id']}/{guide['subcategory_id']}/{op['h4_index']}"
                item=row('kma-api',key,(op['section_title']+' / ' if op['section_title'] and op['title']!=op['section_title'] else '')+(op['title'] or '제목 미확인'),
                    guide['url'],guide['evidence_id'],kind='documented_operation_variant',locator=f'h4[{op["h4_index"]}]',
                    guide_group_id=guide['group_id'],guide_subcategory_id=guide['subcategory_id'],guide_subcategory_name=guide['name'],
                    api_url_examples_as_reported=op['api_url_examples_as_reported'],source_h4_index=op['h4_index'],
                    identity_basis='Project ID from public guide route and heading position; not a provider-assigned API ID.',
                    identity_stability='Guide section order can change on source revision; retain the evidence hash.',
                    guide_metadata=metadata,reference_documents=refs)
                if len(op['api_url_examples_as_reported'])!=1:op['issues'].append({'issue':'operation_url_count_unresolved','count':len(op['api_url_examples_as_reported'])})
                status='column_definition_observed' if op['fields'] and not op['issues'] else ('column_definition_observed_partial' if op['fields'] else 'public_guide_observed_output_schema_pending')
                result={'portal_id':'kma-api','dataset_key':key,'dataset_kind':item['kind'],'evidence_id':guide['evidence_id'],'source_url':guide['url'],
                    'additional_evidence_ids':list(dict.fromkeys([HOME_EID,guide['parent_evidence_id']])),'fields':op['fields'],'request_parameters':op['request_parameters'],
                    'operation_heading':op['title'],'section_heading':op['section_title'],'source_h4_index':op['h4_index'],
                    'api_url_examples_as_reported':op['api_url_examples_as_reported'],'reference_documents':refs,
                    'guide_section_scope_tables':unassigned,
                    'output_table_count':op['output_table_count'],'request_table_count':op['request_table_count'],'issues':op['issues'],
                    'status':status,'human_approved':False,'raw_values_checked':False,'collected_at':now(),'parser_version':1,
                    'api_observation_requests_executed':False,'all_output_formats_documented':False,
                    'scope_note':'Public HTML output-variable tables only; images, binary payloads, separate manuals and codebooks remain for review.'}
                dump(HERE/'definitions'/(uid('kma-api-schema',key)+'.json'),result);records.append(item)
                field_count+=len(op['fields']);status_counts[status]=status_counts.get(status,0)+1
    store_catalog('kma-api',records);dump(HERE/'inventory/kma-api-catalog.json',records)
    report={'generated_at':now(),'scope':'Homepage-linked API guide categories including the special industry guide',
        'root_groups':groups,'guide_pages':guide_reports,'root_group_count':len(groups),'guide_page_count':len(guide_reports),
        'discovered_guide_page_count':len(guides),'catalog_records':len(records),'snapshot_navigation_traversal_complete':len(guide_reports)==len(guides) and not issues,
        'catalog_identity_basis':'Public guide route and h4 position; counts represent documented operation variants, not unique endpoint paths.',
        'issues':issues,'schema_association_issues':schema_association_issues,'all_portal_catalogs_complete':False,'all_columns_complete':False,
        'remaining':'Linked PDF manuals, codebooks, binary/grid/image output structures and public catalogs outside the traversed API navigation.'}
    dump(HERE/'kma-api-catalog-report.json',report)
    dump(HERE/'kma-api-collection-report.json',{'scope':'kma-api','target_count':len(records),'processed':len(records),
        'status_counts':status_counts,'documented_field_occurrences':field_count,'queue_exhausted':True,'all_columns_complete':False,'generated_at':now(),'pid':os.getpid()})
    print(json.dumps({'guides':len(guide_reports),'operations':len(records),'fields':field_count,'statuses':status_counts,'issues':issues},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
