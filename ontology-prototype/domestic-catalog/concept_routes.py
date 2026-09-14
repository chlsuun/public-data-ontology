"""Fixed local routes for the draft concept layer; read-only, bounded search."""
from common import HERE
import json,sqlite3
from urllib.parse import parse_qs

FILES={
    '/concepts/files/model':('concept-model.json','application/json; charset=utf-8'),
    '/concepts/files/review':('review-queue.json','application/json; charset=utf-8'),
    '/concepts/files/rdf':('concept-model.ttl','text/turtle; charset=utf-8'),
    '/concepts/files/terms':('source-terms.jsonl.gz','application/gzip'),
    '/concepts/files/guide':('README.md','text/plain; charset=utf-8')}

def serve(handler,url):
    root=HERE/'concepts'
    if url.path.startswith('/concepts/graph') or url.path.startswith('/api/concepts/graph/'):
        from concepts.graph_api import serve as serve_graph
        if serve_graph(handler,url):return True
    if url.path in ('/concepts','/concepts/'):
        path=root/'explorer.html';ctype='text/html; charset=utf-8'
    elif url.path in FILES:
        name,ctype=FILES[url.path];path=root/name
    elif url.path=='/api/concepts/terms':
        params=parse_qs(url.query);query=params.get('q',[''])[0].strip()[:200];role=params.get('role',[''])[0]
        if role not in ('','source_category','keyword_token_candidate','documented_field_label','documented_unit'):
            handler.send_error(400,'Invalid term role');return True
        where=[];args=[]
        if query:
            where.append("label LIKE ? ESCAPE '\\'");args.append('%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
        if role:where.append('role=?');args.append(role)
        clause=' WHERE '+' AND '.join(where) if where else ''
        db=sqlite3.connect((root/'source-terms.sqlite3').as_uri()+'?mode=ro',uri=True)
        try:
            db.execute('PRAGMA cache_size=-4096')
            total=db.execute('SELECT count(*) FROM terms'+clause,args).fetchone()[0]
            rows=[json.loads(x[0]) for x in db.execute('SELECT data_json FROM terms'+clause+' ORDER BY occurrences DESC,id LIMIT 80',args)]
        finally:db.close()
        body=json.dumps({'total':total,'results':rows,'limit':80,'are_validated_concepts':False},ensure_ascii=False).encode()
        handler.send_response(200);handler.send_header('Content-Type','application/json; charset=utf-8')
        handler.send_header('Content-Length',str(len(body)));handler.send_header('Cache-Control','no-store')
        handler.send_header('X-Content-Type-Options','nosniff');handler.end_headers();handler.wfile.write(body);return True
    else:return False
    if not path.is_file():handler.send_error(404,'Concept snapshot not built');return True
    handler.send_response(200);handler.send_header('Content-Type',ctype)
    handler.send_header('Content-Length',str(path.stat().st_size));handler.send_header('Cache-Control','no-store')
    handler.send_header('X-Content-Type-Options','nosniff')
    if url.path in FILES:handler.send_header('Content-Disposition','attachment; filename="'+path.name+'"')
    handler.end_headers()
    with path.open('rb') as f:
        while chunk:=f.read(64*1024):handler.wfile.write(chunk)
    return True
