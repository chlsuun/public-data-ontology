"""Read-only local metadata browser; fixed queries, no arbitrary SQL or files."""
from common import HERE,ROOT,read
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,parse_qs
import json,sqlite3,argparse
DB=ROOT/'.local/domestic-catalog/catalog.sqlite3'

def query(params):
    db=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    db.execute('PRAGMA cache_size=-8192')
    rid=params.get('id',[''])[0]
    if rid:
        row=db.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
        if not row:db.close();return {'error':'등록정보를 찾을 수 없습니다.'}
        r=dict(row);r['metadata']=json.loads(r.pop('metadata_json'))
        r['definitions']=[json.loads(x[0]) for x in db.execute('SELECT definition_json FROM documented_fields WHERE record_id=? ORDER BY evidence_id,ordinal',(rid,))]
        r['tokens']=[dict(x) for x in db.execute('SELECT role,ordinal,name,status FROM fields WHERE record_id=? ORDER BY role,ordinal',(rid,))]
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_documents'").fetchone():
            r['schema_documents']=[json.loads(x[0]) for x in db.execute('SELECT DISTINCT d.metadata_json FROM schema_documents d JOIN schema_document_sources s ON s.path=d.path WHERE s.record_id=?',(rid,))]
        db.close();return r
    conditions=[];values=[]
    for key,column in [('portal','portal_id'),('provider','provider_name'),('q','title')]:
        text=params.get(key,[''])[0].strip()[:200]
        if text:
            conditions.append(column+(' = ?' if key=='portal' else ' LIKE ?'))
            values.append(text if key=='portal' else '%'+text+'%')
    field=params.get('field',[''])[0].strip()[:200]
    if field:
        conditions.append("id IN (SELECT record_id FROM fields WHERE name LIKE ? UNION SELECT record_id FROM documented_fields WHERE name LIKE ? OR name_en LIKE ? UNION SELECT s.record_id FROM schema_documents d JOIN schema_document_sources s ON s.path=d.path, json_each(d.metadata_json,'$.header_candidates') h WHERE h.value LIKE ? UNION SELECT s.record_id FROM schema_documents d JOIN schema_document_sources s ON s.path=d.path, json_each(d.metadata_json,'$.declared_parameter_lists') p, json_each(p.value,'$.response_label_candidates') h WHERE h.value LIKE ? UNION SELECT s.record_id FROM schema_documents d JOIN schema_document_sources s ON s.path=d.path, json_each(d.metadata_json,'$.declared_parameter_lists') p, json_each(p.value,'$.response_name_candidates') h WHERE h.value LIKE ?)")
        values.extend(['%'+field+'%']*6)
    if params.get('documented',[''])[0]=='yes':
        conditions.append('EXISTS(SELECT 1 FROM documented_fields f WHERE f.record_id=records.id)')
    where=' WHERE '+' AND '.join(conditions) if conditions else ''
    page=max(1,min(100000,int(params.get('page',['1'])[0])))
    total=db.execute('SELECT count(*) FROM records'+where,values).fetchone()[0]
    results=[dict(r) for r in db.execute('SELECT id,portal_id,dataset_key,title,provider_name,kind,url,schema_status,'
      '(SELECT count(*) FROM documented_fields f WHERE f.record_id=records.id) AS documented_columns FROM records'+where+
      ' ORDER BY portal_id,id LIMIT 25 OFFSET ?',values+[(page-1)*25])]
    db.close();return {'total':total,'page':page,'page_size':25,'results':results}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path)
        try:
            if path.path.startswith('/concepts') or path.path.startswith('/api/concepts/'):
                from concept_routes import serve
                if serve(self,path):return
            if path.path=='/':
                body=(HERE/'browser.html').read_bytes();ctype='text/html; charset=utf-8'
            elif path.path=='/api/coverage':
                body=json.dumps(read(HERE/'coverage-report.json'),ensure_ascii=False).encode();ctype='application/json; charset=utf-8'
            elif path.path=='/api/portals':
                body=json.dumps(read(HERE/'inventory/domestic-portals.json'),ensure_ascii=False).encode();ctype='application/json; charset=utf-8'
            elif path.path=='/api/progress':
                reports={p.name:read(p) for p in HERE.glob('*-collection-report.json')}
                body=json.dumps({'reports':reports,'national_complete':False},ensure_ascii=False).encode();ctype='application/json; charset=utf-8'
            elif path.path=='/api/search':
                body=json.dumps(query(parse_qs(path.query)),ensure_ascii=False).encode();ctype='application/json; charset=utf-8'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',ctype)
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
        except (ValueError,sqlite3.Error) as e:self.send_error(400,'Invalid query')
    def log_message(self,*args):pass

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8766);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    print(f'국내 메타데이터 검색: http://127.0.0.1:{a.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
