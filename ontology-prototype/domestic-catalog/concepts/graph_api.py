"""Bounded read-only queries over the complete source-to-concept graph snapshot."""
from pathlib import Path
from common import ROOT, HERE, read
import sqlite3
import json
from urllib.parse import parse_qs

DB_PATH = ROOT / '.local/domestic-catalog/knowledge-graph.sqlite3'
KINDS = ('catalog_label','documented_field','declared_output')


def connect():
    db=sqlite3.connect(DB_PATH.as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA cache_size=-4096')
    db.execute('PRAGMA temp_store=FILE')
    return db


def escape_like(value):
    return '%'+value.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'


def paths(db,params):
    def value(name,default=''):
        return params.get(name,[default])[0].strip()[:200]
    portal,concept,basis,q=value('portal'),value('concept'),value('basis'),value('q')
    record=value('record')
    mode=value('mode','mapped')
    if mode not in ('mapped','all') or basis not in ('',*KINDS):
        raise ValueError('Invalid graph filter')
    page=int(value('page','1'))
    if not 1 <= page <= 1000000:
        raise ValueError('Invalid graph page')
    overview=json.loads(db.execute("SELECT value FROM meta WHERE key='overview'").fetchone()[0])
    if portal and portal not in {p['portal_id'] for p in overview['portals']}:
        raise ValueError('Unknown portal')
    if concept and concept not in {c['id'] for c in overview['concepts']}:
        raise ValueError('Unknown concept')
    clauses=[];args=[]
    if portal:clauses.append('i.portal_id=?');args.append(portal)
    if record:
        if not db.execute('SELECT 1 FROM records WHERE id=?',(record,)).fetchone():raise ValueError('Unknown record')
        clauses.append('i.record_id=?');args.append(record)
    if basis:clauses.append('i.kind=?');args.append(basis)
    if q:
        clauses.append("(i.label LIKE ? ESCAPE '\\' OR i.name_en LIKE ? ESCAPE '\\')")
        args.extend([escape_like(q),escape_like(q)])
    if concept:
        clauses.append('i.id IN(SELECT item_id FROM mappings WHERE concept_id=?)');args.append(concept)
    elif mode=='mapped':
        clauses.append('i.id IN(SELECT item_id FROM mappings)')
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    total=db.execute('SELECT count(*) FROM items i'+where,args).fetchone()[0]
    size=24
    rows=[dict(r) for r in db.execute('SELECT i.* FROM items i'+where+' ORDER BY i.id LIMIT ? OFFSET ?',args+[size,(page-1)*size])]
    for item in rows:
        item['concept_ids']=[r[0] for r in db.execute('SELECT concept_id FROM mappings WHERE item_id=? ORDER BY concept_id',(item['id'],))]
        item['record']=dict(db.execute('SELECT * FROM records WHERE id=?',(item['record_id'],)).fetchone())
        item['semantic_status']='candidate_pending_human_review' if item['concept_ids'] else 'no_match_to_current_concept_draft'
    return {'snapshot_at':overview['generated_at'],'total':total,'page':page,'page_size':size,
        'pages':(total+size-1)//size,'results':rows,'all_matches_indexed':True,'human_approved':False,
        'filters':{'portal':portal,'concept':concept,'basis':basis,'q':q,'mode':mode,'record':record},'view':'items'}


def registrations(db,params):
    portal=params.get('portal',[''])[0].strip()[:200]
    q=params.get('q',[''])[0].strip()[:200]
    page=int(params.get('page',['1'])[0])
    if not 1<=page<=1000000:raise ValueError('Invalid page')
    overview=json.loads(db.execute("SELECT value FROM meta WHERE key='overview'").fetchone()[0])
    if portal and portal not in {p['portal_id'] for p in overview['portals']}:raise ValueError('Unknown portal')
    clauses=[];args=[]
    if portal:clauses.append('r.portal_id=?');args.append(portal)
    if q:clauses.append("r.title LIKE ? ESCAPE '\\'");args.append(escape_like(q))
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    total=db.execute('SELECT count(*) FROM records r'+where,args).fetchone()[0]
    rows=[dict(r) for r in db.execute('SELECT r.*,(SELECT count(*) FROM items i WHERE i.record_id=r.id) AS source_items FROM records r'+where+' ORDER BY r.id LIMIT 24 OFFSET ?',args+[(page-1)*24])]
    return {'snapshot_at':overview['generated_at'],'total':total,'page':page,'page_size':24,'pages':(total+23)//24,
        'results':rows,'view':'registrations','filters':{'portal':portal,'q':q},'records_with_no_items_included':True}


def item_detail(db,identifier):
    row=db.execute('SELECT * FROM items WHERE id=?',(int(identifier),)).fetchone()
    if not row:return None
    item=dict(row)
    item['record']=dict(db.execute('SELECT * FROM records WHERE id=?',(item['record_id'],)).fetchone())
    item['concept_ids']=[r[0] for r in db.execute('SELECT concept_id FROM mappings WHERE item_id=?',(item['id'],))]
    item['source_terms']=[dict(r) for r in db.execute('SELECT t.id,t.label,t.role,t.occurrences FROM terms t JOIN item_terms it ON it.term_id=t.id WHERE it.item_id=?',(item['id'],))]
    receipt=(HERE/'evidence'/(item['evidence_id']+'.json')).resolve()
    if receipt.is_relative_to((HERE/'evidence').resolve()) and receipt.is_file():
        data=read(receipt)
        item['receipt']={k:data.get(k) for k in ('id','requested_url','retrieved_at','status','sha256','raw_file')}
    item['human_approved']=False
    return item


def serve(handler,url):
    if url.path in ('/concepts/graph','/concepts/graph/'):
        path=HERE/'concepts/graph.html'
        if not path.is_file():handler.send_error(404);return True
        body=path.read_bytes();ctype='text/html; charset=utf-8'
    elif url.path.startswith('/api/concepts/graph/'):
        if not DB_PATH.is_file():handler.send_error(503,'Graph snapshot is being built');return True
        db=connect()
        try:
                if url.path=='/api/concepts/graph/overview':
                    body=db.execute("SELECT value FROM meta WHERE key='overview'").fetchone()[0].encode('utf-8')
                elif url.path=='/api/concepts/graph/paths':
                    body=json.dumps(paths(db,parse_qs(url.query)),ensure_ascii=False).encode('utf-8')
                elif url.path=='/api/concepts/graph/registrations':
                    body=json.dumps(registrations(db,parse_qs(url.query)),ensure_ascii=False).encode('utf-8')
                elif url.path=='/api/concepts/graph/item':
                    params=parse_qs(url.query)
                    item=item_detail(db,params.get('id',['0'])[0])
                    if item is None:handler.send_error(404,'Source item not found');return True
                    body=json.dumps(item,ensure_ascii=False).encode('utf-8')
                else:handler.send_error(404);return True
        finally:db.close()
        ctype='application/json; charset=utf-8'
    else:return False
    handler.send_response(200)
    handler.send_header('Content-Type',ctype)
    handler.send_header('Content-Length',str(len(body)))
    handler.send_header('Cache-Control','no-store')
    handler.send_header('X-Content-Type-Options','nosniff')
    if url.path=='/api/concepts/graph/overview' and parse_qs(url.query).get('download')==['1']:
        handler.send_header('Content-Disposition','attachment; filename="graph-overview.json"')
    handler.end_headers();handler.wfile.write(body)
    return True
