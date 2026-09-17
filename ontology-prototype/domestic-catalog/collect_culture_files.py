"""Collect the complete file catalog and only bounded CSV header candidates."""
from common import *
from queue_runner import run_queue
from catalog_storage import row,store_catalog
from urllib.parse import urljoin,urlsplit,parse_qs,quote
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor
import csv,re
BASE='https://www.culture.go.kr'

def catalog_page(page):
    eid=f'culture-file-catalog-page-{page}';url=BASE+f'/data/filedat/filedatList.do?pageNo={page}'
    data,receipt=fetch(eid,url)
    if not data:raise ValueError('catalog_fetch_unresolved:'+eid)
    soup=BeautifulSoup(data,'html.parser');items={}
    for a in soup.select('a[href*="filedatDtl.do"]'):
        u=urljoin(BASE,a['href']);key=(parse_qs(urlsplit(u).query).get('fileDataNo') or [None])[0]
        title=a.select_one('p')
        if key and title and key not in items:items[key]=row('culture',key,title.get_text(' ',strip=True),u,eid,kind='FILE')
    total=re.search(r'총\s*([\d,]+)\s*건의 결과',soup.get_text(' ',strip=True));last=soup.select_one('.pagination .__last a')
    return items,int(total[1].replace(',','')) if total else None,int(parse_qs(urlsplit(last['href']).query)['pageNo'][0]) if last else None

def first_csv_record(eid,url):
    """Store the first CSV record, never the whole file. A first row is a candidate header."""
    receipt_file=HERE/'evidence'/(eid+'.json')
    if receipt_file.exists():return read(receipt_file)
    parsed_url=urlsplit(url);host=parsed_url.hostname
    if parsed_url.scheme not in ('http','https') or host not in ('big.kcisa.kr','www.culture.go.kr'):
        return {'id':eid,'status':'download_host_requires_review','requested_url':url}
    host_turn(host)
    url=quote(url,safe=':/?=&%')
    receipt={'id':eid,'requested_url':url,'retrieved_at':now(),'snapshot_scope':'csv_first_record_only',
        'full_file_downloaded':False,'full_file_sha256':None,'max_metadata_bytes':65536}
    try:
        req=Request(url,headers={'User-Agent':'PublicDataOntologyPrototype/0.5 (metadata research)','Range':'bytes=0-65535'})
        with urlopen(req,timeout=30) as response:
            if 'html' in response.headers.get('Content-Type','').lower():raise ValueError('download_returned_html')
            data=b'';parsed=None
            for _ in range(32):
                chunk=response.readline(65537-len(data));data+=chunk
                if len(data)>65536:raise ValueError('csv_first_record_exceeds_metadata_limit')
                if not chunk:break
                if data.startswith((b'\xff\xfe',b'\xfe\xff')):raise ValueError('utf16_header_requires_separate_adapter')
                decoded=None;encoding=None
                for enc in ('utf-8-sig','cp949'):
                    try:decoded=data.decode(enc);encoding=enc;break
                    except UnicodeDecodeError:continue
                if decoded is None:raise ValueError('header_encoding_unresolved')
                try:rows=list(csv.reader(decoded.splitlines(keepends=True),strict=True))
                except csv.Error:continue
                if rows:
                    parsed=rows[0];break
            if not parsed:raise ValueError('csv_first_record_unresolved')
            if any('<html' in x.lower() or '<!doctype' in x.lower() for x in parsed):raise ValueError('download_returned_markup')
            raw_file='evidence/'+eid+'.raw.gz';(HERE/raw_file).write_bytes(gzip.compress(data,mtime=0))
            receipt.update(status='csv_first_record_observed',http_status=response.status,
                final_url=response.url,content_type=response.headers.get('Content-Type'),
                bytes=len(data),sha256=sha256(data).hexdigest(),raw_file=raw_file,
                encoding=encoding,header_candidates=parsed,first_record_is_header_verified=False)
    except HTTPError as exc:
        receipt.update(status='fetch_unresolved',http_status=exc.code,error=str(exc)[:250])
        if exc.code in (403,429):host_turn(host,cooldown=3600)
    except Exception as exc:receipt.update(status='header_unresolved',error=str(exc)[:250])
    dump(receipt_file,receipt);return receipt

def collect_one(item):
    key=item['dataset_key'];eid='culture-file-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    data,receipt=fetch(eid,item['url']);basic={};candidates=[];header=None
    result={'portal_id':'culture','dataset_key':key,'dataset_kind':'FILE','evidence_id':eid,'source_url':item['url'],
        'fields':[],'status':'fetch_unresolved','human_approved':False,'raw_values_checked':False,'collected_at':now()}
    if data:
        soup=BeautifulSoup(data,'html.parser')
        for title in soup.select('p.__title'):
            desc=title.parent.select_one('p.__desc')
            if desc:basic[title.get_text(' ',strip=True)]=desc.get_text(' ',strip=True)
        for button in soup.select('[onclick]'):
            match=re.search(r"fnFileDwld\('([^']+)'",button['onclick'])
            if not match:continue
            download=match[1];query=parse_qs(urlsplit(download).query)
            filename=(query.get('downFileName') or [''])[0]
            if not filename.lower().endswith('.csv'):continue
            header=first_csv_record(eid+'-header',download)
            candidates=header.get('header_candidates',[]);break
        result.update(dataset_metadata=basic,header_candidates=candidates,
            header_evidence_id=header['id'] if header else None,
            status='csv_header_candidates_observed' if candidates else 'file_schema_unresolved',
            header_note='CSV 첫 레코드에서 읽은 이름 후보이며 공식 칼럼 정의 확인 전이다. 임의의 실제 데이터 값을 칼럼명으로 확정하지 않는다.')
    dump(path,result);return result

def main():
    items,total,pages=catalog_page(1)
    if total is None or pages is None:raise ValueError('catalog_count_or_pagination_unresolved')
    received=len(items);totals={total};pagecounts={pages}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for entries,n,p in pool.map(catalog_page,range(2,pages+1)):
            items.update(entries);received+=len(entries);totals.add(n);pagecounts.add(p)
    report={'scope':'문화공공데이터광장 파일데이터 목록','reported_total':total,'unique_dataset_ids':len(items),
        'received_rows':received,'reported_totals_seen':list(totals),'pages_received':pages,
        'snapshot_pagination_complete':len(totals)==len(pagecounts)==1 and len(items)==received==total,
        'all_columns_complete':False,'generated_at':now()}
    dump(HERE/'culture-file-catalog-report.json',report);dump(HERE/'inventory/culture-file-catalog.json',list(items.values()))
    store_catalog('culture',items.values());print('CATALOG',report,flush=True)
    run_queue('culture-files',items.values(),collect_one,2)
    for item in items.values():
        d=read(HERE/'definitions'/('culture-file-schema-'+item['dataset_key']+'.json'))
        provider=d.get('dataset_metadata',{}).get('기관명')
        if provider:item.update(provider_name=provider,provider_evidence_id=d['evidence_id'])
    store_catalog('culture',items.values())

if __name__=='__main__':main()
