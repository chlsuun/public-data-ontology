"""Validate the concept snapshot against stored source metadata, exports and HTTP.

This checks provenance and representation, never approves semantic equivalence.
The live catalog is opened read-only; captured source responses are not refetched.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import HERE, ROOT, read, dump, now
from build import record_terms, build_review_queue
from collections import Counter
from hashlib import sha256
from itertools import zip_longest
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
import gzip
import json
import sqlite3
import time

OUT = Path(__file__).resolve().parent


def main():
    started = time.monotonic()
    model = read(OUT / 'concept-model.json')
    checks = []

    def passed(name, **facts):
        checks.append({'name': name, 'status': 'passed', **facts})
        print('PASS', name, json.dumps(facts, ensure_ascii=False), flush=True)

    concepts = {c['id']: c for c in model['concepts']}
    mappings = {m['id']: m for m in model['mappings']}
    receipts = {e['id']: e for e in model['evidence']}
    assert len(concepts) == len(model['concepts']) == model['counts']['project_concepts']
    assert len(mappings) == len(model['mappings']) == model['counts']['mapping_examples']
    assert len(receipts) == len(model['evidence'])
    assert len({r['id'] for r in model['relationships']}) == len(model['relationships'])
    assert Counter(c['kind'] for c in concepts.values()) == model['counts']['concepts_by_kind']
    for c in concepts.values():
        assert c['kind'] in model['facets'] and c['working_definition'] and c['scope_checks']
        assert c['human_approved'] is False and c['status'] == 'project_draft'
        assert all(concepts[t]['kind'] == 'Topic' for t in c['topics'])
        assert c['displayed_evidence_examples'] == sum(m['concept_id'] == c['id'] for m in mappings.values())
    for r in model['relationships']:
        assert r['source'] in concepts and r['target'] in concepts
        assert r['human_approved'] is False and r['predicate'] in ('inTopic', 'distinguishFrom')
        if r['predicate'] == 'inTopic':
            assert concepts[r['target']]['kind'] == 'Topic'
    assert model['counts']['human_approved_concept_mappings'] == 0
    assert model['counts']['statistical_associations_verified'] == 0
    assert model['concept_system_complete'] is False
    passed('concept_identity_roles_and_proposal_boundaries', concepts=len(concepts), relationships=len(model['relationships']))

    db = sqlite3.connect((ROOT / '.local/domestic-catalog/catalog.sqlite3').as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA cache_size=-4096')
    db.execute('BEGIN')
    source_counts = Counter()
    unavailable_locations = 0
    definition_cache = {}
    for m in mappings.values():
        c = concepts[m['concept_id']]
        e = m['evidence']
        assert m['status'] == 'candidate_pending_human_review' and m['human_approved'] is False
        assert m['match_is_not_semantic_equivalence'] is True
        assert m['required_checks'] == c['scope_checks']
        assert e['evidence_id'] in receipts
        r = db.execute('SELECT * FROM records WHERE id=?', (e['record_id'],)).fetchone()
        assert r is not None and r['portal_id'] == e['portal_id'] and r['title'] == e['record_title']
        assert r['url'] == e['record_url']
        source_counts[e['kind']] += 1
        if e['kind'] == 'catalog_label':
            assert (e['match_channel'], e['source_label'], e['metadata_locator']) in record_terms(json.loads(r['metadata_json']))
            assert r['evidence_id'] == e['evidence_id'] and r['locator'] == e['catalog_locator']
            assert e['source_label'] in c['aliases'] and c['kind'] != 'Unit'
        else:
            assert e['kind'] == 'documented_field'
            f = db.execute('SELECT * FROM documented_fields WHERE record_id=? AND evidence_id=? AND ordinal=?',
                           (e['record_id'], e['evidence_id'], e['ordinal'])).fetchone()
            assert f is not None
            for stored, exported in [('name','field_name'),('name_en','field_name_en'),('description','description_as_reported'),('datatype','datatype_as_reported'),('unit','unit_as_reported')]:
                assert f[stored] == e[exported], (m['id'], stored)
            definition = json.loads(f['definition_json'])
            raw = definition['raw_definition']
            assert definition['source_url'] == e['source_url']
            assert raw.get('locator') == e['source_locator']
            assert e['source_locator_unavailable'] == (not bool(raw.get('locator')))
            unavailable_locations += int(e['source_locator_unavailable'])
            assert e['stored_field_identity'] == {k:e[k] for k in ('record_id','evidence_id','ordinal')}
            assert e['definition_document']
            path = e['definition_document']
            if path not in definition_cache:
                definition_cache[path] = read(HERE / 'definitions' / path)
            position = e['extracted_definition_locator'].split('/')
            assert position[:2] == ['', 'fields'] and len(position) == 3
            assert definition_cache[path]['fields'][int(position[2])] == raw
            if 'code_context' in e:
                context = e['code_context']
                assert context['declared_code_count'] == raw['declared_code_count']
                assert context['display_sample'] == raw.get('observed_codes', [])[:10]
                assert context['code_list_complete'] == raw.get('code_list_complete')
            if c['kind'] == 'Unit':
                assert e['unit_as_reported'] in c['aliases'] and m['proposed_predicate'] == 'hasUnit'
    for j in model['join_review_candidates']:
        assert j['human_approved'] is False and j['actual_join_executed'] is False
        assert j['statistical_association_asserted'] is False and j['required_checks']
        for key in ('source_record_id', 'target_record_id'):
            assert db.execute('SELECT 1 FROM records WHERE id=?', (j[key],)).fetchone()
    db.rollback()
    db.close()
    passed('every_mapping_matches_stored_catalog_or_formal_definition', **dict(source_counts), raw_location_not_recorded=unavailable_locations)

    checked_bytes = 0
    for i, e in enumerate(receipts.values(), 1):
        original = read(HERE / 'evidence' / (e['id'] + '.json'))
        assert e['status'] == 'fetched'
        assert all(original.get(k) == v for k, v in e.items())
        path = (HERE / e['raw_file']).resolve()
        assert path.is_relative_to(HERE.resolve())
        digest = sha256()
        size = 0
        with gzip.open(path, 'rb') as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
        assert digest.hexdigest() == e['sha256'], e['id']
        if 'bytes' in original:
            assert size == original['bytes'], e['id']
        checked_bytes += size
        if i % 50 == 0:
            print('SOURCE_RECEIPTS', i, '/', len(receipts), flush=True)
    passed('all_selected_receipts_and_raw_sha256', receipts=len(receipts), uncompressed_bytes=checked_bytes)

    terms = sqlite3.connect((OUT / 'source-terms.sqlite3').as_uri() + '?mode=ro', uri=True)
    terms.execute('PRAGMA cache_size=-4096')
    terms.execute('PRAGMA temp_store=FILE')
    assert terms.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    count = 0
    roles = Counter()
    with gzip.open(OUT / 'source-terms.jsonl.gz', 'rt', encoding='utf-8') as stream:
        sql = 'SELECT id,label,role,portal_id,occurrences,data_json FROM terms ORDER BY occurrences DESC,id'
        for line, row in zip_longest(stream, terms.execute(sql)):
            assert line is not None and row is not None
            t = json.loads(line)
            assert t == json.loads(row[5])
            assert (t['id'],t['label_as_reported'],t['role'],t['portal_id'],t['occurrences_in_index']) == row[:5]
            assert t['status'] == 'source_label_bucket_not_validated_concept' and 0 < len(t['examples']) <= 2
            roles[t['role']] += 1
            count += 1
            if count % 100000 == 0:
                print('TERM_EXPORT', count, flush=True)
    assert count == model['counts']['source_label_buckets']
    terms.close()
    passed('complete_term_export_roundtrip_and_database_integrity', term_buckets=count, roles=dict(roles))

    queue = read(OUT / 'review-queue.json')
    assert {x['id'] for x in queue['items']} == set(mappings)
    assert len(queue['items']) == len(mappings) and queue['decisions_not_automatically_applied_to_model'] is True
    for item in queue['items']:
        m = mappings[item['id']]
        assert item['concept_id'] == m['concept_id'] and item['record_id'] == m['evidence']['record_id']
    passed('review_queue_identity_and_manual_decision_boundary', review_items=len(queue['items']))

    sample = next(iter(mappings.values()))
    fixture = build_review_queue([sample], {})
    fixture['items'][0].update(reviewer='test-only-reviewer', decision='revise', rationale='test-only-scope-check')
    before = json.dumps(fixture, sort_keys=True)
    absent = build_review_queue([], fixture)
    absent_again = build_review_queue([], absent)
    restored = build_review_queue([sample], absent_again)
    assert len(absent_again['previous_items_outside_current_sample']) == 1
    assert restored['items'][0] == fixture['items'][0]
    assert not restored['previous_items_outside_current_sample']
    assert json.dumps(fixture, sort_keys=True) == before
    assert sample['human_approved'] is False
    passed('review_survives_sampling_removal_and_return_without_auto_approval')

    from rdflib import Graph, Namespace
    from rdflib.namespace import RDF, SKOS, OWL
    graph = Graph().parse(OUT / 'concept-model.ttl', format='turtle')
    p = Namespace('urn:public-data-ontology:')
    assert len(set(graph.subjects(RDF.type, SKOS.Concept))) == len(concepts)
    assert len(set(graph.subjects(RDF.type, p.ConceptMappingProposal))) == len(mappings)
    assert not list(graph.triples((None, OWL.sameAs, None)))
    assert not list(graph.triples((None, SKOS.exactMatch, None)))
    passed('rdf_parse_and_unapproved_equivalence_not_asserted', triples=len(graph))

    def get(path):
        with urlopen('http://127.0.0.1:8766' + path, timeout=30) as response:
            return response.status, response.read()

    status, html = get('/concepts')
    assert status == 200 and '__CONCEPT_DATA__' not in html.decode('utf-8')
    assert json.loads(get('/concepts/files/model')[1]) == model
    assert json.loads(get('/concepts/files/review')[1]) == queue
    for query, role in [('감염',''),('실업률','documented_field_label'),('%',''),("' OR 1=1 --",'')]:
        data = json.loads(get('/api/concepts/terms?' + urlencode({'q':query,'role':role}))[1])
        assert data['are_validated_concepts'] is False and len(data['results']) <= 80
        assert all(query in t['label_as_reported'] and (not role or t['role'] == role) for t in data['results'])
        if query == '실업률':
            assert data['total'] > 0
    for path, expected in [('/api/concepts/terms?role=invalid',400),('/concepts/files/../../common.py',404)]:
        try:
            get(path)
            raise AssertionError('Expected HTTP error for ' + path)
        except HTTPError as error:
            assert error.code == expected
    main_model = read(HERE / 'model.json')
    assert main_model['concept_layer']['model'] == 'concepts/concept-model.json'
    assert (HERE / main_model['concept_layer']['explorer']).is_file()
    passed('http_search_downloads_literal_queries_and_model_reference')

    report = {'generated_at':now(), 'concept_snapshot_at':model['generated_at'], 'status':'passed',
              'scope':'Current concept snapshot, selected source evidence and complete term export; no human semantic approval or statistical validation.',
              'checks':checks, 'elapsed_seconds':round(time.monotonic()-started,2)}
    dump(OUT / 'validation-report.json', report)
    print('ALL_PASSED', len(checks), 'checks', report['elapsed_seconds'], 'seconds', flush=True)


if __name__ == '__main__':
    main()
