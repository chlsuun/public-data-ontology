"""Public catalog and displayed-schema adapters for Chungnam and Jeonbuk."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import ordered_pages,run_queue
from static_js_data import literal_value
from openapi_schema import javascript_literal
from urllib.parse import urljoin,urlsplit,parse_qs,urlencode
import argparse,re,math

CONFIG={
 'chungnam':{'base':'https://alldam.chungnam.go.kr','path':'/bigdata/collect/totalSearchList.chungnam',
  'params':{'isOpen':'Y','dataGubun':'PUB','menuCd':'DOM_000000201001001000','contentsSid':'576'},'page':'pageIndex','id':'apiIdx','table':'table.list01'},
 'jeonbuk':{'base':'https://www.bigdatahub.go.kr','path':'/index.jeonbuk',
  'params':{'menuCd':'DOM_000000103007000000','pListTypeStr':'','orgCdStr':'','pCategoryCdStr':'','searchKeyword':'','srowCount':'10'},'page':'startPage','id':'pId','table':'table.list'}
}

def parse_catalog(portal,body,page,eid,url):
    cfg=CONFIG[portal];soup=BeautifulSoup(body,'html.parser');text=soup.get_text(' ',strip=True)
    hidden=soup.select_one('input[name='+cfg['page']+']')
    if hidden is None or hidden.get('value')!=str(page):raise ValueError('catalog_page_identity_mismatch')
    if portal=='chungnam':
        m=re.search(r'총\s*([\d,]+)\s*건\s*\(\s*(\d+)\s*/\s*(\d+)\s*페이지',text)
        if not m or int(m[2])!=page:raise ValueError('catalog_totals_or_current_page_missing')
        total=int(m[1].replace(',',''));last=int(m[3])
        if math.ceil(total/10)!=last:raise ValueError('catalog_total_page_count_disagrees')
    else:
        m=re.search(r'총 데이터셋\s*([\d,]+)\s*건',text)
        if not m:raise ValueError('catalog_total_missing')
        total=int(m[1].replace(',',''));last=math.ceil(total/10)
    table=soup.select_one(cfg['table'])
    if table is None:raise ValueError('catalog_table_missing')
    records=[]
    for pos,tr in enumerate(table.select('tbody tr')):
        cells=tr.find_all('td',recursive=False);values=[x.get_text(' ',strip=True) for x in cells]
        if len(cells)!=7:raise ValueError('unexpected_catalog_row_layout')
        a=tr.select_one('td.title strong a') if portal=='chungnam' else tr.select_one('td.subject a')
        if not a:raise ValueError('catalog_detail_link_missing')
        detail=urljoin(url,a['href']);params=parse_qs(urlsplit(detail).query)
        registration_key=cfg['id']
        if portal=='chungnam' and 'publicdatapk' in params:registration_key='publicdatapk'
        native_key=(params.get(registration_key) or [''])[0]
        if not re.fullmatch(r'[A-Za-z0-9_-]+',native_key) or (registration_key!='publicdatapk' and not native_key.isdigit()):raise ValueError('catalog_native_id_missing')
        key='publicdatapk-'+native_key if registration_key=='publicdatapk' else native_key
        if portal=='jeonbuk':
            if values[0]!=str(total-(page-1)*10-pos):raise ValueError('catalog_displayed_rank_mismatch')
            clone=BeautifulSoup(str(a),'html.parser').a
            for em in clone.select('em'):em.decompose()
            title=clone.get_text(' ',strip=True);provider=values[3];types=values[4];category=values[1]
        else:title=a.get_text(' ',strip=True);provider=None;types=values[1];category=values[2]
        records.append(row(portal,key,title,detail,eid,provider_name=provider,locator=cfg['table']+f' tbody tr[{pos}]',
            source_catalog_cells=values,source_page=page,source_service_types=types,source_category=category,
            source_detail_url=detail,source_registration_key=registration_key,source_native_id=native_key,
            identity_note='Native portal registration key retained in its portal namespace; numeric equality to another portal is not an identity or joinability claim.'))
    expected=min(10,max(0,total-(page-1)*10))
    if len(records)!=expected:raise ValueError('catalog_page_row_count_mismatch')
    return records,total,last

def catalog_page(portal,page):
    cfg=CONFIG[portal];eid=portal+'-catalog-page' if page==1 else f'{portal}-catalog-page-{page}'
    url=cfg['base']+cfg['path']+'?'+urlencode({**cfg['params'],cfg['page']:page})
    body,receipt=fetch(eid,url)
    if not body:raise ValueError('catalog_fetch_unresolved:'+eid)
    return parse_catalog(portal,body,page,eid,receipt['requested_url'])

def catalog(portal):
    rp=HERE/(portal+'-catalog-report.json');dest=HERE/'inventory'/(portal+'-catalog.json')
    if dest.exists() and rp.exists() and read(rp).get('snapshot_pagination_complete'):return read(dest)
    first,total,last=catalog_page(portal,1);items={};receipts=[];duplicates=[];errors=[];totals={total};received=0
    stop=ROOT/'.local/domestic-catalog'/(portal+'.stop')
    def absorb(page,rows,count):
        nonlocal received
        totals.add(count);received+=len(rows)
        receipts.append({'page':page,'rows':len(rows),'reported_total':count,'evidence_id':rows[0]['evidence_id']})
        for r in rows:
            if r['id'] in items:duplicates.append({'id':r['id'],'page':page,'earlier_page':items[r['id']]['source_page']})
            items[r['id']]=r
    def checkpoint():
        complete=len(receipts)==last and len(totals)==1 and received==len(items)==total and not duplicates and not errors
        store_catalog(portal,list(items.values()));dump(dest,list(items.values()))
        dump(rp,{'generated_at':now(),'catalog_records':len(items),'reported_total':total,'reported_totals':sorted(totals),
            'pages_expected':last,'pages_received':len(receipts),'received_rows':received,'page_receipts':receipts,
            'duplicate_observations':duplicates,'errors':errors,'snapshot_pagination_complete':complete,
            'all_portal_catalogs_complete':False,'all_columns_complete':False,'parser_version':3,
            'scope':'public dataset list; private/custom data, statistics and other portal catalog scopes remain separate'})
        dump(HERE/(portal+'-collection-report.json'),{'generated_at':now(),'phase':'catalog_pagination','scope':portal,
            'target_count':last,'processed':len(receipts),'status_counts':{'catalog_records':len(items)},'queue_exhausted':False,'all_columns_complete':False,'pid':os.getpid()})
    absorb(1,first,total);checkpoint()
    def get(page):
        try:rows,count,end=catalog_page(portal,page);return page,rows,count,None
        except (ValueError,KeyError,TypeError) as exc:return page,[],0,str(exc)
    for page,rows,count,error in ordered_pages(get,range(2,last+1),stop,2):
        if error:errors.append({'page':page,'error':error})
        else:absorb(page,rows,count)
        if page%20==0:checkpoint();print(portal,'catalog pages',page,'/',last,flush=True)
    checkpoint()
    if not read(rp)['snapshot_pagination_complete']:raise ValueError('catalog_pagination_incomplete:'+portal)
    return list(items.values())

def without_comments(code):
    """Blank JS comments, preserving literal contents and source character offsets."""
    chars=list(code);pos=0
    while pos<len(code):
        if code[pos] in ('\"',"'",'`'):
            _,pos=javascript_literal(code,pos);continue
        end=None
        if code.startswith('//',pos):
            end=code.find('\n',pos);end=len(code) if end<0 else end
        elif code.startswith('/*',pos):
            end=code.find('*/',pos+2)
            if end<0:raise ValueError('unterminated_script_comment')
            end+=2
        if end is not None:
            for i in range(pos,end):
                if chars[i] not in '\r\n':chars[i]=' '
            pos=end
        else:pos+=1
    return ''.join(chars)

def parse_chungnam_detail(body,key):
    source=body.decode('utf-8-sig');soup=BeautifulSoup(source,'html.parser')
    identities=re.findall(r"(?m)^\s*apiIdx\s*=\s*'([0-9]+)'\s*;",source)
    if identities!=[key]:raise ValueError('detail_apiIdx_identity_mismatch')
    fields=[];issues=[];grid_sections=[]
    for sn,script in enumerate(soup.select('script:not([src])')):
        code=script.string or script.get_text()
        if not ('new tui.Grid' in code and 'columns: columns' in code):continue
        try:active=without_comments(code)
        except ValueError as exc:issues.append({'script_index':sn,'error':str(exc)});continue
        initial=list(re.finditer(r'var\s+columns\s*=\s*\[\]\s*;',active))
        grids=list(re.finditer(r'(?:var\s+\w+\s*=\s*)?new\s+tui\.Grid\s*\(',active))
        if len(initial)!=1 or len(grids)!=1 or initial[0].end()>grids[0].start():issues.append({'script_index':sn,'error':'grid_column_array_scope_ambiguous'});continue
        start,stop=initial[0].end(),grids[0].start();residual=list(active[start:stop])
        matches=list(re.finditer(r'(?m)^\s*columns\.push\(\s*',active[start:stop]));grid_fields=[]
        for m in matches:
            try:
                begin=start+m.end();obj,end=literal_value(code,begin)
                suffix=re.match(r'\s*\)\s*;',active[end:])
                if not suffix:raise ValueError('grid_push_has_dynamic_suffix')
                if not isinstance(obj,dict) or not isinstance(obj.get('header'),str) or not isinstance(obj.get('name'),str):raise ValueError('grid_header_or_name_missing')
                for i in range(m.start(),end+suffix.end()-start):residual[i]=' '
                grid_fields.append({'name':obj['header'],'name_en':obj['name'],'datatype':None,'unit':None,
                    'role':'displayed_sheet_column','description':None,'script_index':sn,'start_char':begin,'end_char':end,
                    'source_literal':code[begin:end],'source_grid_definition':obj,
                    'locator':f'inline_script[{sn}].columns.push literal chars[{begin}:{end}]',
                    'scope_note':'Column explicitly configured for the displayed sample grid; not inferred from sample record keys and not a guarantee for every file version.'})
            except ValueError as exc:issues.append({'script_index':sn,'position':start+m.end(),'error':str(exc)})
        if ''.join(residual).strip():
            issues.append({'script_index':sn,'error':'nonliteral_or_conditional_grid_column_setup'});grid_fields=[]
        fields.extend(grid_fields);grid_sections.append({'script_index':sn,'explicit_column_push_count':len(matches),'parsed_columns':len(grid_fields)})
    return soup,fields,issues,grid_sections

def collect_one(portal,item):
    key=item['dataset_key'];eid=portal+'-schema-'+key;path=HERE/'definitions'/(eid+'.json')
    if path.exists() and read(path).get('parser_version',0)>=4:return read(path)
    d={'portal_id':portal,'dataset_key':key,'evidence_id':eid,'source_url':item['url'],'additional_evidence_ids':[item['evidence_id']],
        'fields':[],'outgoing_links':[],'status':'fetch_unresolved','human_approved':False,'raw_values_checked':False,'collected_at':now(),'parser_version':4}
    body,receipt=fetch(eid,item['url'])
    if body:
        try:
            if portal=='chungnam' and item['source_registration_key']=='apiIdx':soup,fields,issues,grids=parse_chungnam_detail(body,key);d.update(fields=fields,parse_issues=issues,displayed_grid_sections=grids)
            elif portal=='chungnam':
                soup=BeautifulSoup(body,'html.parser');identity=soup.select_one('input[name=publicdatapk]')
                if identity is None or identity.get('value')!=item['source_native_id']:raise ValueError('detail_publicdatapk_identity_mismatch')
                heading=soup.select_one('h4.h4BI-tit')
                if heading is None:raise ValueError('detail_title_missing')
                heading=BeautifulSoup(str(heading),'html.parser').h4
                for child in heading.select('span'):child.decompose()
                if heading.get_text(' ',strip=True)!=item['title']:raise ValueError('detail_title_mismatch')
                d['schema_followup_note']='Linked-public-data UI has file/API tabs and dynamic parameter tables. Empty templates and sample values are not schemas; operation metadata lookup remains pending.'
            else:
                soup=BeautifulSoup(body,'html.parser');headings=[h.get_text(' ',strip=True) for h in soup.select('h4:not([id])')]
                if item['title'] not in headings:raise ValueError('detail_title_mismatch')
                expected='https://www.data.go.kr/data/'+key+'/'
                if not any(a.get('href','').startswith(expected) for a in soup.select('a[href]')):raise ValueError('detail_source_reference_identity_unresolved')
            content=soup.select_one('article.s_con') if portal=='chungnam' and item['source_registration_key']=='publicdatapk' else soup.select_one('.bbs_skin')
            if content is None:raise ValueError('detail_content_scope_missing')
            d['metadata_tables']=[{'table_index':n,'caption':t.caption.get_text(' ',strip=True) if t.caption else None,
                'interpretation':'source page table retained; not promoted to output schema',
                'rows':[[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)] for tr in t.select('tr')]}
                for n,t in enumerate(soup.select('table')) if content in t.parents and not t.find_parent(id='vueCtrl') and '요청변수' not in (t.caption.get_text(' ',strip=True) if t.caption else '')]
            d['resource_versions']=[]
            for n,h in enumerate(soup.select('div#info_wrap > h4[id]')):
                following=h.find_next_sibling();table_indexes=[]
                if following and 'toggle' in following.get('class',[]):
                    table_indexes=[i for i,t in enumerate(soup.select('table')) if following in t.parents]
                d['resource_versions'].append({'source_resource_id':h['id'],'source_heading':h.get_text(' ',strip=True),
                    'locator':f'div#info_wrap > h4[id][{n}]','metadata_table_indexes':table_indexes,
                    'references':[{'url':urljoin(item['url'],a['href']),'label':a.get_text(' ',strip=True)} for a in h.select('a[href]') if urljoin(item['url'],a['href']).startswith(('https://','http://'))],
                    'schema_observed':False,'version_identity_is_source_reported':True})
            for n,a in enumerate(soup.select('a[href]')):
                if content not in a.parents:continue
                url=urljoin(item['url'],a['href'])
                if url.startswith(('http://','https://')) and (urlsplit(url).hostname!=urlsplit(item['url']).hostname or 'fileDownload' in url or 'csvDownLoad' in url):
                    d['outgoing_links'].append({'url':url,'label':a.get_text(' ',strip=True),'locator':f'a[href][{n}]@href','target_content_not_fetched':True})
            d['status']=('displayed_column_definition_observed' if d['fields'] and not d.get('parse_issues') else
                'displayed_column_definition_observed_partial' if d['fields'] else 'public_metadata_observed_schema_pending')
            d['all_file_versions_schema_complete']=False
        except (ValueError,KeyError,TypeError) as exc:d.update(status='parse_unresolved',error=str(exc))
    dump(path,d);return d

def main(portal):
    ap=argparse.ArgumentParser();ap.add_argument('--catalog-only',action='store_true');ap.add_argument('--limit',type=int);args=ap.parse_args()
    rows=catalog(portal)
    if args.catalog_only:return
    rows=sorted(rows,key=lambda r:('API' not in r['source_service_types'],r['dataset_key']))
    run_queue(portal,rows[:args.limit] if args.limit else rows,lambda r:collect_one(portal,r),2,bool(args.limit))
