"""Collect MAFRA's public FILE/OPENAPI/LINK catalogs and displayed definitions."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import ordered_pages,run_queue
from urllib.parse import urlencode,urljoin
import argparse,math,re

BASE='https://data.mafra.go.kr'
KINDS={'OPENAPI':('Openapi','openapiSearch'),'FILE':('File','fileSearch'),'LINK':('Link','linkSearch')}

def documentation_url(source):
    path='/privatedata/indexPrivateDataDetail.do' if source.get('se')=='PRIVATE' else '/opendata/data/indexOpenDataDetail.do'
    return BASE+path+'?'+urlencode({'data_id':source['data_id']})

def enrich_catalog(items):
    for item in items:
        source=item['source_catalog_record'];item['url']=documentation_url(source)
        item['source_listing_classification']=source.get('se')
        item['producer_ownership_not_inferred_from_portal_membership']=True
        item['external_reference_url']=source.get('exchn_data_url')
        item['listing_classification_note']='PRIVATE is the source search category for linked marketplace products; it is not inferred as access permission, a license, or government ownership.'
    return items

def catalog_page(kind,page,sort='updt_dt'):
    if sort not in ('updt_dt','rdcnt'):raise ValueError('sort_not_observed_in_public_UI')
    route,array=KINDS[kind];eid=f'mafra-{kind.lower()}-all-page-{page}' if sort=='updt_dt' else f'mafra-{kind.lower()}-rdcnt-page-{page}'
    # The public '전체' checkbox has value '*'; [] incorrectly selects no agencies.
    params={'search_param':'','insttListToStr':'["*"]','clnmListToStr':'["*"]','gteListToStr':'','lteListToStr':'',
        'sort':sort,'category':kind,'cur_page':str(page)}
    body,receipt=fetch(eid,BASE+'/opendata/data/get'+route+'ConditionSearch.do',form=params)
    if not body:raise ValueError('catalog_fetch_unresolved:'+eid)
    data=json.loads(body);items=data.get(array);grid=data.get('grid') or {};total=int(data[kind.lower()+'_cnt'])
    if not isinstance(items,list) or grid.get('page_str')!=f'{page}/{math.ceil(total/15)}' or grid.get('total_cnt')!=total:raise ValueError('catalog_page_identity_or_count_mismatch:'+eid)
    records=[]
    for pos,hit in enumerate(items):
        item=hit['_source'];key=hit['_id'];data_id=item.get('data_id')
        if not data_id or item.get('category')!=kind or key!=kind+'-'+data_id:raise ValueError('catalog_source_id_mismatch:'+eid)
        pid=item.get('provd_instt_id')
        records.append(row('mafra',key,item.get('data_nm'),documentation_url(item),eid,
            kind=kind,provider_id='mafra:org:'+pid if pid else None,provider_name=item.get('instt_nm'),
            locator=f'{array}[{pos}]._source',source_search_document_id=key,source_data_id=data_id,
            source_parent_dataset_id=item.get('dataset_id'),source_catalog_record=item,
            source_title_variant=item.get('korean_nm'),catalog_scope='public FILE, OPENAPI and LINK search tabs',
            identity_note='Source data_id registrations are kept separately from parent dataset_id and other portals.'))
    return enrich_catalog(records),total,{k:data.get(k) for k in ('file_cnt','openapi_cnt','link_cnt','stdword_cnt','bbs_cnt')}

def catalog():
    dest=HERE/'inventory/mafra-catalog.json';reportpath=HERE/'mafra-catalog-report.json'
    if dest.exists() and reportpath.exists() and read(reportpath).get('snapshot_pagination_complete'):
        report=read(reportpath);items=read(dest)
        if report.get('catalog_parser_version',1)<2:
            items=enrich_catalog(items);store_catalog('mafra',items);dump(dest,items)
            report.update(catalog_parser_version=2,source_listing_classification_counts={kind:sum(x['source_listing_classification']==kind for x in items) for kind in ('PUBLIC','PRIVATE')})
            dump(reportpath,report)
        return items
    records={};reports={};errors=[];stop=ROOT/'.local/domestic-catalog/mafra.stop'
    def checkpoint():
        store_catalog('mafra',list(records.values()));dump(dest,list(records.values()))
        complete=len(reports)==len(KINDS) and all(x['complete'] for x in reports.values()) and not errors
        report={'generated_at':now(),'scope':'공개 통합검색 FILE·OPENAPI·LINK 목록; 표준용어·게시물은 별도 범위',
            'categories':reports,'catalog_records':len(records),'snapshot_pagination_complete':complete,
            'issues':errors,'all_portal_catalogs_complete':False,'all_columns_complete':False,
            'navigation_evidence_id':'mafra-catalog-page','unfiltered_checkbox_value':'*','catalog_parser_version':2,
            'source_listing_classification_counts':{kind:sum(x.get('source_listing_classification')==kind for x in records.values()) for kind in ('PUBLIC','PRIVATE')},
            'remaining':'source standard dictionaries, source file headers and linked providers, API operation variants and manuals'}
        dump(reportpath,report)
        dump(HERE/'mafra-collection-report.json',{'phase':'catalog_pagination','scope':'mafra',
            'target_count':sum(x['pages_expected'] for x in reports.values()),'processed':sum(x['pages_received'] for x in reports.values()),
            'generated_at':now(),'status_counts':{'catalog_records':len(records)},'queue_exhausted':False,'all_columns_complete':False,'pid':os.getpid()})
    for kind in KINDS:
        first,total,counts=catalog_page(kind,1);pages=math.ceil(total/15);seen=set()
        r={'reported_total':total,'reported_totals':[total],'pages_expected':pages,'pages_received':0,'received_rows':0,'unique_ids':0,
            'duplicate_observations':[],'complete':False,'other_tab_counts_as_reported':counts};reports[kind]=r
        def absorb(page,rows,count):
            if count not in r['reported_totals']:r['reported_totals'].append(count)
            r['pages_received']+=1;r['received_rows']+=len(rows)
            for item in rows:
                if item['id'] in seen:r['duplicate_observations'].append({'id':item['id'],'page':page})
                seen.add(item['id']);records[item['id']]=item
            r['unique_ids']=len(seen)
            r['complete']=r['pages_received']==pages and len(r['reported_totals'])==1 and r['received_rows']==len(seen)==total
        absorb(1,first,total);checkpoint()
        def get(page):
            try:rows,count,_=catalog_page(kind,page);return page,rows,count,None
            except (ValueError,KeyError,TypeError) as exc:return page,[],None,str(exc)
        for page,rows,count,error in ordered_pages(get,range(2,pages+1),stop,2):
            if error:errors.append({'kind':kind,'page':page,'error':error})
            else:absorb(page,rows,count)
            if r['pages_received']%5==0:checkpoint()
        if not stop.exists() and r['pages_received']==pages and len(seen)<total and len(r['reported_totals'])==1:
            # A second sort exposed by the same public UI can recover unstable
            # equal-date boundaries. Preserve both passes instead of hiding duplicates.
            r['primary_pass_unique_ids']=len(seen)
            alt={'sort':'rdcnt','pages_expected':pages,'pages_received':0,'received_rows':0,'unique_ids':0,'reported_totals':[], 'duplicate_observations':[]}
            r['alternate_pass']=alt;alt_seen=set()
            def alternate(page):
                try:rows,count,_=catalog_page(kind,page,'rdcnt');return page,rows,count,None
                except (ValueError,KeyError,TypeError) as exc:return page,[],None,str(exc)
            for page,rows,count,error in ordered_pages(alternate,range(1,pages+1),stop,2):
                if error:errors.append({'kind':kind,'sort':'rdcnt','page':page,'error':error});continue
                alt['pages_received']+=1;alt['received_rows']+=len(rows)
                if count not in alt['reported_totals']:alt['reported_totals'].append(count)
                for item in rows:
                    if item['id'] in alt_seen:alt['duplicate_observations'].append({'id':item['id'],'page':page})
                    alt_seen.add(item['id']);seen.add(item['id']);records[item['id']]=item
                alt['unique_ids']=len(alt_seen);r['unique_ids']=len(seen)
                r['complete']=alt['pages_received']==pages and alt['reported_totals']==[total] and len(seen)==total
                if alt['pages_received']%5==0:checkpoint()
            r['reconciliation_method']='Union of two complete public UI sort traversals; source totals must agree, duplicates and original pass counts remain visible.'
        checkpoint()
        if stop.exists():break
    print('MAFRA_CATALOG',len(records),{k:v['complete'] for k,v in reports.items()},flush=True)
    return list(records.values())

def parse_detail(body,expected_id):
    soup=BeautifulSoup(body,'html.parser');identity=soup.select_one('input#data_id')
    if not identity or identity.get('value')!=expected_id:raise ValueError('detail_identity_mismatch')
    fields=[];requests=[];metadata=[];issues=[];outgoing=[];file_links=[]
    tables=soup.select('table')
    for tn,table in enumerate(tables):
        caption=table.caption.get_text(' ',strip=True) if table.caption else ''
        role_locator=None
        if not caption:
            # The public function-detail fragment labels its tabs instead of
            # repeating table captions. Require the corresponding navigation label.
            for tab_id,label in (('tab7','출력결과'),('tab5','요청변수')):
                nav=soup.select_one('a[href="#'+tab_id+'"], a.'+tab_id)
                if table.find_parent(id=tab_id) and nav and label in nav.get_text(' ',strip=True):
                    caption=label;role_locator='#'+tab_id+' with matching labeled navigation anchor';break
        for rn,tr in enumerate(table.select('tbody tr')):
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]
            locator=f'table[{tn}].tbody.tr[{rn}]'
            if caption=='출력결과':
                if len(cells)==1 and '존재하지 않습니다' in cells[0]:continue
                if len(cells)!=2 or not cells[0]:issues.append({'locator':locator,'issue':'unexpected_output_row','cells':cells});continue
                fields.append({'name_en':cells[0],'name':cells[1] or cells[0],'description':cells[1],
                    'datatype':None,'unit':None,'role':'output_column','locator':locator,'source_cells':cells,'table_index':tn,'row_index':rn,
                    'table_role_locator':role_locator})
            elif caption=='요청변수' and len(cells)==4:
                requests.append({'name':cells[0],'requirement_as_reported':cells[1],'sample_as_reported':cells[2],'description':cells[3],
                    'locator':locator,'source_cells':cells})
            elif caption=='상세내용':
                metadata.append({'locator':locator,'source_cells':cells})
                for a in tr.select('a[href]'):
                    url=urljoin(BASE,a['href'])
                    if url.startswith(('http://','https://')):outgoing.append({'url':url,'label':a.get_text(' ',strip=True),'locator':locator,'relation':'referencesExternalPage'})
                for a in tr.select('a[onclick]'):
                    match=re.fullmatch(r"goUrl\('[^']*','(https?://[^']+)'\)",a['onclick'])
                    if match:outgoing.append({'url':match[1],'label':a.get_text(' ',strip=True),'locator':locator+' a@onclick goUrl URL argument','relation':'referencesExternalPage'})
    for a in soup.select('a[href]'):
        if any(x in a.get_text(' ',strip=True).lower() for x in ('.csv','.xlsx','.xls','.zip','.pdf')):
            file_links.append({'label':a.get_text(' ',strip=True),'href_as_reported':a['href'],'onclick_as_reported':a.get('onclick'),
                'status':'link_observed_file_not_downloaded'})
    return {'fields':fields,'request_parameters':requests,'dataset_metadata_rows':metadata,'outgoing_links':outgoing,
        'file_link_candidates':file_links,'issues':issues,'embedded_sample_values_not_promoted_to_schema':True}

def collect_one(item):
    key=item['dataset_key'];eid='mafra-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    result={'portal_id':'mafra','dataset_key':key,'dataset_kind':item['kind'],'source_url':item['url'],'evidence_id':eid,
        'additional_evidence_ids':[item['evidence_id']],'fields':[],'status':'fetch_unresolved',
        'human_approved':False,'raw_values_checked':False,'collected_at':now(),'parser_version':1,'api_observation_requests_executed':False}
    body,receipt=fetch(eid,item['url'])
    if body:
        try:
            result.update(parse_detail(body,item['source_data_id']))
            result['status']='column_definition_observed' if result['fields'] and not result['issues'] else ('column_definition_observed_partial' if result['fields'] else 'public_metadata_observed_schema_pending')
        except (ValueError,KeyError,TypeError) as exc:result.update(status='parse_unresolved',error=str(exc))
    dump(path,result);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--catalog-only',action='store_true');ap.add_argument('--limit',type=int);args=ap.parse_args()
    items=catalog()
    if args.catalog_only:return
    run_queue('mafra',items[:args.limit] if args.limit else items,collect_one,2,bool(args.limit))

if __name__=='__main__':main()
