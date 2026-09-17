"""Resume public column-definition collection without fetching observation data."""
from common import *
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from urllib.parse import urlsplit,urljoin
import argparse,sqlite3,re

DB=ROOT/'.local/domestic-catalog/catalog.sqlite3'

def parse_data_go(data):
    s=BeautifulSoup(data,'html.parser');fields=[]
    for table in s.find_all('table'):
        caption=table.find('caption')
        if not caption or '항목명(영문명)' not in caption.get_text():continue
        for tr in table.select('tbody tr'):
            cells=[x.get_text(' ',strip=True) for x in tr.find_all('td',recursive=False)]
            if len(cells)!=12 or not cells[0]:continue
            keys=['name','name_en','description','domain','datatype','max_length','format','unit','source_system','source_db','source_table','code']
            fields.append(dict(zip(keys,cells)))
    # Links are observations of cross-site references, not same-dataset assertions.
    links=[]
    for a in s.select('.value a[href]'):
        u=urljoin('https://www.data.go.kr/',a['href'])
        if urlsplit(u).scheme in ('http','https') and 'data.go.kr' not in (urlsplit(u).hostname or ''):
            links.append({'url':u,'label':a.get_text(' ',strip=True)})
    return fields,list({x['url']:x for x in links}.values())

def collect_one(row):
    key,url=row
    evidence_id='data-go-schema-'+key
    cached=HERE/'definitions'/(evidence_id+'.json')
    if cached.exists():
        return read(cached)
    data,receipt=fetch(evidence_id,url)
    fields,links=parse_data_go(data) if data else ([],[])
    item={'dataset_key':key,'dataset_kind':'FILE','portal_id':'data-go','source_url':url,'evidence_id':evidence_id,
        'status':'column_definition_observed' if fields else ('no_definition_table_observed' if data else 'fetch_unresolved'),
        'fields':fields,'outgoing_links':links,'raw_values_checked':False,'human_approved':False}
    dump(HERE/'definitions'/(evidence_id+'.json'),item)
    time.sleep(.35)
    return item

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--all',action='store_true')
    ap.add_argument('--workers',type=int,default=3);args=ap.parse_args()
    db=sqlite3.connect(DB)
    if args.all:
        targets=db.execute("SELECT dataset_key,min(url) FROM records WHERE portal_id='data-go' AND kind='FILE' GROUP BY dataset_key ORDER BY dataset_key").fetchall()
        scope='all_acquired_data_go_file_catalog_keys'
    else:
        # Broad coverage check of the adapter, one FILE record per provider.
        targets=db.execute("SELECT dataset_key,url FROM records WHERE id IN (SELECT min(id) FROM records WHERE portal_id='data-go' AND kind='FILE' AND output_raw IS NOT NULL GROUP BY provider_id) ORDER BY dataset_key").fetchall()
        scope='one_declared_schema_file_per_provider_adapter_check'
    db.close();statuses={};count=0
    started=now()
    def progress(finished=False):
        dump(HERE/'definition-collection-report.json',{'scope':scope,'target_count':len(targets),
            'processed':count,'remaining':len(targets)-count,'status_counts':statuses,
            'queue_exhausted':finished,'all_columns_complete':False,'started_at':started,'generated_at':now(),'pid':os.getpid()})
    progress()
    workers=min(max(1,args.workers),4);iterator=iter(targets)
    stop=ROOT/'.local/domestic-catalog/data-go-file.stop'
    with ThreadPoolExecutor(max_workers=workers) as ex:
        pending=set()
        while True:
            while len(pending)<workers*2 and not stop.exists():
                row=next(iterator,None)
                if row is None:break
                pending.add(ex.submit(collect_one,row))
            if not pending:break
            done,pending=wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                item=future.result();count+=1;st=item['status'];statuses[st]=statuses.get(st,0)+1
            if count%25==0:
                progress();print('DEFINITIONS',count,'/',len(targets),statuses,flush=True)
    progress(count==len(targets))
    print('DONE',count,statuses,flush=True)

if __name__=='__main__':main()
