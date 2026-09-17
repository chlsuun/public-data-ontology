"""Anonymous Jeju catalog metadata, embedded parameter definitions and file versions."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import ordered_pages,run_queue
from urllib.parse import urlencode,urlsplit
import math

PARAMS={'includedKeywords':'','excludedKeywords':'','categories':'','userId':'','dataType':'','orderBy':'createAt','authYn':'false',
 'autoUpdateYn':'false','keyword':'','keywordOrTagFlag':'keyword','isPaging':'true','start':'0','pageNumber':'1','length':'10'}

def page(number):
    eid='jeju-public-catalog-page1' if number==1 else f'jeju-public-catalog-page{number}'
    raw,r=fetch(eid,'https://jejudatahub.net/api/data?'+urlencode({**PARAMS,'pageNumber':str(number),'start':str((number-1)*10)}))
    if raw is None:raise ValueError('catalog_fetch_unresolved:'+eid)
    data=json.loads(raw)
    if data.get('result')!='success' or not isinstance(data.get('data'),list):raise ValueError('catalog_result_not_success')
    total=data['recordsTotal'];filtered=data['recordsFiltered']
    if not isinstance(total,int) or filtered!=total:raise ValueError('catalog_default_scope_total_mismatch')
    if len(data['data'])!=min(10,max(0,total-(number-1)*10)):raise ValueError('catalog_page_length_mismatch')
    rows=[]
    for pos,x in enumerate(data['data']):
        if not isinstance(x.get('id'),int) or not isinstance(x.get('title'),str):raise ValueError('catalog_native_id_or_title_missing')
        key=str(x['id']);types=[name for name,prop in [('API','dataApi'),('FILE','dataFile'),('LINK','dataLink')] if x.get(prop)]
        rows.append(row('jeju',key,x['title'],'https://jejudatahub.net/data/view/data/'+key,eid,
            locator=f'data[{pos}]',source_page=number,source_catalog_record=x,source_service_types=types,
            source_data_key=x.get('dataKey'),source_owner_as_reported=x.get('owner'),source_creator_as_reported=x.get('createByName'),
            owner_is_not_verified_producing_organization=True,identity_note='Native numeric registration ID, distinct from dataKey, API ID, file ID and uploader account ID.'))
    return rows,total

def catalog():
    report_path=HERE/'jeju-catalog-report.json';dest=HERE/'inventory/jeju-catalog.json'
    if report_path.exists() and dest.exists() and read(report_path).get('snapshot_pagination_complete'):return read(dest)
    first,total=page(1);count_raw,count_receipt=fetch('jeju-public-count-page1','https://jejudatahub.net/api/data/count?'+urlencode(PARAMS))
    count=json.loads(count_raw) if count_raw else None;last=math.ceil(total/10);items={};receipts=[];errors=[];duplicates=[];totals=set()
    def add(p,rows,n):
        totals.add(n);receipts.append({'page':p,'rows':len(rows),'total':n,'evidence_id':rows[0]['evidence_id']})
        for r in rows:
            if r['id'] in items:duplicates.append({'id':r['id'],'earlier_page':items[r['id']]['source_page'],'page':p})
            items[r['id']]=r
    def checkpoint():
        store_catalog('jeju',list(items.values()));dump(dest,list(items.values()))
        complete=len(receipts)==last and len(items)==total==count and len(totals)==1 and not errors and not duplicates
        dump(report_path,{'generated_at':now(),'catalog_records':len(items),'reported_total':total,'independent_count':count,
            'pages_expected':last,'pages_received':len(receipts),'page_receipts':receipts,'reported_totals':sorted(totals),
            'duplicate_observations':duplicates,'errors':errors,'snapshot_pagination_complete':complete,
            'all_portal_catalogs_complete':False,'all_columns_complete':False,'source_ui_parameters':PARAMS,
            'scope':'Anonymous default data listing with all categories/types; portal permits non-government uploads. Other infographic/report/center catalogs remain separate.'})
        dump(HERE/'jeju-collection-report.json',{'generated_at':now(),'phase':'catalog_pagination','scope':'jeju','target_count':last,'processed':len(receipts),
            'status_counts':{'catalog_records':len(items)},'queue_exhausted':False,'all_columns_complete':False,'pid':os.getpid()})
    def get(p):
        try:r,n=page(p);return p,r,n,None
        except (ValueError,KeyError,TypeError) as exc:return p,[],0,str(exc)
    add(1,first,total);checkpoint()
    for p,rows,n,error in ordered_pages(get,range(2,last+1),ROOT/'.local/domestic-catalog/jeju.stop',2):
        if error:errors.append({'page':p,'error':error})
        else:add(p,rows,n)
        if p%20==0:checkpoint();print('jeju catalog',p,'/',last,flush=True)
    checkpoint()
    if not read(report_path)['snapshot_pagination_complete']:raise ValueError('catalog_pagination_incomplete')
    return list(items.values())

def definition(item):
    path=HERE/'definitions'/('jeju-schema-'+item['dataset_key']+'.json')
    if path.exists():return read(path)
    x=item['source_catalog_record'];base=item['locator']
    d={'portal_id':'jeju','dataset_key':item['dataset_key'],'evidence_id':item['evidence_id'],'source_url':item['url'],
        'additional_evidence_ids':['jeju-public-app-js'],'fields':[],'request_parameters':[],'outgoing_links':[],
        'file_versions':[],'public_dataset_metadata':x,'status':'public_metadata_observed_schema_pending',
        'human_approved':False,'raw_values_checked':False,'all_columns_complete':False,'api_called':False,'collected_at':now()}
    api=x.get('dataApi')
    if api:
        d['source_api_id']=api.get('id');d['api_endpoint_as_published']=api.get('url');d['api_endpoint_verified_or_called']=False
        try:
            elements=api.get('dataApiElements')
            if not isinstance(elements,list):raise ValueError('api_parameter_list_missing')
            for n,f in enumerate(elements):
                if f.get('apiId')!=api['id']:raise ValueError('parameter_parent_api_mismatch')
                if f.get('type') not in ('request','response') or not isinstance(f.get('name'),str) or not f['name']:raise ValueError('parameter_direction_or_name_unresolved')
                source={'source_api_id':api['id'],'source_parameter_id':f.get('id'),'source_parameter_record':f,'locator':base+f'.dataApi.dataApiElements[{n}]'}
                if f['type']=='request':d['request_parameters'].append(source);continue
                d['fields'].append({**source,'name':f['name'],'name_en':f['name'],'description':f.get('description'),'datatype':f.get('paramType'),
                    'unit':None,'role':'api_response_parameter','scope_note':'Explicit response parameter in public catalog metadata; example values do not establish datatype, units, nesting or quality.'})
            if d['fields']:d['status']='response_definition_observed'
        except (ValueError,KeyError,TypeError) as exc:d.update(fields=[],status='parameter_parse_unresolved',error=str(exc))
    for label,obj in [('dataset_file',x.get('dataFile')),('dataset_preview',x.get('file')),('api_preview',(api or {}).get('file'))]:
        if not obj:continue
        for n,f in enumerate(obj.get('fileInfos') or []):
            d['file_versions'].append({'source_role':label,'parent_file_id':obj.get('id'),'source_file_record':f,
                'locator':base+{'dataset_file':'.dataFile','dataset_preview':'.file','api_preview':'.dataApi.file'}[label]+f'.fileInfos[{n}]',
                'file_content_or_header_fetched':False})
    link=x.get('dataLink')
    if link and isinstance(link.get('url'),str) and urlsplit(link['url']).scheme in ('https','http'):
        d['outgoing_links'].append({'url':link['url'],'locator':base+'.dataLink.url','label':'Source declared data link','target_content_not_fetched':True})
    dump(path,d);return d

def main():run_queue('jeju',catalog(),definition,2)
if __name__=='__main__':main()
