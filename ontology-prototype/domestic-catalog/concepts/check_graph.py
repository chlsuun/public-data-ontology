"""Check complete graph provenance, all lexical matches, aggregation and paging."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import HERE, ROOT, read, dump, now
from build_graph import DB_PATH
from build import record_terms
from collections import defaultdict,Counter
from itertools import zip_longest
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
import json,sqlite3,time


def main():
    started=time.monotonic();checks=[]
    def passed(name,**facts):
        checks.append({'name':name,'status':'passed',**facts})
        print('PASS',name,json.dumps(facts,ensure_ascii=False),flush=True)
    db=sqlite3.connect(DB_PATH.as_uri()+'?mode=ro',uri=True)
    db.execute('PRAGMA cache_size=-8192');db.execute('PRAGMA temp_store=FILE')
    overview=json.loads(db.execute("SELECT value FROM meta WHERE key='overview'").fetchone()[0])
    assert overview==read(HERE/'concepts/graph-overview.json')
    c=overview['counts'];concepts={x['id']:x for x in overview['concepts']};portals={p['portal_id']:p for p in overview['portals']}
    assert len(concepts)==c['project_concepts'] and len(portals)==c['registered_portal_candidates']
    for table,count in [('records',c['catalog_records']),('items',c['source_items']),('terms',c['source_term_buckets']),('mappings',c['lexical_mapping_occurrences'])]:
        assert db.execute('SELECT count(*) FROM '+table).fetchone()[0]==count
    assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    assert not db.execute('SELECT 1 FROM items i LEFT JOIN records r ON r.id=i.record_id WHERE r.id IS NULL OR i.portal_id<>r.portal_id LIMIT 1').fetchone()
    assert not db.execute('SELECT 1 FROM mappings m LEFT JOIN items i ON i.id=m.item_id WHERE i.id IS NULL LIMIT 1').fetchone()
    assert not db.execute('SELECT 1 FROM item_terms x LEFT JOIN items i ON i.id=x.item_id LEFT JOIN terms t ON t.id=x.term_id WHERE i.id IS NULL OR t.id IS NULL LIMIT 1').fetchone()
    assert db.execute('SELECT sum(occurrences) FROM terms').fetchone()[0]==db.execute('SELECT count(*) FROM item_terms').fetchone()[0]
    actual_portals=dict(db.execute('SELECT portal_id,count(*) FROM records GROUP BY portal_id'))
    assert all(portals[p]['catalog_records']==n for p,n in actual_portals.items())
    passed('graph_integrity_complete_inventory_and_reference_identity',records=c['catalog_records'],source_items=c['source_items'],term_buckets=c['source_term_buckets'])

    source_uri=(ROOT/'.local/domestic-catalog/catalog.sqlite3').as_uri()+'?mode=ro'
    db.execute('ATTACH DATABASE ? AS source',(source_uri,))
    assert not db.execute('''SELECT 1 FROM records g LEFT JOIN source.records s ON s.id=g.id
        WHERE s.id IS NULL OR g.portal_id IS NOT s.portal_id OR g.title IS NOT s.title OR g.evidence_id IS NOT s.evidence_id
        OR g.provider_id IS NOT s.provider_id OR g.provider_name IS NOT s.provider_name OR g.url IS NOT s.url OR g.locator IS NOT s.locator LIMIT 1''').fetchone()
    assert not db.execute('''SELECT 1 FROM items i LEFT JOIN source.documented_fields f
        ON f.record_id=i.record_id AND f.evidence_id=i.evidence_id AND f.ordinal=i.ordinal
        WHERE i.kind='documented_field' AND (f.record_id IS NULL OR i.label IS NOT f.name OR i.name_en IS NOT f.name_en
          OR i.unit IS NOT f.unit OR i.description IS NOT f.description OR i.datatype IS NOT f.datatype
          OR i.locator IS NOT json_extract(f.definition_json,'$.raw_definition.locator')
          OR i.source_url IS NOT json_extract(f.definition_json,'$.source_url')) LIMIT 1''').fetchone()
    assert not db.execute('''SELECT 1 FROM items i LEFT JOIN source.fields f ON f.record_id=i.record_id AND f.role='output' AND f.ordinal=i.ordinal
        WHERE i.kind='declared_output' AND (f.record_id IS NULL OR i.label IS NOT f.name) LIMIT 1''').fetchone()
    def expected_catalog_items():
        for rid,raw in db.execute('SELECT s.id,s.metadata_json FROM source.records s JOIN records g ON s.id=g.id ORDER BY s.id'):
            for role,label,locator in record_terms(json.loads(raw)):
                yield rid,role,label,locator
    catalog_labels=0
    actual_catalog=db.execute("SELECT record_id,role,label,locator FROM items WHERE kind='catalog_label' ORDER BY id")
    for expected,actual in zip_longest(expected_catalog_items(),actual_catalog):
        assert expected==actual,(expected,actual)
        catalog_labels+=1
    assert catalog_labels==c['items_by_kind']['catalog_label']
    db.execute('DETACH DATABASE source')
    passed('all_graph_records_catalog_labels_formal_fields_and_declared_tokens_match_source_database',catalog_labels=catalog_labels,formal_fields=c['documented_fields'],output_tokens=c['declared_output_tokens'])

    aliases=defaultdict(set)
    for cid,concept in concepts.items():
        for label in concept['aliases']:aliases[label].add(cid)
    def expected_matches():
        for n,(iid,p,kind,label,en,unit,control) in enumerate(db.execute('SELECT id,portal_id,kind,label,name_en,unit,is_control FROM items ORDER BY id'),1):
            matches=set()
            if not control:
                for term in {x.strip() for x in (label,en) if isinstance(x,str) and x.strip()}:
                    for cid in aliases.get(term,()):
                        role=concepts[cid]['kind']
                        if role!='Unit' and (kind=='catalog_label' or role!='Topic'):matches.add(cid)
                if kind=='documented_field':
                    matches.update(cid for cid in aliases.get(unit,()) if concepts[cid]['kind']=='Unit')
                    if p=='hrfco' and en in ('RF','WL'):
                        matches.add('measure:'+('precipitation' if en=='RF' else 'water-level'))
                if p!='neis' and label=='행정표준코드':matches.discard('identifierscheme:school-code')
            for cid in sorted(matches):yield (iid,cid)
            if n%1000000==0:print('MATCHES_RECOMPUTED',n,'source items',flush=True)
    number=0
    for expected,actual in zip_longest(expected_matches(),db.execute('SELECT item_id,concept_id FROM mappings ORDER BY item_id,concept_id')):
        assert expected==actual,(expected,actual)
        number+=1
    assert number==c['lexical_mapping_occurrences']
    assert number>703 and c['human_approved_semantic_mappings']==0
    passed('all_lexical_matches_recomputed_without_sample_cap',mapping_occurrences=number)

    actual=list(db.execute('''SELECT i.portal_id,m.concept_id,i.kind,count(*),count(DISTINCT i.record_id)
       FROM mappings m JOIN items i ON i.id=m.item_id GROUP BY i.portal_id,m.concept_id,i.kind
       ORDER BY i.portal_id,m.concept_id,i.kind'''))
    exported=[(e['source'][7:],e['target'],e['kind'],e['occurrences'],e['record_count']) for e in overview['edges']]
    assert actual==exported
    assert all(e['human_approved'] is False and e['status']=='candidate_aggregate' for e in overview['edges'])
    assert c['portal_concept_pairs']==len({(e[0],e[1]) for e in actual})
    passed('every_portal_concept_aggregate_matches_full_paths',portal_concept_pairs=c['portal_concept_pairs'],basis_edges=len(actual))

    def get(path,params=None):
        url='http://127.0.0.1:8766'+path+('?' + urlencode(params) if params else '')
        with urlopen(url,timeout=60) as r:return json.load(r)
    params={'portal':'kosis','concept':'measure:unemployment-rate','basis':'documented_field'}
    first=get('/api/concepts/graph/paths',params)
    assert first['total']>24
    ids=[]
    for page in range(1,first['pages']+1):
        data=first if page==1 else get('/api/concepts/graph/paths',{**params,'page':page})
        assert len(data['results'])<=24 and data['snapshot_at']==overview['generated_at']
        for item in data['results']:
            assert item['portal_id']=='kosis' and 'measure:unemployment-rate' in item['concept_ids'] and item['kind']=='documented_field'
            assert item['record']['id']==item['record_id']
            ids.append(item['id'])
    assert len(set(ids))==len(ids)==first['total']
    detail=get('/api/concepts/graph/item',{'id':ids[0]})
    assert detail['human_approved'] is False and detail['receipt']['status']=='fetched' and detail['receipt']['sha256']
    assert get('/api/concepts/graph/overview')==overview
    passed('http_paging_reaches_all_matching_items_and_provenance',portal='kosis',concept='measure:unemployment-rate',paths=len(ids),pages=first['pages'])

    pending=next(p for p in portals.values() if not p['catalog_records'])
    assert get('/api/concepts/graph/paths',{'portal':pending['portal_id'],'mode':'all'})['total']==0
    unmapped=get('/api/concepts/graph/paths',{'mode':'all','q':'감염'})
    assert unmapped['total'] and any(not x['concept_ids'] for x in unmapped['results'])
    for term in ['%',"' OR 1=1 --"]:
        data=get('/api/concepts/graph/paths',{'mode':'all','q':term})
        assert all(term in (x['label'] or '') or term in (x['name_en'] or '') for x in data['results'])
    for params in [{'page':0},{'basis':'not-valid'},{'portal':'not-a-portal'},{'concept':'not-a-concept'}]:
        try:
            get('/api/concepts/graph/paths',params)
            raise AssertionError('Invalid filter was accepted')
        except HTTPError as e:assert e.code==400
    passed('unmapped_sources_pending_portals_and_query_boundaries',unmapped_query='감염',unmapped_query_total=unmapped['total'])
    db.close()
    report={'generated_at':now(),'graph_snapshot_at':overview['generated_at'],'status':'passed','checks':checks,
        'scope':'Graph storage and source references, complete lexical match set, aggregation and HTTP; not semantic or statistical approval.',
        'elapsed_seconds':round(time.monotonic()-started,2)}
    dump(HERE/'concepts/graph-validation.json',report)
    print('ALL_PASSED',len(checks),'groups',report['elapsed_seconds'],'seconds',flush=True)


if __name__=='__main__':main()
