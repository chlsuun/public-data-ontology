"""Add source-namespaced catalog rows without replacing other portals' work."""
from common import *
import sqlite3

KEYS=['id','portal_id','dataset_key','title','provider_id','provider_name','kind','url',
    'evidence_id','locator','output_raw','request_raw','schema_status']

def store_catalog(portal,rows):
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3',timeout=60)
    db.execute('PRAGMA foreign_keys=ON')
    dest=HERE/'inventory'/(portal+'-catalog-records.jsonl.gz');temp=dest.with_suffix('.gz.tmp')
    # Preserve earlier registrations that disappear from a later listing as historical observations.
    combined={r[0]:json.loads(r[1]) for r in db.execute('SELECT id,metadata_json FROM records WHERE portal_id=?',(portal,))}
    combined.update({r['id']:r for r in rows})
    with gzip.open(temp,'wt',encoding='utf-8') as out:
        for row in combined.values():
            assert row['portal_id']==portal
            text=json.dumps(row,ensure_ascii=False,separators=(',',':'))
            db.execute('INSERT INTO records VALUES('+','.join('?' for _ in range(14))+') ON CONFLICT(id) DO UPDATE SET '+
                ','.join(k+'=excluded.'+k for k in KEYS[1:]+['metadata_json']),[row.get(k) for k in KEYS]+[text])
            out.write(text+'\n')
    db.commit();db.close();temp.replace(dest)

def row(portal,key,title,url,evidence,kind='public_catalog_entry',provider_id=None,provider_name=None,**metadata):
    return {'id':portal+'-'+key,'portal_id':portal,'dataset_key':key,'title':title,
        'provider_id':provider_id,'provider_name':provider_name,'kind':kind,'url':url,
        'evidence_id':evidence,'locator':'source registration id='+key,'output_raw':None,
        'request_raw':None,'schema_status':'separate_definition_check',**metadata}
