"""Collect published output definitions for all acquired national standard datasets."""
from common import *
from collect_definitions import parse_data_go
from collect_data_go_api import parse_tables
from queue_runner import run_queue
import sqlite3,re

def collect_one(target):
    key,url=target;eid='data-go-std-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    previous=read(path) if path.exists() else None
    if previous and (previous.get('fields') or previous.get('parser_version',1)>=2):return previous
    data,receipt=fetch(eid,url);fields=[]
    if data:
        fields,_=parse_data_go(data)
        if not fields:fields,_=parse_tables(data,{'id':'standard_output'},eid)
        if not fields:
            soup=BeautifulSoup(data,'html.parser')
            for ti,table in enumerate(soup.find_all('table')):
                caption=table.find('caption')
                if not caption or 'Response Element' not in caption.get_text():continue
                headers=[x.get_text(' ',strip=True) for x in table.select('thead th')]
                if len(headers)!=3 or '항목명' not in headers[0] or '설명' not in headers[2]:continue
                for pos,tr in enumerate(table.select('tbody tr')):
                    cells=[x.get_text(' ',strip=True) for x in tr.find_all('td',recursive=False)]
                    if len(cells)!=3:continue
                    fields.append({'name':cells[0],'name_en':cells[0] if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',cells[0]) else None,
                        'description':cells[2],'role':'standard_output_column','datatype':None,'unit':None,
                        'source_name_header':headers[0],'locator':f'table[{ti}].tbody.tr[{pos}]',
                        'note':'원문의 국문 항목명 헤더 아래 영문 코드가 출력되기도 하므로 원문 이름과 설명을 별도 보존'})
    result={'portal_id':'data-go','dataset_key':key,'dataset_kind':'STD','evidence_id':eid,'source_url':url,
        'status':'column_definition_observed' if fields else ('definition_unresolved' if data else 'fetch_unresolved'),
        'fields':fields,'human_approved':False,'raw_values_checked':False,'collected_at':now(),'parser_version':2}
    if previous:result['previous_parser_status']=previous['status']
    dump(path,result);return result

def main():
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3')
    targets=db.execute("SELECT dataset_key,min(url) FROM records WHERE portal_id='data-go' AND kind='STD' GROUP BY dataset_key ORDER BY dataset_key").fetchall();db.close()
    run_queue('data-go-std',targets,collect_one,1)

if __name__=='__main__':main()
