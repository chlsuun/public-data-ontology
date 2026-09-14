"""Export the entire fixed source graph for GitHub Pages, in bounded gzip shards.

Reads the local graph SQLite snapshot only. Does not collect data, approve
semantic relationships, or require a database/API server for the shared site.
"""
import gzip
import hashlib
import json
import sqlite3
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'ontology-prototype/domestic-catalog/concepts'
OUT = ROOT / 'docs/graph-data'
CHUNK = 5000
SECRET_QUERY_KEYS = {'servicekey', 'apikey', 'api_key', 'authkey', 'access_token', 'token', 'key', 'authorization', 'password', 'signature', 'x-amz-signature', 'x-amz-credential', 'x-amz-security-token'}
redactions = 0


def clean(value):
    global redactions
    if isinstance(value, str) and value.startswith(('https://', 'http://')):
        u = urlsplit(value)
        pairs = parse_qsl(u.query, keep_blank_values=True)
        if any(k.lower() in SECRET_QUERY_KEYS and v for k, v in pairs):
            redactions += 1
            value = urlunsplit((u.scheme, u.netloc, u.path,
                urlencode([(k, '[REDACTED]' if k.lower() in SECRET_QUERY_KEYS and v else v) for k, v in pairs]), u.fragment))
    return value


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf8')


def shard(name, rows):
    raw = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode('utf8')
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    path = OUT / name
    path.write_bytes(packed)
    return {'file': name, 'rows': len(rows), 'bytes': len(packed), 'sha256': hashlib.sha256(packed).hexdigest()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect((ROOT / '.local/domestic-catalog/knowledge-graph.sqlite3').as_uri()+'?mode=ro', uri=True)
    db.execute('PRAGMA cache_size=-8192')
    db.execute('BEGIN')
    overview = json.loads(db.execute("SELECT value FROM meta WHERE key='overview'").fetchone()[0])
    item_columns = [r[1] for r in db.execute('PRAGMA table_info(items)')] + ['concept_ids']
    record_columns = [r[1] for r in db.execute('PRAGMA table_info(records)')] + ['source_items']
    manifest = {'format': 1, 'snapshot_at': overview['generated_at'], 'counts': overview['counts'],
        'item_columns': item_columns, 'record_columns': record_columns, 'items': [], 'records': [],
        'receipt_scope': '원문 파일은 로컬 보관. 공유본은 원문 URL·항목 위치·근거 ID 및 공개 조회 영수증을 포함한다.'}
    sql = '''SELECT i.*, (SELECT json_group_array(concept_id) FROM mappings m WHERE m.item_id=i.id)
             FROM items i ORDER BY i.id'''
    cursor = db.execute(sql)
    count = mapped = mappings = 0
    evidence_ids = set()
    while batch := cursor.fetchmany(CHUNK):
        rows, stats = [], {}
        for row in batch:
            row = [clean(v) for v in row]
            row[-1] = json.loads(row[-1])
            rows.append(row)
            evidence_ids.add(row[7])
            key = (row[2], row[3])
            st = stats.setdefault(key, [0, 0, Counter(), row[1], row[1]])
            st[0] += 1
            st[1] += bool(row[-1])
            st[2].update(row[-1])
            st[3] = min(st[3], row[1]); st[4] = max(st[4], row[1])
            mapped += bool(row[-1]); mappings += len(row[-1])
        part = shard(f'items-{len(manifest["items"]):04d}.json.gz', rows)
        part.update(first=rows[0][0], last=rows[-1][0], stats=[[*k, a, b, dict(c), lo, hi] for k, (a,b,c,lo,hi) in stats.items()])
        manifest['items'].append(part)
        count += len(rows)
        if len(manifest['items']) % 100 == 0: print('EXPORTED_ITEMS', count, flush=True)
    assert count == overview['counts']['source_items']
    assert mapped == overview['counts']['matched_source_items']
    assert mappings == overview['counts']['lexical_mapping_occurrences']
    cursor = db.execute('SELECT r.*, (SELECT count(*) FROM items i WHERE i.record_id=r.id) FROM records r ORDER BY r.id')
    record_count = 0
    while batch := cursor.fetchmany(CHUNK):
        rows = [[clean(v) for v in row] for row in batch]
        part = shard(f'records-{len(manifest["records"]):04d}.json.gz', rows)
        part.update(first=rows[0][0], last=rows[-1][0], portals=dict(Counter(r[1] for r in rows)))
        manifest['records'].append(part)
        record_count += len(rows)
    assert record_count == overview['counts']['catalog_records']
    # Receipts only expose the fields used by the source inspector, never raw
    # responses, local paths, cookies or HTTP authorization headers.
    receipts = {}
    evidence = (SOURCE.parent/'evidence').resolve()
    def load_receipt(eid):
        path = (evidence/(eid+'.json')).resolve()
        if not path.is_relative_to(evidence):
            raise ValueError('Receipt path outside the evidence directory')
        try:
            return eid, json.loads(path.read_bytes())
        except FileNotFoundError:
            return eid, None
    receipt_ids = sorted(e for e in evidence_ids if e)
    # Bound both open files and queued work. These are local immutable metadata
    # reads; no new source requests are issued during publication.
    with ThreadPoolExecutor(max_workers=8) as pool:
        for start in range(0, len(receipt_ids), 512):
            for eid, obj in pool.map(load_receipt, receipt_ids[start:start+512]):
                if obj is not None:
                    receipts[eid] = {k:clean(obj.get(k)) for k in ('id','requested_url','retrieved_at','status','sha256')}
            if start // 10000 != (start + 512) // 10000:
                print('EXPORTED_RECEIPTS', min(start+512,len(receipt_ids)), '/', len(receipt_ids), flush=True)
    receipt_groups = {}
    for eid, receipt in receipts.items():
        prefix = hashlib.sha256(eid.encode('utf8')).hexdigest()[:2]
        receipt_groups.setdefault(prefix, {})[eid] = receipt
    manifest['receipts'] = {prefix: shard('receipts-'+prefix+'.json.gz', values) for prefix, values in sorted(receipt_groups.items())}
    manifest['redacted_url_parameters'] = redactions
    write_json(OUT/'overview.json', overview)
    write_json(OUT/'manifest.json', manifest)
    total_bytes = sum(x['bytes'] for group in ('items','records') for x in manifest[group]) + sum(x['bytes'] for x in manifest['receipts'].values())
    report = {'passed': True, 'snapshot_at': manifest['snapshot_at'], 'source_items': count, 'catalog_records': record_count,
        'matched_source_items': mapped, 'mapping_occurrences': mappings, 'item_shards': len(manifest['items']),
        'record_shards': len(manifest['records']), 'compressed_bytes': total_bytes, 'receipt_count': len(receipts),
        'redacted_url_parameters': redactions, 'sampling': False,
        'referenced_receipts':len(receipt_ids), 'missing_receipts':len(receipt_ids)-len(receipts)}
    write_json(OUT/'export-report.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    db.close()


if __name__ == '__main__':
    main()
