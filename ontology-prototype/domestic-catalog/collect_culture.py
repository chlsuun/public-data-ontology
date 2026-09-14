"""Collect Culture Data Square's public OpenAPI list and response definitions."""
from common import *
from queue_runner import run_queue
from catalog_storage import row,store_catalog
from urllib.parse import urljoin,urlsplit,parse_qs
from concurrent.futures import ThreadPoolExecutor
import re
BASE='https://www.culture.go.kr'

def catalog_page(page):
    eid=f'culture-api-catalog-page-{page}';url=BASE+f'/data/openapi/openapiList.do?pageNo={page}&gubun=A'
    data,receipt=fetch(eid,url)
    if not data:raise ValueError('catalog_fetch_unresolved:'+eid)
    soup=BeautifulSoup(data,'html.parser');items={}
    for link in soup.select('a[href*="openapiView.do"]'):
        u=urljoin(BASE,link['href']);q=parse_qs(urlsplit(u).query);key=(q.get('id') or [None])[0]
        title=link.select_one('p')
        if key and title and key not in items:
            items[key]=row('culture',key,title.get_text(' ',strip=True),u,eid,kind='API')
    total=re.search(r'총\s*([\d,]+)\s*건의 결과',soup.get_text(' ',strip=True))
    last=soup.select_one('#id_yourpagination .__last a')
    pages=int(parse_qs(urlsplit(last['href']).query)['pageNo'][0]) if last else None
    return items,int(total[1].replace(',','')) if total else None,pages

def collect_one(item):
    key=item['dataset_key'];eid='culture-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    previous=read(path) if path.exists() else None
    if previous:
        if previous['status']!='fetch_unresolved' or previous.get('retry_count',0)>=2:return previous
        prior_receipt=read(HERE/'evidence'/(previous['evidence_id']+'.json'))
        status=prior_receipt.get('http_status')
        if status is not None and status not in (500,502,503,504):return previous
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(previous['collected_at'])).total_seconds()
        if age<120:return previous
        eid+='-retry-'+str(previous.get('retry_count',0)+1)
    data,receipt=fetch(eid,item['url'])
    result={'portal_id':'culture','dataset_key':key,'dataset_kind':'API','evidence_id':eid,'source_url':item['url'],
        'fields':[],'status':'fetch_unresolved','human_approved':False,'raw_values_checked':False,'collected_at':now()}
    if previous:
        result.update(retry_count=previous.get('retry_count',0)+1,previous_fetch_attempt={'evidence_id':previous['evidence_id'],'status':previous['status']})
    if data:
        soup=BeautifulSoup(data,'html.parser');basic={}
        for title in soup.select('p.__title'):
            desc=title.parent.select_one('p.__desc')
            if desc:basic[title.get_text(' ',strip=True)]=desc.get_text(' ',strip=True)
        for ti,table in enumerate(soup.find_all('table')):
            caption=table.find('caption')
            if not caption or '출력 값' not in caption.get_text():continue
            for pos,tr in enumerate(table.select('tbody tr')):
                cells=[x.get_text(' ',strip=True) for x in tr.find_all('td',recursive=False)]
                if len(cells)==3:
                    result['fields'].append({'name':cells[2],'name_en':cells[1],'description':cells[2],
                        'role':'output_column','datatype':None,'unit':None,'locator':f'table[{ti}].tbody.tr[{pos}]'})
        result.update(dataset_metadata=basic,status='column_definition_observed' if result['fields'] else 'definition_unresolved')
    dump(path,result);return result

def main():
    items,total,pages=catalog_page(1)
    if pages is None or total is None:raise ValueError('catalog_count_or_last_page_unresolved')
    received=len(items);totals={total};pagecounts={pages}
    with ThreadPoolExecutor(max_workers=2) as ex:
        for entries,n,p in ex.map(catalog_page,range(2,pages+1)):
            received+=len(entries);items.update(entries);totals.add(n);pagecounts.add(p)
    report={'scope':'문화공공데이터광장 OpenAPI gubun=A; 파일·카탈로그 등 별도 목록은 추가 조사',
        'reported_total':total,'reported_totals_seen':list(totals),'pages_received':pages,
        'received_rows':received,'unique_dataset_ids':len(items),
        'snapshot_pagination_complete':len(totals)==1 and len(pagecounts)==1 and len(items)==received==total,
        'all_portal_catalogs_complete':False,'all_columns_complete':False,'generated_at':now()}
    dump(HERE/'culture-catalog-report.json',report);dump(HERE/'inventory/culture-catalog.json',list(items.values()))
    store_catalog('culture',items.values());print('CATALOG',report,flush=True)
    run_queue('culture',items.values(),collect_one,2)
    # Attach the provider explicitly named on the definition page; never infer it from a title.
    for item in items.values():
        d=read(HERE/'definitions'/('culture-schema-'+item['dataset_key']+'.json'))
        provider=d.get('dataset_metadata',{}).get('제공기관')
        if provider:item.update(provider_name=provider,provider_evidence_id=d['evidence_id'])
    store_catalog('culture',items.values())

if __name__=='__main__':main()
