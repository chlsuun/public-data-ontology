"""Primary culture-market column dictionaries reached through public KSPO references.

This is a referred subset, not the culture market's complete catalog.
"""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from urllib.parse import urlsplit,parse_qs
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

PORTAL='bigdata-culture';BASE='https://www.bigdata-culture.kr'
HEAD=['순서','컬럼영문명','컬럼한글명','데이터타입','길이','PK여부','NOT NULL여부','데이터 상품명']

def targets():
    entries={}
    for p in (HERE/'definitions').glob('kspo-schema-explorer-*.json'):
        d=read(p)
        for link in d['outgoing_links']:
            u=urlsplit(link['url'])
            if u.hostname!='www.bigdata-culture.kr' or u.path!='/bigdata/user/data_market/detail.do':continue
            key=parse_qs(u.query)['id'][0]
            item=entries.setdefault(key,{'key':key,'url':link['url'],'references':[]})
            item['references'].append({'portal_id':'kspo','dataset_key':d['dataset_key'],'evidence_id':d['evidence_id'],'locator':link['locator']})
    return list(entries.values())

def page(item):
    key=item['key'];eid='kspo-primary-culture-7' if key=='2fc01bbd-f19a-44c7-a8bd-fe131fcd5330' else 'culture-market-detail-'+key
    b,r=fetch(eid,item['url'])
    if b is None:return {'target':item,'status':'fetch_unresolved','evidence_id':eid}
    try:
        s=BeautifulSoup(b,'html.parser');ident=s.select_one('input[name="id"]');title=s.select_one('.tit_w p.tit span')
        if ident is None or ident.get('value')!=key or title is None or not title.get_text(' ',strip=True):raise ValueError('primary_detail_identity_or_title_unresolved')
        agency=s.select_one('a.data_srch_sub_title');agencyid=parse_qs(urlsplit(agency['href']).query).get('id',[None])[0] if agency else None
        script=next((x.get_text() for x in s.select('script') if 'fnLoad_columnSheet' in x.get_text()),'')
        if '/bigdata/data_market/columninfo.do' not in script or '"preview"' not in script:raise ValueError('public_column_dictionary_renderer_missing')
        if not any(t.caption and t.caption.get_text(' ',strip=True)=='컬럼정의서 시트' for t in s.select('table')):raise ValueError('dictionary_table_missing')
        record=row(PORTAL,key,title.get_text(' ',strip=True),item['url'],eid,kind='public_dataset_detail_from_referred_subset',
            provider_id=PORTAL+':org:'+agencyid if agencyid else None,provider_name=agency.get_text(' ',strip=True) if agency else None,
            locator='.tit_w p.tit span',source_referrals=item['references'],public_catalog_scope='Only primary pages linked by the KSPO referred map; not the complete market catalog')
        return {'record':record,'status':'primary_detail_observed','evidence_id':eid}
    except (ValueError,KeyError,TypeError) as exc:return {'target':item,'status':'parse_unresolved','evidence_id':eid,'error':str(exc)}

def columns(item):
    key=item['dataset_key'];dest=HERE/'definitions'/('bigdata-culture-schema-'+key+'.json')
    if dest.exists():return read(dest)
    eid='culture-market-columninfo-'+key
    d={'portal_id':PORTAL,'dataset_key':key,'source_url':item['url'],'evidence_id':eid,'collected_at':now(),
        'parent_html_evidence_id':item['evidence_id'],'fields':[],'status':'fetch_unresolved','issues':[],
        'human_approved':False,'raw_values_checked':False,'all_columns_complete':False,'observation_api_called':False,
        'original_files_downloaded':False,'source_qa_reference':'culture-market-reference-source-qa.json'}
    try:
        b,r=fetch(eid,BASE+'/bigdata/data_market/columninfo.do',form={'type':'preview','id':key},accept='application/json')
        if b:
            obj=json.loads(b);d['source_status_as_reported']=obj.get('status')
            if obj.get('status')!='OK':d['status']='source_dictionary_unresolved'
            else:
                rows=obj['data'];d['source_dictionary_header']=rows[0] if rows else []
                if not rows or rows[0]!=HEAD:raise ValueError('unreviewed_column_dictionary_header')
                for n,v in enumerate(rows[1:],1):
                    if len(v)!=8 or not v[1]:raise ValueError('column_dictionary_row_shape_changed')
                    d['fields'].append({'name_en':v[1],'name':v[2] or v[1],'description':v[2],'datatype':v[3] or None,'unit':None,
                        'source_order_as_reported':v[0],'length_as_reported':v[4],'primary_key_flag_as_reported':v[5],
                        'not_null_flag_as_reported':v[6],'product_name_as_reported':v[7],'source_cells':v,'locator':f'data[{n}]',
                        'role':'file_column_definition','all_file_versions_share_definition_verified':False})
                orders=[v[0] for v in rows[1:]]
                if orders and all(str(x).isdigit() for x in orders):
                    integers=[int(x) for x in orders]
                    if integers!=list(range(1,len(integers)+1)):d['issues'].append({'issue':'source_order_not_contiguous_from_one','values_as_reported':orders,'missing_fields_not_invented':True})
                d['status']='file_column_definition_observed' if d['fields'] else 'source_dictionary_empty'
    except (ValueError,KeyError,TypeError) as exc:d.update(status='parse_unresolved',error=str(exc),fields=[])
    dump(dest,d);return d

def main():
    todo=targets()
    with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(page,todo))
    records=[x['record'] for x in outcomes if 'record' in x]
    store_catalog(PORTAL,records);dump(HERE/'inventory/bigdata-culture-catalog.json',records)
    dump(HERE/'culture-market-reference-catalog-report.json',{'generated_at':now(),'discovered_reference_targets':len(todo),'primary_details_observed':len(records),
        'outcomes':outcomes,'all_portal_catalogs_complete':False,'all_columns_complete':False,'scope':'Public primary pages linked from active KSPO map registrations only'})
    run_queue('culture-market-references',records,columns,2)
    docs=[read(HERE/'definitions'/('bigdata-culture-schema-'+r['dataset_key']+'.json')) for r in records]
    dump(HERE/'culture-market-reference-source-qa.json',{'generated_at':now(),'portal_id':PORTAL,'records':len(records),
        'documented_field_occurrences':sum(len(d['fields']) for d in docs),'status_counts':dict(Counter(d['status'] for d in docs)),
        'issues':[{'dataset_key':d['dataset_key'],**issue} for d in docs for issue in d['issues']],
        'raw_values_checked':False,'quality_scores_assigned':False,'all_columns_complete':False,
        'remaining_scope':['Full culture market catalog and other institutions','Unresolved dictionary formats','Distribution/file version applicability']})

if __name__=='__main__':main()
