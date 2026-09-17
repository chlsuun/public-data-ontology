"""Index every captured source item and every lexical concept match, without sampling.

The catalog is read-only. The separate graph index is a fixed snapshot with
bounded queries; a browser never needs to load millions of source nodes at once.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, HERE, now, read, dump, uid
from build import record_terms
from collections import defaultdict, Counter
import sqlite3
import json
import gzip
import time

OUT = Path(__file__).resolve().parent
DB_PATH = ROOT / '.local/domestic-catalog/knowledge-graph.sqlite3'

def register_model(overview):
    root=read(HERE/'model.json')
    root['knowledge_graph_layer']={'version':overview['version'],'overview':'concepts/graph-overview.json',
        'explorer':'concepts/graph.html','guide':'concepts/GRAPH-README.md',
        'database_workspace_relative':'.local/domestic-catalog/knowledge-graph.sqlite3',
        'snapshot_at':overview['generated_at'],'all_lexical_matches_indexed_without_sampling':True,
        'human_approved_semantic_mappings':0}
    root['instance_files']['knowledge_graph_overview']='concepts/graph-overview.json'
    dump(HERE/'model.json',root)


def main():
    started = now()
    model = read(OUT / 'concept-model.json')
    registry = read(HERE / 'inventory/domestic-portals.json')
    by_id = {c['id']:c for c in model['concepts']}
    aliases = defaultdict(set)
    for c in model['concepts']:
        for label in c['aliases']:
            aliases[label].add(c['id'])
    source = sqlite3.connect((ROOT / '.local/domestic-catalog/catalog.sqlite3').as_uri() + '?mode=ro', uri=True)
    source.execute('PRAGMA cache_size=-8192')
    source.execute('PRAGMA temp_store=FILE')
    source.execute('BEGIN')
    record_total = source.execute('SELECT count(*) FROM records').fetchone()[0]
    field_total = source.execute('SELECT count(*) FROM documented_fields').fetchone()[0]
    token_total = source.execute("SELECT count(*) FROM fields WHERE role='output'").fetchone()[0]
    temp = DB_PATH.with_name('knowledge-graph.build.sqlite3')
    if temp.exists():
        raise RuntimeError('An unfinished graph build exists; inspect it before replacing it.')
    db = sqlite3.connect(temp)
    db.execute('PRAGMA journal_mode=OFF')
    db.execute('PRAGMA synchronous=OFF')
    db.execute('PRAGMA cache_size=-16384')
    db.execute('PRAGMA temp_store=FILE')
    db.executescript('''
      CREATE TABLE records(id TEXT PRIMARY KEY,portal_id TEXT,title TEXT,provider_id TEXT,provider_name TEXT,url TEXT,evidence_id TEXT,locator TEXT);
      CREATE TABLE items(id INTEGER PRIMARY KEY,record_id TEXT,portal_id TEXT,kind TEXT,label TEXT,name_en TEXT,unit TEXT,evidence_id TEXT,ordinal INTEGER,locator TEXT,source_url TEXT,description TEXT,datatype TEXT,role TEXT,is_control INTEGER);
      CREATE TABLE terms(id INTEGER PRIMARY KEY,portal_id TEXT,role TEXT,label TEXT,occurrences INTEGER NOT NULL DEFAULT 0,UNIQUE(portal_id,role,label));
      CREATE TABLE item_terms(item_id INTEGER,term_id INTEGER,PRIMARY KEY(item_id,term_id)) WITHOUT ROWID;
      CREATE TABLE mappings(item_id INTEGER,concept_id TEXT,PRIMARY KEY(item_id,concept_id)) WITHOUT ROWID;
      CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
    ''')
    term_cache = {}
    record_counts = Counter()
    item_counts = Counter()
    controls = 0
    item_no = 0
    mapping_count = 0

    def add_term(item_id, portal, role, label):
        if not isinstance(label, str) or not label.strip():
            return
        label = label.strip()
        key = (portal,role,label)
        tid = term_cache.get(key)
        if tid is None:
            # Bounded cache; SQLite's unique index retains identity across evictions.
            if len(term_cache) > 100000:
                term_cache.clear()
            db.execute('INSERT OR IGNORE INTO terms(portal_id,role,label) VALUES(?,?,?)', key)
            tid = db.execute('SELECT id FROM terms WHERE portal_id=? AND role=? AND label=?',key).fetchone()[0]
            term_cache[key] = tid
        db.execute('INSERT INTO item_terms VALUES(?,?)', (item_id,tid))
        db.execute('UPDATE terms SET occurrences=occurrences+1 WHERE id=?', (tid,))

    def add_item(rid,portal,kind,label,en,unit,eid,ordinal,locator,url,description,datatype,role,control=False):
        nonlocal item_no, mapping_count
        item_no += 1
        db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (item_no,rid,portal,kind,label,en,unit,eid,ordinal,locator,url,description,datatype,role,int(control)))
        item_counts[kind] += 1
        labels = list(dict.fromkeys(x.strip() for x in (label,en) if isinstance(x,str) and x.strip()))
        if kind == 'catalog_label':
            term_role = role
        elif kind == 'declared_output':
            term_role = 'declared_output_token'
        elif control:
            term_role = 'documented_control_label'
        else:
            term_role = 'documented_field_label'
        for name in labels:
            add_term(item_no,portal,term_role,name)
        if unit:
            add_term(item_no,portal,'documented_unit',unit)
        cids = set()
        if not control:
            for name in labels:
                cids.update(c for c in aliases.get(name,()) if by_id[c]['kind'] != 'Unit' and
                            (kind == 'catalog_label' or by_id[c]['kind'] != 'Topic'))
            if kind == 'documented_field':
                cids.update(c for c in aliases.get(unit,()) if by_id[c]['kind'] == 'Unit')
                if portal != 'neis' and label == '행정표준코드':
                    cids.discard('identifierscheme:school-code')
                if portal == 'hrfco':
                    if en == 'RF':cids.add('measure:precipitation')
                    if en == 'WL':cids.add('measure:water-level')
            if portal != 'neis' and label == '행정표준코드':
                cids.discard('identifierscheme:school-code')
        db.executemany('INSERT INTO mappings VALUES(?,?)', ((item_no,c) for c in sorted(cids)))
        mapping_count += len(cids)

    sql = 'SELECT id,portal_id,title,provider_id,provider_name,url,evidence_id,locator,metadata_json FROM records ORDER BY id'
    for n,row in enumerate(source.execute(sql),1):
        rid,portal,title,pid,pname,url,eid,locator,raw = row
        db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?)',row[:8])
        record_counts[portal] += 1
        for role,label,location in record_terms(json.loads(raw)):
            add_item(rid,portal,'catalog_label',label,None,None,eid,None,location,None,None,None,role)
        if n % 100000 == 0:
            db.commit()
            print('CATALOG',n,'/',record_total,'items',item_no,flush=True)
    sql = '''SELECT f.record_id,r.portal_id,f.name,f.name_en,f.unit,f.evidence_id,f.ordinal,
        json_extract(f.definition_json,'$.raw_definition.locator'),json_extract(f.definition_json,'$.source_url'),
        f.description,f.datatype,json_extract(f.definition_json,'$.role')
        FROM documented_fields f JOIN records r ON r.id=f.record_id ORDER BY f.record_id,f.evidence_id,f.ordinal'''
    for n,row in enumerate(source.execute(sql),1):
        rid,portal,label,en,unit,eid,ordinal,locator,url,desc,datatype,role = row
        control = role in ('response_envelope','response_control','api_response_control','error_response') or en in (
            'resultCode','resultMsg','resultMgs','list_total_count','RESULT.CODE','RESULT.MESSAGE','totalCount','numOfRows','pageNo')
        controls += int(control)
        add_item(rid,portal,'documented_field',label,en,unit,eid,ordinal,locator,url,desc,datatype,role,control)
        if n % 200000 == 0:
            db.commit()
            print('FORMAL_FIELDS',n,'/',field_total,'matches',mapping_count,flush=True)
    sql = '''SELECT f.record_id,r.portal_id,f.name,r.evidence_id,f.ordinal,r.url
             FROM fields f JOIN records r ON r.id=f.record_id WHERE f.role='output' ORDER BY f.record_id,f.ordinal'''
    for n,(rid,portal,label,eid,ordinal,url) in enumerate(source.execute(sql),1):
        add_item(rid,portal,'declared_output',label,None,None,eid,ordinal,'stored_fields:role=output;ordinal='+str(ordinal),url,
                 '공식 목록의 출력 문자열을 나눈 후보. 구분자와 항목 경계 검토 전.',None,'declared_output_token')
        if n % 200000 == 0:
            db.commit()
            print('DECLARED_OUTPUT',n,'/',token_total,flush=True)
    source.rollback()
    source.close()
    term_cache.clear()
    print('BUILDING_GRAPH_INDICES',item_no,'source items',mapping_count,'matches',flush=True)
    db.executescript('''
      CREATE INDEX records_portal ON records(portal_id,id);
      CREATE INDEX items_portal_kind ON items(portal_id,kind,id);
      CREATE INDEX items_record ON items(record_id,id);
      CREATE INDEX mappings_concept ON mappings(concept_id,item_id);
      CREATE INDEX item_terms_term ON item_terms(term_id,item_id);
      CREATE INDEX terms_portal_role ON terms(portal_id,role,occurrences DESC);
      CREATE INDEX terms_occurrences ON terms(occurrences DESC,id);
      CREATE TABLE portal_concepts AS
        SELECT i.portal_id,m.concept_id,i.kind,count(*) AS occurrences,count(DISTINCT i.record_id) AS record_count
        FROM mappings m JOIN items i ON i.id=m.item_id GROUP BY i.portal_id,m.concept_id,i.kind;
      CREATE UNIQUE INDEX portal_concepts_key ON portal_concepts(portal_id,concept_id,kind);
    ''')
    portal_items = {p:{'source_items':0,'formal_fields':0,'declared_output':0,'catalog_labels':0,'concepts':0} for p in record_counts}
    for p,kind,num in db.execute('SELECT portal_id,kind,count(*) FROM items GROUP BY portal_id,kind'):
        portal_items[p]['source_items'] += num
        portal_items[p][{'catalog_label':'catalog_labels','documented_field':'formal_fields','declared_output':'declared_output'}[kind]] = num
    for p,n in db.execute('SELECT portal_id,count(DISTINCT concept_id) FROM portal_concepts GROUP BY portal_id'):
        portal_items[p]['concepts'] = n
    term_count = db.execute('SELECT count(*) FROM terms').fetchone()[0]
    matched_items = db.execute('SELECT count(DISTINCT item_id) FROM mappings').fetchone()[0]
    matched_records = db.execute('SELECT count(DISTINCT i.record_id) FROM items i JOIN mappings m ON m.item_id=i.id').fetchone()[0]
    portal_nodes = []
    for p in registry['portals']:
        n = record_counts.get(p['id'],0)
        portal_nodes.append({'id':'portal:'+p['id'],'portal_id':p['id'],'label':p['research_name'],'kind':'Portal',
            'url':p.get('requested_url'),'group':p.get('group'),'catalog_records':n,
            'collection_status':'catalog_partially_collected' if n else 'no_catalog_in_snapshot',
            'evidence_ids':p.get('evidence_ids',[]),**portal_items.get(p['id'],{})})
    assert set(record_counts) <= {p['portal_id'] for p in portal_nodes}
    edges=[]
    for p,c,kind,num,records in db.execute('SELECT * FROM portal_concepts ORDER BY portal_id,concept_id,kind'):
        edges.append({'source':'portal:'+p,'target':c,'kind':kind,'occurrences':num,'record_count':records,
                      'status':'candidate_aggregate','human_approved':False})
    counts={'registered_portal_candidates':len(portal_nodes),'collected_portals':len(record_counts),'project_concepts':len(model['concepts']),
            'catalog_records':record_total,'documented_fields':field_total,'declared_output_tokens':token_total,
            'source_items':item_no,'items_by_kind':dict(item_counts),'source_term_buckets':term_count,'lexical_mapping_occurrences':mapping_count,
            'matched_source_items':matched_items,'unmapped_source_items':item_no-matched_items,'matched_catalog_records':matched_records,
            'portal_concept_pairs':len({(e['source'],e['target']) for e in edges}),'portal_concept_basis_edges':len(edges),
            'control_fields_excluded_from_semantic_matches':controls,'human_approved_semantic_mappings':0}
    overview={'version':'0.1.0','snapshot_started_at':started,'generated_at':now(),'concept_definitions_snapshot_at':model['generated_at'],
        'scope':'현재 저장된 국내 포털 등록정보·원분류·키워드·명세 항목·목록 출력항목 후보 전체. 전국 전수는 아님.',
        'counts':counts,'portals':portal_nodes,'concepts':model['concepts'],'facets':model['facets'],
        'edges':edges,'concept_relationships':model['relationships'],
        'rules':{'all_lexical_matches_indexed_without_sampling':True,'portal_edges_are_path_aggregates_not_semantic_approval':True,
                 'project_concepts_are_not_claimed_to_be_official_portal_ontology':True,'unmapped_items_remain_searchable':True,
                 'snapshot_is_not_live_catalog':True,'header_preview_candidates_not_in_this_graph':True}}
    db.execute('INSERT INTO meta VALUES(?,?)',('overview',json.dumps(overview,ensure_ascii=False)))
    db.commit()
    db.execute('ANALYZE')
    db.close()
    temp.replace(DB_PATH)
    dump(OUT/'graph-overview.json',overview)
    register_model(overview)
    dump(OUT/'graph-build-report.json',{'generated_at':now(),'source_snapshot_started_at':started,'counts':counts,
        'graph_database_bytes':DB_PATH.stat().st_size,'graph_database_path':'.local/domestic-catalog/knowledge-graph.sqlite3',
        'source_database_modified':False,'semantic_approval_performed':False})
    print('GRAPH_READY',json.dumps(counts,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
