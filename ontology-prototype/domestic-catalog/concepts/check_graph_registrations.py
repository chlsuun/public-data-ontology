"""Verify every registration is reachable even when no source item was extracted."""
import sys,json,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import HERE,read,dump,now
from graph_api import DB_PATH
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError

def get(route,**params):
    with urlopen('http://127.0.0.1:8766/api/concepts/graph/'+route+'?'+urlencode(params),timeout=30) as r:
        return json.load(r)

def main():
    db=sqlite3.connect(DB_PATH.as_uri()+'?mode=ro',uri=True)
    all_records=get('registrations')
    expected=db.execute('SELECT count(*) FROM records').fetchone()[0]
    assert all_records['total']==expected and all_records['records_with_no_items_included'] is True
    # Busan has a collected catalog and no matches to the current concept draft.
    first=get('registrations',portal='busan')
    last=get('registrations',portal='busan',page=first['pages'])
    assert first['total']==db.execute("SELECT count(*) FROM records WHERE portal_id='busan'").fetchone()[0]
    assert first['total']>24 and last['results']
    sample=None
    for r in first['results']+last['results']:
        assert r['portal_id']=='busan'
        assert r['source_items']==db.execute('SELECT count(*) FROM items WHERE record_id=?',(r['id'],)).fetchone()[0]
        if r['source_items']==0:sample=r
    assert sample is not None
    assert get('paths',record=sample['id'],mode='all')['total']==0
    sourced=db.execute("SELECT record_id,count(*) FROM items WHERE portal_id='kosis' GROUP BY record_id LIMIT 1").fetchone()
    rows=get('paths',record=sourced[0],mode='all')
    assert rows['total']==sourced[1] and all(x['record_id']==sourced[0] for x in rows['results'])
    for kwargs in [{'page':0},{'portal':'unknown-portal'}]:
        try:get('registrations',**kwargs);raise AssertionError('Expected invalid filter rejection')
        except HTTPError as e:assert e.code==400
    for q in ["' OR 1=1 --",'%']:
        response=get('registrations',q=q)
        assert all(q in r['title'] for r in response['results'])
    db.close()
    result={'generated_at':now(),'status':'passed','all_registrations_reachable':expected,
        'no_concept_match_portal_checked':'busan','busan_registration_count':first['total'],
        'no_source_item_registration_checked':sample['id'],'registration_specific_item_filter_checked':True,
        'invalid_filters_and_literal_queries_checked':True}
    dump(HERE/'concepts/graph-registration-check.json',result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
