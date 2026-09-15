"""Collect FISIS public UI catalogs, statistical item metadata and glossaries.

Only requests explicitly used by the public selector/metadata window are allowed.
No keyed Open API, statistics value query, report-data or Excel request is made.
API documentation operations are collected separately from statistical reports.
"""
from common import *
from catalog_storage import row,store_catalog
from collections import Counter
import argparse,re

BASE='https://fisis.fss.or.kr'
PAGE=BASE+'/page/fsv101.jsp'
SCRIPT_EID='fisis-stats-ui-101-20260914'
VERSION=2
ALLOWED={'fsv101_getLrgDiv','fsv101_getSmlDiv','fsv101_getReportList','fsv102_getRowList','fsv102_metadata'}


def public_get(endpoint,params,eid,post=False):
    if endpoint not in ALLOWED:raise ValueError('Not an allowed public metadata request')
    url=BASE+'/fss/wa/'+endpoint+'.do'
    if params and not post:url+='?'+urlencode(params)
    data,r=fetch(eid,url,form=params if post else None,referer=PAGE)
    return data,r,url


def dataset(data,expected):
    obj=json.loads(data)
    if obj.get('err_cd')!=0:raise ValueError('Source returned unsuccessful err_cd: '+str(obj.get('err_cd')))
    arr=obj.get('dataset')
    if not isinstance(arr,list):raise ValueError('Missing dataset array')
    ds=next((d for d in arr if d.get('id')==expected),None)
    if ds is None or not isinstance(ds.get('rows'),list):raise ValueError('Missing '+expected)
    if any(not isinstance(x,dict) for x in ds['rows']):raise ValueError('Unexpected row type')
    return obj,ds,arr.index(ds)


def catalog():
    script,receipt=fetch(SCRIPT_EID,BASE+'/js/stats-ui-101.js?v=202606221702',referer=PAGE)
    if script is None:raise ValueError('Public selector script unavailable')
    text=script.decode('utf8')
    if not all('/fss/wa/'+endpoint+'.do' in text for endpoint in ALLOWED):raise ValueError('Unrecognized public request paths')
    body,r,url=public_get('fsv101_getLrgDiv',{},'fisis-sectors-20260914',post=True)
    if body is None:raise ValueError('Sector selector unavailable; no catalog replaced')
    obj,ds,di=dataset(body,'ds_partDiv');sectors=ds['rows']
    records={};occurrences=[];failures=[];requests=[];groups=[];started=now()
    def progress(done):
        dump(HERE/'fisis-collection-report.json',{'generated_at':now(),'started_at':started,'phase':'catalog_pagination',
            'scope':'fisis-public-sector-and-category-catalog','target_count':len(sectors),'processed':done,'remaining':len(sectors)-done,
            'status_counts':{'catalog_records_observed':len(records),'catalog_requests':len(requests),'unresolved_requests':len(failures)},
            'queue_exhausted':False,'all_columns_complete':False,'pid':os.getpid()})
    progress(0)
    for sn,sector in enumerate(sectors):
        code=sector['GROUP_LRG_DIV'];eid='fisis-categories-'+code+'-20260914'
        b,r,url=public_get('fsv101_getSmlDiv',{'GROUP_LRG_DIV':code},eid)
        try:
            if b is None:raise ValueError('fetch_unresolved')
            obj,ds,di=dataset(b,'ds_class')
        except (ValueError,KeyError) as exc:
            failures.append({'phase':'category','evidence_id':eid,'issue':str(exc)});continue
        seen=set()
        for cn,category in enumerate(ds['rows']):
            assert category['GROUP_LRG_DIV']==code
            params={'GROUP_LRG_DIV':code,'GROUP_SML_DIV':category['GROUP_SML_DIV']}
            if str(category['LVL'])!='0':params['GROUP_MID_DIV']=category['GROUP_DIV']
            reqkey=tuple(params.items())
            groups.append({'sector':sector,'category':category,'evidence_id':eid,'locator':f'/dataset/{di}/rows/{cn}','request':params})
            if reqkey in seen:continue
            seen.add(reqkey)
            ceid='fisis-catalog-'+'-'.join(params.values())+'-20260914'
            b,rr,cu=public_get('fsv101_getReportList',params,ceid)
            req={'evidence_id':ceid,'url':cu,'params':params}
            requests.append(req)
            try:
                if b is None:raise ValueError('fetch_unresolved')
                co,cd,cdi=dataset(b,'ds_report');req['row_count']=len(cd['rows']);req['status']='catalog_observed'
                for rn,source in enumerate(cd['rows']):
                    key=source['FORM_NO']
                    if not key or not source['FULL_FORM_NAME']:raise ValueError('Missing report identity/name')
                    occurrence={'source':source,'evidence_id':ceid,'source_url':cu,'locator':f'/dataset/{cdi}/rows/{rn}',
                        'category_evidence_id':eid,'category_locator':f'/dataset/{di}/rows/{cn}','request':params}
                    occurrences.append(occurrence)
                    if key not in records:
                        records[key]=row('fisis',key,source['FULL_FORM_NAME'],PAGE,ceid,kind='financial_statistics_table',
                            provider_name='금융감독원',provider_name_role='public system publisher; reporting financial companies are separate',
                            locator=occurrence['locator'],catalog_source_rows=[],
                            classification_status='source classification paths preserved; no cross-portal semantic approval')
                    records[key]['catalog_source_rows'].append(occurrence)
            except (ValueError,KeyError) as exc:
                req['status']='catalog_unresolved';failures.append({'phase':'catalog','evidence_id':ceid,'issue':str(exc)})
        progress(sn+1)
    values=list(records.values());store_catalog('fisis',values)
    dump(HERE/'inventory/fisis-catalog.json',values)
    dump(HERE/'inventory/fisis-catalog-paths.json',{'sectors':sectors,'category_paths':groups,'catalog_requests':requests,'occurrences':occurrences})
    versions={}
    for item in occurrences:
        source=item['source'];form=source['FORM_NO'];st=source['ST_DAY'][:6];ed=source['ED_DAY'][:6]
        if not all(re.fullmatch(r'\d{6}',v) for v in (st,ed)):
            failures.append({'phase':'period','source':item,'issue':'Invalid stated coverage period'});continue
        key=(form,st,ed)
        versions.setdefault(key,{'form_no':form,'start_month':st,'end_month':ed,'source_rows':[]})['source_rows'].append(item)
    queue=list(versions.values());dump(HERE/'inventory/fisis-definition-queue.json',queue)
    report={'generated_at':now(),'scope':'All sectors and category selectors returned by the captured public single-table UI',
        'sectors':len(sectors),'category_paths':len(groups),'catalog_requests':len(requests),'catalog_row_occurrences':len(occurrences),
        'unique_report_ids':len(records),'report_period_targets':len(queue),'failures':failures,
        'selector_traversal_exhausted':not failures,'official_total_available':False,'all_portal_catalogs_complete':False,
        'script_evidence_id':SCRIPT_EID,'request_paths_allowlisted':sorted(ALLOWED),
        'identity_note':'FORM_NO and stated periods retained; public UI report IDs are not equated with Open API listNo codes.'}
    dump(HERE/'fisis-catalog-report.json',report)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return queue


