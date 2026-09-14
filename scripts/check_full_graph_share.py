"""Verify every published shard and count against the fixed graph snapshot."""
import gzip, hashlib, json, sqlite3, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_full_graph_share import clean
data=ROOT/'docs/graph-data'
m=json.loads((data/'manifest.json').read_text(encoding='utf8'))
db=sqlite3.connect((ROOT/'.local/domestic-catalog/knowledge-graph.sqlite3').as_uri()+'?mode=ro',uri=True)
db.execute('PRAGMA cache_size=-8192')
def load(part):
    packed=(data/part['file']).read_bytes()
    assert len(packed)==part['bytes']
    assert hashlib.sha256(packed).hexdigest()==part['sha256']
    rows=json.loads(gzip.decompress(packed))
    assert len(rows)==part['rows']
    return rows
cursor=db.execute('SELECT i.*,(SELECT json_group_array(concept_id) FROM mappings m WHERE m.item_id=i.id) FROM items i ORDER BY i.id')
items=maps=matched=0
for part in m['items']:
    rows=load(part);assert rows[0][0]==part['first'] and rows[-1][0]==part['last']
    stats={}
    for r in rows:
        raw=cursor.fetchone();expect=[clean(v) for v in raw];expect[-1]=json.loads(expect[-1])
        assert r==expect, ('item mismatch',r[0])
        s=stats.setdefault((r[2],r[3]),[0,0,Counter(),r[1],r[1]])
        s[0]+=1;s[1]+=bool(r[-1]);s[2].update(r[-1]);s[3]=min(s[3],r[1]);s[4]=max(s[4],r[1])
        items+=1;maps+=len(r[-1]);matched+=bool(r[-1])
    assert [[*k,a,b,dict(c),lo,hi] for k,(a,b,c,lo,hi) in stats.items()]==part['stats']
assert cursor.fetchone() is None
cursor=db.execute('SELECT r.*,(SELECT count(*) FROM items i WHERE i.record_id=r.id) FROM records r ORDER BY r.id')
records=0
for part in m['records']:
    rows=load(part)
    assert rows[0][0]==part['first'] and rows[-1][0]==part['last']
    assert dict(Counter(r[1] for r in rows))==part['portals']
    for r in rows: assert r==[clean(v) for v in cursor.fetchone()];records+=1
assert cursor.fetchone() is None
receipts=0
for prefix,part in m['receipts'].items():
    rows=load(part)
    for eid,obj in rows.items():
        assert hashlib.sha256(eid.encode()).hexdigest().startswith(prefix)
        assert set(obj)=={'id','requested_url','retrieved_at','status','sha256'}
    receipts+=len(rows)
assert (items,records,maps,matched)==(m['counts']['source_items'],m['counts']['catalog_records'],m['counts']['lexical_mapping_occurrences'],m['counts']['matched_source_items'])
report={'passed':True,'source_items_verified':items,'registrations_verified':records,'mapping_occurrences_verified':maps,'matched_items_verified':matched,'receipts_verified':receipts,'every_row_compared_to_sqlite':True,'every_shard_sha256_checked':True}
(data/'validation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report))
