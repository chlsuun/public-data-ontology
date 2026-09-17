"""Read public landing pages; store observations, never infer API availability."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import argparse
import json
from pathlib import Path
import re
import socket
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent


class Page(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.links, self.parts, self.title_parts, self.options = base, [], [], [], []
        self.anchor = None
        self.option = None
        self.select = None
        self.hidden, self.in_title = 0, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'title':
            self.in_title = True
        if tag == 'a':
            self.anchor = {'href': a.get('href', ''), 'text': []}
        if tag == 'img' and self.anchor and a.get('alt'):
            self.anchor['text'].append(a['alt'])
        if tag == 'select':
            self.select = a.get('id') or a.get('name')
        if tag == 'option':
            self.option = {'select': self.select, 'value': a.get('value', ''), 'text': []}

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag == 'title':
            self.in_title = False
        if tag == 'a' and self.anchor:
            raw = self.anchor['href']
            if raw and not raw.lower().startswith(('javascript:', 'mailto:', 'tel:', '#')):
                target = urljoin(self.base, raw)
                if urlsplit(target).scheme in ('http', 'https'):
                    self.links.append({'url': stable_url(target), 'label': clean(' '.join(self.anchor['text']))})
            self.anchor = None
        if tag == 'option' and self.option:
            self.option['text'] = clean(' '.join(self.option['text']))
            self.options.append(self.option)
            self.option = None
        if tag == 'select':
            self.select = None

    def handle_data(self, text):
        if self.hidden:
            return
        if self.in_title:
            self.title_parts.append(text)
        if self.anchor:
            self.anchor['text'].append(text)
        if self.option:
            self.option['text'].append(text)
        if text.strip():
            self.parts.append(text.strip())


def clean(text):
    return re.sub(r'\s+', ' ', text).strip()


def stable_url(url):
    return re.sub(r';jsessionid=[^/?#;]+', '', url, flags=re.I)


def fetch(item):
    result = {'id': item['id'], 'requested_url': item['url'],
              'retrieved_at': datetime.now(timezone.utc).isoformat(),
              'api_tested': False}
    try:
        req = Request(item['url'], headers={'User-Agent': 'PublicCatalogResearch/0.1 (metadata inspection)', 'Accept': 'text/html,application/xhtml+xml'})
        with urlopen(req, timeout=12) as response:
            body = response.read(2_000_001)
            result.update(final_url=stable_url(response.url), http_status=response.status,
                          media_type=response.headers.get_content_type(),
                          sha256=sha256(body).hexdigest(), truncated=len(body) > 2_000_000)
            encoding = response.headers.get_content_charset()
            if not encoding:
                match = re.search(br'charset\s*=\s*["\']?([a-zA-Z0-9_-]+)', body[:12000], re.I)
                encoding = match.group(1).decode('ascii') if match else 'utf-8'
            try:
                raw = body.decode(encoding, errors='replace')
            except LookupError:
                raw = body.decode('utf-8', errors='replace')
        page = Page(result['final_url'])
        page.feed(raw)
        text = clean(' '.join(page.parts))
        result.update(status='page_observed', title=clean(' '.join(page.title_parts)),
                      text=text[:60000], links=page.links, select_options=page.options)
    except (HTTPError, URLError, TimeoutError, socket.timeout, ValueError, OSError) as exc:
        result.update(status='fetch_unresolved', error=clean(str(exc))[:300])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    parser.add_argument('--output', default='page-observations.json')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    items = json.loads((ROOT / args.manifest).read_text(encoding='utf-8'))
    output = ROOT / args.output
    previous = json.loads(output.read_text(encoding='utf-8')) if output.exists() else []
    saved = {r['id']: r for r in previous}
    pending = [x for x in items if args.refresh or x['id'] not in saved
               or saved[x['id']].get('requested_url') != x['url']]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(fetch, pending):
            saved[row['id']] = row
            output.write_text(json.dumps(list(saved.values()), ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: row.get(k) for k in ('id','status','title','final_url','error')}, ensure_ascii=False), flush=True)
    print(f'Saved {len(saved)} public page observations to {output.name}', flush=True)


if __name__ == '__main__':
    main()
