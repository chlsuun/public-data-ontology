"""Collect a bounded set of public metadata and documentation pages. No data rows."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('page_parser', ROOT.parent/'national-catalog/research_fetch.py')
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
SOURCES = [
 ('kosis-migration','https://kosis.kr/serviceInfo/newContrainDataDetail.do?boardIdx=1976003&boardOrgId=101'),
 ('oecd-unemployment','https://www.oecd.org/en/data/indicators/youth-unemployment-rate.html'),
 ('oecd-housing','https://www.oecd.org/en/data/indicators/housing-prices.html'),
 ('oecd-neet','https://www.oecd.org/en/data/indicators/youth-not-in-employment-education-or-training-neet.html'),
 ('wb-unemployment','https://api.worldbank.org/v2/indicator/SL.UEM.1524.ZS?format=json'),
 ('wb-employment','https://api.worldbank.org/v2/indicator/SL.EMP.1524.SP.ZS?format=json'),
 ('openai-models','https://developers.openai.com/api/docs/models'),
 ('openai-retention','https://developers.openai.com/api/docs/guides/your-data'),
 ('aws-fargate','https://aws.amazon.com/fargate/pricing/'),
 ('aws-rds','https://aws.amazon.com/rds/pricing/'),
]

def collect(item):
    sid,url=item
    result={'id':sid,'url':url,'retrieved_at':datetime.now(timezone.utc).isoformat(),'scope':'metadata_or_documentation_only'}
    try:
        with urlopen(Request(url,headers={'User-Agent':'PublicDataOntologyResearch/0.3'}),timeout=20) as response:
            raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError('Response exceeds metadata byte limit')
            result.update(http_status=response.status,final_url=response.url,sha256=sha256(raw).hexdigest())
        text=raw.decode('utf-8','replace')
        if sid.startswith('wb-'):
            value=json.loads(text)
            if not isinstance(value,list) or not isinstance(value[1],list) or 'sourceNote' not in value[1][0]:
                raise ValueError('Expected indicator metadata, not time-series data')
            result.update(status='metadata_observed',metadata=value[1],title=value[1][0]['name'])
        else:
            page=parser.Page(result['final_url']);page.feed(text)
            content=parser.clean(' '.join(page.parts))
            if sid.startswith('oecd-'):
                start=content.find('Definition')
                if start>=0:content=content[start:start+5000]
            elif sid=='kosis-migration':
                start=content.find('[통계명]')
                if start>=0:content=content[start:start+6000]
            result.update(status='page_observed',title=parser.clean(' '.join(page.title_parts)),text=content[:30000])
            result['relevant_links']=[x for x in page.links if 'data-explorer.oecd.org' in x['url'] or 'api.worldbank.org' in x['url']]
            if sid=='kosis-migration':
                result['tables']=[{'org_id':a,'table_id':b,'title':c} for a,b,c in re.findall(r"generator_link\('([^']+)','([^']+)','[^']*',\s*'([^']+)'",text)]
    except Exception as error:
        result.update(status='unresolved',error=str(error)[:300])
    return result

if __name__=='__main__':
    output=ROOT/'source-observations.json'
    if output.exists():raise SystemExit('Snapshot exists; use a new version for a new research run.')
    with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(collect,SOURCES))
    output.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{'id':r['id'],'status':r['status'],'title':r.get('title')} for r in rows],ensure_ascii=False,indent=2))
