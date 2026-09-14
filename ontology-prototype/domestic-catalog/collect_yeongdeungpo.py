"""Observe Yeongdeungpo's own catalog and public output documentation."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
import re
BASE='https://data.ydp.go.kr'

def catalog_page(page):
    eid=f'yeongdeungpo-catalog-name-{page}'
    url=BASE+'/openinf/dataset/datasetlist.jsp?'+urlencode({'pageNo':page,'sortCol':'Z1.INF_NM ASC'})
    b,r=fetch(eid,url)
    if not b:raise ValueError('catalog_fetch_unresolved:'+eid)
    s=BeautifulSoup(b,'html.parser');total=s.select_one('.total')
    counts=re.search(r'([\d,]+)건.*?(\d+)\s*/\s*(\d+)\s*Page',total.get_text(' ',strip=True) if total else '')
    if not counts or int(counts[2])!=page:raise ValueError('catalog_page_or_count_unresolved')
    items=[]
    for tr in s.select('table[summary="Dataset 목록"] tbody tr'):
        services=[];key=None
        for button in tr.select('[onclick]'):
            match=re.search(r"dataSetView\('([^']+)'\s*,\s*'([^']+)'\)",button['onclick'])
            if match:
                if key is not None and key!=match[1]:raise ValueError('multiple_dataset_ids_in_catalog_row')
                key=match[1]
                if match[2] not in services:services.append(match[2])
        name=tr.select_one('td[title]');cells=tr.find_all('td',recursive=False)
        if not key or not name:continue
        title=name['title'];service='A' if 'A' in services else services[0]
        view={'A':'openapiview.jsp','S':'sheetview.jsp','F':'fileview.jsp','L':'linkview.jsp','C':'chartview.jsp','M':'mapview.jsp'}[service]
        item=row('yeongdeungpo',key,title,BASE+'/openinf/'+view+'?'+urlencode({'infId':key,'selSrvType':service}),eid,
            advertised_services=services,selected_service=service,
            source_row_text=[x.get_text(' ',strip=True) for x in cells])
        items.append(item)
    return items,int(counts[1].replace(',','')),int(counts[3])

def parse(data):
    s=BeautifulSoup(data,'html.parser');fields=[];parameters=[];meta={}
    for ti,table in enumerate(s.find_all('table')):
        cap=table.find('caption');name=cap.get_text(' ',strip=True) if cap else ''
        if name=='출력 값 리스트':
            for pos,tr in enumerate(table.select('tbody tr')):
                cells=[x.get_text(' ',strip=True) for x in tr.find_all('td',recursive=False)]
                if len(cells)==3:
                    fields.append({'name':cells[2],'name_en':cells[1],'description':cells[2],
                        'datatype':None,'unit':None,'role':'output_column','locator':f'table[{ti}].tbody.tr[{pos}]'})
        elif name=='요청인자리스트':
            for tr in table.select('tbody tr'):
                cells=[x.get_text(' ',strip=True) for x in tr.find_all('td',recursive=False)]
                if len(cells)==4:parameters.append(dict(zip(['name','type_as_reported','description','values_description'],cells)))
        elif name=='메타정보 리스트':
            allowed={'분류체계','원본시스템','태그','저작권자명','제공기관','제공부서','제3저작권자','원본형태','DATA등록일','적재주기','최종수정일'}
            for th in table.select('th'):
                label=th.get_text(' ',strip=True);td=th.find_next_sibling('td')
                if label in allowed and td:meta[label]=td.get_text(' ',strip=True)
    return fields,parameters,meta

def collect_one(item):
    key=item['dataset_key'];eid='yeongdeungpo-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    b,r=fetch(eid,item['url'],form={'infId':key,'selSrvType':item['selected_service']})
    fields,parameters,meta=parse(b) if b else ([],[],{})
    result={'portal_id':'yeongdeungpo','dataset_key':key,'evidence_id':eid,'source_url':item['url'],
        'fields':fields,'request_parameters':parameters,'dataset_metadata':meta,
        'status':'column_definition_observed' if fields else ('non_api_definition_pending' if b else 'fetch_unresolved'),
        'human_approved':False,'raw_values_checked':False,'collected_at':now()}
    dump(path,result);return result

def main():
    first,total,pages=catalog_page(1);all_rows=list(first);totals={total};pagecounts={pages}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for rows,t,p in pool.map(catalog_page,range(2,pages+1)):
            all_rows.extend(rows);totals.add(t);pagecounts.add(p)
    items={x['dataset_key']:x for x in all_rows}
    report={'scope':'영등포구 열린 데이터 광장 Dataset 목록','generated_at':now(),'reported_total':total,
        'received_rows':len(all_rows),'unique_dataset_ids':len(items),'pages_received':pages,
        'snapshot_pagination_complete':len(totals)==len(pagecounts)==1 and len(items)==len(all_rows)==total,
        'api_entries':sum('A' in x['advertised_services'] for x in items.values()),'all_columns_complete':False}
    dump(HERE/'yeongdeungpo-catalog-report.json',report);dump(HERE/'inventory/yeongdeungpo-catalog.json',list(items.values()))
    store_catalog('yeongdeungpo',items.values());print('CATALOG',report,flush=True)
    run_queue('yeongdeungpo',items.values(),collect_one,2)
    for item in items.values():
        d=read(HERE/'definitions'/('yeongdeungpo-schema-'+item['dataset_key']+'.json'))
        if d.get('dataset_metadata',{}).get('제공기관'):
            item.update(provider_name=d['dataset_metadata']['제공기관'],provider_evidence_id=d['evidence_id'])
    store_catalog('yeongdeungpo',items.values())

if __name__=='__main__':main()
