"""Traverse Ulsan's public catalog tabs; preserve row occurrences and references."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import ordered_pages
from urllib.parse import urlencode
import re

BASE='https://data.ulsan.go.kr/portal/unit/ggdata/'
SNAPSHOT='20260913-size15'
TABS={'FILE':('fileList','001002002001000000'),'API':('openList','001002002002000000'),'STD':('standardList','001002002003000000')}

def parse_page(body,kind,page,eid,url):
    if not body.rstrip().endswith(b'</html>'):raise ValueError('truncated_html_document')
    soup=BeautifulSoup(body,'html.parser');hidden=soup.select_one('input[name=page]')
    if hidden is None or hidden.get('value')!=str(page):raise ValueError('response_page_identity_mismatch')
    menu=soup.select_one('input[name=mId]')
    if menu is None or menu.get('value')!=TABS[kind][1]:raise ValueError('response_catalog_tab_mismatch')
    selected=soup.select_one('select[name=recordCountPerPage] option[selected]')
    if selected is None or selected.get('value')!='15':raise ValueError('response_page_size_mismatch')
    last=soup.select_one('a.last[onclick]');m=re.fullmatch(r'goPage\((\d+)\);',last.get('onclick','')) if last else None
    if not m:raise ValueError('last_page_navigation_missing')
    total_pages=int(m[1]);records=[]
    for pos,node in enumerate(soup.select('.result_listbox .rsl_area')):
        title=node.select_one('.rsl_tit');link=title.find_parent('a') if title else None
        if not link:raise ValueError('catalog_title_link_missing')
        target=link.get('href');ref=re.fullmatch(r'https://(?:www\.)?data.go.kr/data/(\d+)/(fileData|openapi|standard)\.do',target or '')
        meta={dl.dt.get_text(' ',strip=True).rstrip(' :'):dl.dd.get_text(' ',strip=True) for dl in node.select('dl') if dl.dt and dl.dd}
        desc=node.select_one('.rsl_txt');fmt=node.select_one('.division')
        key=f'{SNAPSHOT}/{kind}/{page}/{pos}'
        records.append(row('ulsan',key,title.get_text(' ',strip=True),url,eid,kind='catalog_entry_reference',
            provider_name=meta.get('제공기관'),locator=f'.result_listbox .rsl_area[{pos}]',
            external_reference_url=target,source_reference_dataset_id=ref[1] if ref else None,
            source_reference_type=ref[2] if ref else None,source_catalog_tab=kind,source_page=page,source_row=pos,
            source_metadata=meta,source_description=desc.get_text(' ',strip=True) if desc else None,
            source_format=fmt.get_text(' ',strip=True) if fmt else None,
            identity_note='Project snapshot row occurrence ID, not an official Ulsan dataset ID. Different API operations and provider registrations sharing a target URL are retained.',
            same_dataset_asserted=False,joinability_asserted=False))
    if not 1<=len(records)<=15 or (page<total_pages and len(records)!=15):raise ValueError('unexpected_page_row_count')
    return records,total_pages

def page_data(kind,page):
    route,mid=TABS[kind];eid=f'ulsan-{route}-size15-page{page}'
    url=BASE+route+'.do?'+urlencode({'mId':mid,'recordCountPerPage':15,'page':page})
    body,receipt=fetch(eid,url)
    if not body:raise ValueError('fetch_unresolved:'+eid)
    return parse_page(body,kind,page,eid,url)

def main():
    rp=HERE/'ulsan-catalog-report.json';dest=HERE/'inventory/ulsan-catalog.json'
    if rp.exists() and read(rp).get('snapshot_navigation_traversal_complete'):return
    records={};tabs={};errors=[];stop=ROOT/'.local/domestic-catalog/ulsan.stop'
    def checkpoint():
        complete=len(tabs)==3 and not errors and all(t['pages_received']==t['last_page_as_reported'] for t in tabs.values())
        store_catalog('ulsan',list(records.values()));dump(dest,list(records.values()))
        dump(rp,{'generated_at':now(),'scope':'Public FILE, API and STD tabs; other platform/statistics boards remain separate scopes',
            'snapshot_id':SNAPSHOT,'tabs':tabs,'catalog_row_occurrences':len(records),'snapshot_navigation_traversal_complete':complete,
            'advertised_dataset_total':None,'errors':errors,'all_portal_catalogs_complete':False,'all_columns_complete':False,
            'identity_note':'All page row occurrences are retained. Count is not a deduplicated dataset count; the source provides no independent registration IDs in these rows.'})
        dump(HERE/'ulsan-collection-report.json',{'generated_at':now(),'phase':'catalog_pagination','target_count':sum(t['last_page_as_reported'] for t in tabs.values()),
            'processed':sum(t['pages_received'] for t in tabs.values()),'status_counts':{'catalog_row_occurrences':len(records)},
            'queue_exhausted':complete,'all_columns_complete':False,'pid':os.getpid()})
    for kind in TABS:
        first,last=page_data(kind,1);tabs[kind]={'last_page_as_reported':last,'pages_received':0,'rows_received':0,'page_receipts':[]}
        def absorb(page,items,pages):
            if pages!=last:raise ValueError('last_page_changed_during_collection')
            tabs[kind]['pages_received']+=1;tabs[kind]['rows_received']+=len(items)
            tabs[kind]['page_receipts'].append({'page':page,'rows':len(items),'evidence_id':items[0]['evidence_id']})
            records.update({r['id']:r for r in items})
        absorb(1,first,last);checkpoint()
        def get(page):
            try:items,pages=page_data(kind,page);return page,items,pages,None
            except (ValueError,KeyError,TypeError) as exc:return page,[],None,str(exc)
        for page,items,pages,error in ordered_pages(get,range(2,last+1),stop,2):
            if error:errors.append({'kind':kind,'page':page,'error':error})
            else:absorb(page,items,pages)
            if page%10==0:checkpoint()
        checkpoint()
        if stop.exists():break
    print(json.dumps(read(rp),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