def parse_items(body):
    obj=json.loads(body)
    if obj.get('err_cd')!=0:raise ValueError('Unsuccessful item response')
    fields=[];issues=[];cols=rows=0
    for di,ds in enumerate(obj['dataset']):
        if ds['id'] not in ('ds_rowItem','ds_colItem'):
            issues.append({'issue':'unknown_item_dataset','id':ds.get('id')});continue
        for rn,value in enumerate(ds['rows']):
            is_row=ds['id']=='ds_rowItem';code=value.get('ROW_CD' if is_row else 'DB_COL_NM');name=value.get('ROW_NM' if is_row else 'COL_NM')
            if not code or not name:
                issues.append({'issue':'item_without_code_or_name','locator':f'/dataset/{di}/rows/{rn}','raw_source_row':value});continue
            fields.append({'name':name,'name_en':code,'description':None,'datatype':None,
                'source_data_type_code':value.get('DATA_TYPE'),'datatype_code_status':'not_mapped_to_storage_datatype',
                'source_calculation_unit_code':value.get('CAL_UNIT'),
                'unit':None,'role':'statistical_row_item' if is_row else 'statistical_column_item',
                'locator':f'/dataset/{di}/rows/{rn}','raw_source_row':value,'source_dataset':ds['id'],
                'code_namespace':'FORM_NO plus item axis; cross-report identity not asserted',
                'source_indentation_preserved':True,'parent_inferred':False})
            rows+=int(is_row);cols+=int(not is_row)
    count=obj.get('values',{}).get('columnCount')
    if count is not None and count!=cols:issues.append({'issue':'column_count_exceeds_observed_column_definitions','reported':count,'observed':cols})
    return {'fields':fields,'item_response_datasets':obj['dataset'],'reported_values':obj.get('values'),
        'item_issues':issues,'row_item_count':rows,'column_item_count':cols,
        'status':'statistical_items_observed_columns_partial' if fields and issues else 'statistical_items_observed' if fields else 'item_definition_not_observed'}


