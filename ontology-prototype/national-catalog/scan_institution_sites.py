"""One-page institutional discovery. Results are leads, not verified portals."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from research_fetch import fetch, stable_url

ROOT = Path(__file__).resolve().parent
PATTERN = re.compile(r'공공\s*데이터|데이터\s*(?:개방|포털|허브|플랫폼)|오픈\s*API|OPEN[ -]?API|통계\s*(?:정보|포털)|데이터셋',re.I)


def main():
    queue = json.loads((ROOT/'institution-review-queue.json').read_text(encoding='utf-8'))
    targets = {}
    for row in queue['institutions']:
        url = (row.get('homepage') or '').strip()
        if not url:
            continue
        assumed = not url.startswith(('https://','http://'))
        if assumed:
            url = 'https://' + url
        try:
            parts = urlsplit(url)
            if not parts.hostname or any(x in url for x in ('<','>',' ','\n')):
                continue
        except ValueError:
            continue
        key = parts.netloc.lower().removeprefix('www.') + parts.path.rstrip('/')
        targets.setdefault(key, {'id':'site-'+sha256(key.encode()).hexdigest()[:12],
                                'url':url,'institution_ids':[], 'scheme_assumed':assumed})
        targets[key]['institution_ids'].append(row['id'])
    path = ROOT/'institution-site-observations.jsonl'
    existing = {r['id']:r for line in path.read_text(encoding='utf-8').splitlines()
                if line.strip() for r in [json.loads(line)]} if path.exists() else {}
    pending = [t for t in targets.values() if t['id'] not in existing]
    print(f'Institution homepage targets: {len(targets)}; pending: {len(pending)}',flush=True)
    with path.open('a',encoding='utf-8') as log, ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch,t):t for t in pending}
        for completed, future in enumerate(as_completed(futures),1):
            t = futures[future]
            try:
                full = future.result()
            except Exception as error:
                full = {'id':t['id'],'status':'fetch_unresolved','error':str(error)[:200]}
            links = {}
            for x in full.get('links',[]):
                if PATTERN.search(x['label']):
                    url = stable_url(x['url'])
                    links[url] = {'url':url,'label':x['label'][:180],
                                  'verification':'navigation_candidate'}
            out = {k:v for k,v in full.items() if k not in ('text','links','select_options')}
            out.update(institution_ids=t['institution_ids'],scheme_assumed=t['scheme_assumed'],
                       content_chars=len(full.get('text','')),
                       candidate_data_links=list(links.values()),
                       review_status='automatic_navigation_scan_only')
            log.write(json.dumps(out,ensure_ascii=False)+'\n')
            log.flush()
            existing[out['id']] = out
            if completed % 30 == 0 or completed == len(pending):
                print(f'Scanned {len(existing)}/{len(targets)}; pages with leads: '+
                      str(sum(bool(r.get('candidate_data_links')) for r in existing.values())),flush=True)
    summary = {'targets':len(targets),'attempted':len(existing),
               'pages_with_candidates':sum(bool(r.get('candidate_data_links')) for r in existing.values()),
               'candidate_links':sum(len(r.get('candidate_data_links',[])) for r in existing.values()),
               'scope':'One public landing page per listed homepage; not a full website crawl or portal verification',
               'complete_for_manifest':len(existing)==len(targets),
               'national_census_complete':False}
    (ROOT/'institution-scan-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
