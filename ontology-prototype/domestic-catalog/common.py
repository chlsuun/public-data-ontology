"""Local metadata collection with source receipts and bounded HTTP reads."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlencode
import gzip,json,sys,time,os,threading,sqlite3

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'.prototype-tools'))
from bs4 import BeautifulSoup

def now(): return datetime.now(timezone.utc).isoformat()
def uid(prefix,*parts): return prefix+'-'+sha256('\x1f'.join(map(str,parts)).encode()).hexdigest()[:20]
def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+f'.{os.getpid()}.{threading.get_ident()}.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def host_turn(host, cooldown=0):
    """Coordinate public metadata requests across this project's worker processes."""
    path=ROOT/'.local/domestic-catalog/http-pacing.sqlite3';path.parent.mkdir(parents=True,exist_ok=True)
    interval={'www.data.go.kr':.8,'kosis.kr':1.0,'data.seoul.go.kr':1.0}.get(host,1.0)
    while True:
        db=sqlite3.connect(path,timeout=30)
        db.execute('CREATE TABLE IF NOT EXISTS hosts(host TEXT PRIMARY KEY,next_at REAL NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT next_at FROM hosts WHERE host=?',(host,)).fetchone()
        due=row[0] if row else 0;stamp=time.time()
        if cooldown:
            db.execute('INSERT OR REPLACE INTO hosts VALUES(?,?)',(host,max(due,stamp+cooldown)))
            db.commit();db.close();return
        if due<=stamp:
            db.execute('INSERT OR REPLACE INTO hosts VALUES(?,?)',(host,stamp+interval))
            db.commit();db.close();return
        db.rollback();db.close();time.sleep(min(due-stamp,1.0))

def fetch(source_id,url,limit=8_000_000,refresh=False,form=None,referer=None,json_body=None,accept=None):
    """Cache by evidence id; never store cookies, authorization or API secrets."""
    folder=HERE/'evidence';folder.mkdir(exist_ok=True)
    receipt_path=folder/(source_id+'.json')
    if receipt_path.exists() and not refresh:
        receipt=read(receipt_path)
        if receipt.get('status')=='fetched':
            return gzip.decompress((HERE/receipt['raw_file']).read_bytes()),receipt
        return None,receipt
    receipt={'id':source_id,'requested_url':url,'retrieved_at':now()}
    host=urlsplit(url).hostname
    try:
        host_turn(host)
        headers={'User-Agent':'PublicDataOntologyPrototype/0.5 (metadata research)','Accept':'*/*'}
        if accept:
            headers['Accept']=accept
            receipt['request_accept']=accept
        if referer:headers['Referer']=referer
        if form is not None and json_body is not None:raise ValueError('choose_one_request_body')
        body=urlencode(form).encode() if form is not None else None
        if json_body is not None:
            body=json.dumps(json_body,ensure_ascii=False).encode()
            headers['Content-Type']='application/json'
            receipt.update(method='POST',public_json_parameters=json_body)
        elif body is not None:
            headers['Content-Type']='application/x-www-form-urlencoded; charset=UTF-8'
            receipt.update(method='POST',public_form_parameters=form)
        req=Request(url,data=body,headers=headers)
        with urlopen(req,timeout=30) as r:
            data=r.read(limit+1)
            if len(data)>limit: raise ValueError('response_exceeds_byte_limit')
            raw_file='evidence/'+source_id+'.raw.gz'
            (HERE/raw_file).write_bytes(gzip.compress(data,mtime=0))
            receipt.update(status='fetched',http_status=r.status,final_url=r.url,
                content_type=r.headers.get('Content-Type'),bytes=len(data),
                sha256=sha256(data).hexdigest(),raw_file=raw_file)
    except HTTPError as exc:
        data=None;receipt.update(status='fetch_unresolved',http_status=exc.code,error=str(exc)[:300])
        if exc.code in (403,429):
            retry=exc.headers.get('Retry-After','')
            seconds=max(900,int(retry) if retry.isdigit() else 3600)
            host_turn(host,cooldown=seconds)
            receipt['host_cooldown_seconds']=seconds
    except Exception as exc:
        data=None;receipt.update(status='fetch_unresolved',error=str(exc)[:300])
    dump(receipt_path,receipt)
    return data,receipt

if __name__=='__main__':
    _,r=fetch(sys.argv[1],sys.argv[2],limit=120_000_000 if '--bulk' in sys.argv else 8_000_000)
    print(json.dumps(r,ensure_ascii=False))