def parse_metadata(body):
    soup=BeautifulSoup(body,'html.parser');tables=[];terms=[]
    for tn,t in enumerate(soup.select('table')):
        caption=t.caption.get_text(' ',strip=True) if t.caption else ''
        physical=[tr for tr in t.select('tr') if tr.find_parent('table') is t];rows=[]
        for rn,tr in enumerate(physical):
            cs=tr.find_all(['th','td'],recursive=False)
            cells=[{'text':c.get_text(' ',strip=True),'tag':c.name,'colspan':c.get('colspan','1'),'rowspan':c.get('rowspan','1'),
                'locator':f'table[{tn}].tr[{rn}].cell[{cn}]'} for cn,c in enumerate(cs)]
            rr={'locator':f'table[{tn}].tr[{rn}]','cells':cells};rows.append(rr)
            if caption=='용어해설' and len(cells)==2 and any(c['tag']=='td' for c in cells) and cells[0]['text']:
                terms.append({'term_as_reported':cells[0]['text'],'definition_as_reported':cells[1]['text'],'locator':rr['locator'],
                    'mapping_to_statistical_item':'not_approved'})
        tables.append({'table_index':tn,'caption':caption,'rows':rows})
    if not any(t['caption']=='통계개요' for t in tables):raise ValueError('Expected metadata overview not observed')
    return {'metadata_status':'metadata_document_observed','metadata_tables':tables,'glossary_terms':terms,
        'glossary_count_is_not_added_to_field_count':True}


def definitions(queue,limit=None):
    started=now();statuses=Counter();metadata_statuses=Counter();total=fields=terms=0
    def report():
        r={'generated_at':now(),'started_at':started,'scope':'fisis-public-report-period-item-definitions-and-metadata',
            'target_count':len(queue),'processed':total,'remaining':len(queue)-total,'status_counts':dict(statuses),
            'documented_field_occurrences':fields,'glossary_term_occurrences':terms,'metadata_status_counts':dict(metadata_statuses),'queue_exhausted':total==len(queue),
            'all_columns_complete':False,'pid':os.getpid()}
        dump(HERE/'fisis-collection-report.json',r);print(json.dumps(r,ensure_ascii=False),flush=True)
    report()
    for target in queue:
        if (ROOT/'.local/domestic-catalog/fisis.stop').exists() or (limit is not None and total>=limit):break
        form=target['form_no'];st=target['start_month'];ed=target['end_month'];key=form+'-'+st+'-'+ed
        path=HERE/'definitions'/('fisis-schema-'+key+'.json');old=read(path) if path.exists() else None
        if old and old.get('parser_version')==VERSION:d=old
        else:
            # Reuse the initial bounded probe for this exact published period.
            probe=form=='SDSA001V' and st=='199906' and ed=='201809'
            suffix=form if probe else key;eid='fisis-items-'+suffix+'-20260914';meid='fisis-metadata-'+suffix+'-20260914'
            params={'FORM_NO':form,'ST_MONTH':st,'ED_MONTH':ed}
            b,r,url=public_get('fsv102_getRowList',params,eid)
            d={'portal_id':'fisis','dataset_key':form,'dataset_kind':'financial_statistics_table','source_url':url,
                'evidence_id':eid,'collected_at':now(),'parser_version':VERSION,'fields':[],'status':'fetch_unresolved',
                'stated_period':params,'catalog_source_rows':target['source_rows'],'observation_values_requested':False,
                'human_approved':False,'all_columns_complete':False}
            if b:
                try:d.update(parse_items(b))
                except (ValueError,KeyError,TypeError) as exc:d.update(status='parse_unresolved',error=str(exc)[:400])
            else:d['fetch_issue']={k:r.get(k) for k in ('status','http_status','error')}
            b,r,url=public_get('fsv102_metadata',params,meid)
            d['metadata_evidence_id']=meid;d['metadata_source_url']=url
            if b:
                try:d.update(parse_metadata(b))
                except (ValueError,KeyError) as exc:d.update(metadata_status='metadata_parse_unresolved',metadata_error=str(exc)[:400])
            else:d.update(metadata_status='metadata_fetch_unresolved',metadata_error={k:r.get(k) for k in ('status','http_status','error')})
            if old:
                d['previous_parser_attempt']={'parser_version':old.get('parser_version'),'collected_at':old.get('collected_at'),
                    'status':old.get('status'),'field_count':len(old.get('fields',[])),
                    'change_reason':'Preserve DATA_TYPE as an uninterpreted source code, not a physical storage datatype. Source JS handles code 5 as a ratio indicator.'}
            dump(path,d)
        statuses[d['status']]+=1;metadata_statuses[d.get('metadata_status','metadata_status_unresolved')]+=1
        fields+=len(d['fields']);terms+=len(d.get('glossary_terms',[]));total+=1
        if total%10==0:report()
    report()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser();ap.add_argument('--catalog-only',action='store_true');ap.add_argument('--limit',type=int);a=ap.parse_args()
    queue_path=HERE/'inventory/fisis-definition-queue.json'
    queue=read(queue_path) if queue_path.exists() else catalog()
    if not a.catalog_only:definitions(queue,a.limit)
