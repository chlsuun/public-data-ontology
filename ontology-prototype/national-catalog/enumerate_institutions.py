"""Build source-scoped institution review queues, not a claim of national completeness."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ALIO_URL = 'https://alio.go.kr/organ/findOrganApbaList.json'


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def alio_roster():
    rows, pages, total, page_no = {}, [], None, 1
    while True:
        request_body = {'apbaNa': '', 'pageNo': page_no}
        req = Request(ALIO_URL, data=json.dumps(request_body).encode('utf-8'), method='POST',
                      headers={'Content-Type':'application/json',
                               'Referer':'https://alio.go.kr/guide/publicAgencyList.do'})
        with urlopen(req, timeout=15) as response:
            raw = response.read()
        obj = json.loads(raw)
        if obj.get('status') != 'success':
            raise RuntimeError('ALIO did not return success')
        block = obj['data']['organList']
        page = block['page']
        if page_no == 1:
            print('ALIO pagination: '+json.dumps(page, ensure_ascii=False), flush=True)
        found_total = int(page['totalCount'])
        if total is not None and total != found_total:
            raise RuntimeError('ALIO total changed during collection; rerun required')
        total = found_total
        old_count = len(rows)
        for row in block['result']:
            # Store institutional information only; omit individual staff and executive fields.
            rows[row['apbaId']] = {key:row.get(key) for key in
                ('apbaId','apbaNa','parnApbaId','parnApbaNa','typeNa','jidtNa','homepage','addrCd')}
        pages.append({'page':page_no,'request':request_body,'sha256':sha256(raw).hexdigest(),
                      'rows':len(block['result']),'reported_total':total})
        print(f'ALIO page {page_no}: {len(rows)}/{total}', flush=True)
        if len(rows) >= total:
            if len(rows) != total:
                raise RuntimeError('Unique row count differs from total')
            break
        if not block['result'] or len(rows) == old_count or page_no >= 150:
            raise RuntimeError('ALIO pagination ended before reaching total')
        page_no += 1
        time.sleep(0.2)
    result = {'source_url':'https://alio.go.kr/guide/publicAgencyList.do',
              'endpoint':ALIO_URL,'method':'POST (public read-only listing)',
              'retrieved_at':datetime.now(timezone.utc).isoformat(),
              'source_roster_complete':True,'national_institution_roster_complete':False,
              'reported_total':total,'pages':pages,'rows':list(rows.values())}
    (ROOT / 'alio-roster.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def main():
    directories = {r['id']:r for r in read_json('directory-observations.json')}
    alio = alio_roster()
    institutions = []
    groups = {'jrsdOrgAstCd1':'중앙기관 선택항목','jrsdOrgAstCd2':'광역·교육청 선택항목',
              'jrsdOrgAstCd4':'헌법기관 선택항목'}
    for row in directories['directory-gov24']['select_options']:
        if row['select'] not in groups or row['value'] in ('', 'ALL'):
            continue
        institutions.append({'id':'gov24-'+row['value'],'name':row['text'],
            'category':groups[row['select']],'source_identifier':row['value'],
            'source':'directory-gov24','homepage':None,'parent_name':None,
            'data_service_review_status':'not_reviewed',
            'note':'공식 디렉터리 선택항목; 행정표준기관코드 또는 법적 기관 총수로 해석하지 않음'})
    local = directories['directory-local']['links']
    start = next(i for i,r in enumerate(local) if r['label']=='서울특별시' and 'seoul.go.kr' in r['url'])
    end = next(i for i,r in enumerate(local[start:],start) if r['label']=='서귀포시' and 'seogwipo.go.kr' in r['url'])
    region_names = {r['text'] for r in directories['directory-gov24']['select_options']
                    if r['select']=='jrsdOrgAstCd2' and r['value'].startswith('0201')}
    parent, seen = None, set()
    for row in local[start:end+1]:
        if row['url'] in seen:
            continue
        seen.add(row['url'])
        if row['label'] in region_names:
            parent, category = row['label'], '광역 누리집'
        elif parent:
            category = '행정시 누리집' if row['label'] in ('제주시','서귀포시') else '기초 누리집'
        else:
            raise RuntimeError('Local directory parsing lost region context')
        institutions.append({'id':'local-'+sha256(row['url'].encode()).hexdigest()[:12],
            'name':row['label'],'category':category,'source_identifier':None,
            'source':'directory-local','homepage':row['url'],'parent_name':parent,
            'data_service_review_status':'not_reviewed',
            'note':'행정안전부 누리집 목록 항목; 해당 기관의 데이터 제공처 조사는 별도'})
    for row in alio['rows']:
        institutions.append({'id':'alio-'+row['apbaId'],'name':row['apbaNa'],
            'category':'ALIO '+(row['typeNa'] or '미분류'),'source_identifier':row['apbaId'],
            'source':'alio-roster','homepage':row['homepage'],
            'parent_name':row['parnApbaNa'],'supervising_ministry':row['jidtNa'],
            'data_service_review_status':'not_reviewed',
            'note':'ALIO의 현재 운영기관 목록 항목; 기관의 개별 데이터 포털 조사와 구분'})
    result = {'created_at':datetime.now(timezone.utc).isoformat(),
        'national_census_complete':False,'unit':'출처별 조사 항목 (기관 간 중복 미통합)',
        'source_counts':{source:sum(r['source']==source for r in institutions)
                         for source in ('directory-gov24','directory-local','alio-roster')},
        'gaps':['대학교 개별 기관 목록 미확보','지방공공기관 전체 목록 미확보',
                '중앙기관 소속기관 전체 목록 미확보','출처 사이 중복 기관·조직변경 대응 미검증',
                '기관별 데이터 제공처 전수조사 미완료'],
        'institutions':institutions}
    (ROOT / 'institution-review-queue.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['source_counts'],ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
