"""Collect Seoul's publicly documented API outputs and displayed sheet fields."""
from common import *
from queue_runner import run_queue
from urllib.parse import urlencode
import re,sqlite3,argparse

BASE='https://data.seoul.go.kr'

def parse_api(data):
    soup=BeautifulSoup(data,'html.parser');fields=[];requests=[]
    for table_no,table in enumerate(soup.find_all('table')):
        caption=table.find('caption');label=caption.get_text(' ',strip=True) if caption else ''
        if '출력값' not in label and '요청인자' not in label:continue
        for pos,tr in enumerate(table.select('tbody tr')):
            cells=[td.get_text(' ',strip=True) for td in tr.find_all('td',recursive=False)]
            if '출력값' in label and len(cells)==3:
                fields.append({'name':cells[2],'name_en':cells[1],'description':cells[2],
                    'role':'response_envelope' if cells[0]=='공통' else 'output_column',
                    'datatype':None,'unit':None,'locator':f'table[{table_no}].tbody.tr[{pos}]'})
            elif '요청인자' in label and len(cells)==4:
                requests.append(dict(zip(['name','type_as_reported','description','value_description'],cells)))
    return fields,requests

def parse_sheet(data):
    html=data.decode('utf-8-sig');fields=[]
    match=re.search(r'var\s+getColGroup\s*=\s*function\s*\(\)\s*\{\s*return\s*(\[.*?\]);',html,re.S)
    if not match:return fields
    # Read only literal strings from the public grid declaration; never evaluate JS.
    for pos,item in enumerate(re.finditer(r'\{\s*key\s*:\s*("(?:\\.|[^"\\])*")\s*,\s*label\s*:\s*("(?:\\.|[^"\\])*")',match[1])):
        fields.append({'name_en':json.loads(item[1]),'name':json.loads(item[2]),
            'role':'displayed_sheet_column','datatype':None,'unit':None,'description':None,
            'locator':f'getColGroup()[{pos}]'})
    if len(fields)!=len(re.findall(r'\bkey\s*:',match[1])):
        raise ValueError('grid_column_parser_coverage_mismatch')
    return fields

def collect_one(row):
    key,url=row;eid='seoul-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    data,receipt=fetch(eid+'-page',url.replace('http://','https://',1))
    result={'portal_id':'seoul','dataset_key':key,'source_url':url,'evidence_id':eid+'-page',
        'fields':[],'status':'fetch_unresolved','raw_values_checked':False,'human_approved':False,
        'collected_at':now(),'service_checks':[]}
    if data:
        soup=BeautifulSoup(data,'html.parser')
        services=[]
        for button in soup.select('[onclick]'):
            m=re.search(r"dataSetView\('([^']+)'\s*,\s*'([^']+)'\s*,\s*(\d+)\)",button.get('onclick',''))
            if m and tuple(m.groups()) not in services:services.append(tuple(m.groups()))
        result['advertised_services']=services
        # One API view provides richer definitions; sheet fallback preserves visible field names.
        api=[x for x in services if x[1]=='A'];sheet=[x for x in services if x[1]=='S' and x[2]=='1']
        for inf,kind,service_kind in api+sheet:
            endpoint='/dataList/openApiView.do' if kind=='A' else '/dataList/sheetView.do'
            source=BASE+endpoint+'?'+urlencode({'infId':inf,'srvType':kind})
            se=eid+'-'+kind
            body,rc=fetch(se,source,form={'infId':inf,'srvType':kind,'serviceKind':service_kind},referer=url)
            observed=[];request_fields=[];error=None
            if body:
                try:
                    if kind=='A':observed,request_fields=parse_api(body)
                    else:observed=parse_sheet(body)
                except (ValueError,TypeError) as exc:error=str(exc)[:200]
            result['service_checks'].append({'service':kind,'evidence_id':se,'fields':len(observed),
                'status':'definition_observed' if observed else ('parse_unresolved' if error else 'definition_unresolved'), 'error':error})
            if observed:
                result.update(fields=observed,request_parameters=request_fields,source_url=source,evidence_id=se,
                    status='column_definition_observed' if kind=='A' else 'displayed_column_definition_observed')
                break
        if not result['fields']:
            result['status']='public_schema_unresolved' if services else 'service_declaration_unresolved'
    dump(path,result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);ap.add_argument('--workers',type=int,default=2);args=ap.parse_args()
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3')
    rows=db.execute("SELECT dataset_key,min(url) FROM records WHERE portal_id='seoul' GROUP BY dataset_key ORDER BY dataset_key").fetchall();db.close()
    run_queue('seoul',rows[:args.limit] if args.limit else rows,collect_one,min(3,max(1,args.workers)),bool(args.limit))

if __name__=='__main__':main()
