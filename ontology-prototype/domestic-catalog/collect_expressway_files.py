"""Public original-document version lists and explicitly displayed external links.

Reads list metadata, never download requests, usage forms or observation previews.
Parent HTML column definitions are kept in their separate source document.
"""
from common import *
from queue_runner import run_queue
from urllib.parse import urlsplit
import re

BASE='https://data.ex.co.kr'

def collect(item):
    key=item['dataset_key'];dest=HERE/'definitions'/('expressway-schema-'+key+'-files.json')
    if dest.exists():return read(dest)
    parent=read(HERE/'definitions'/('expressway-schema-'+key+'.json'))
    d={'portal_id':'expressway','dataset_key':key,'source_url':item['url'],
        'evidence_id':'expressway-original-files-'+key,'collected_at':now(),'fields':[],
        'status':'fetch_unresolved','file_versions':[],'outgoing_links':[],
        'human_approved':False,'raw_values_checked':False,'all_columns_complete':False,
        'original_files_downloaded':False,'usage_form_submitted':False,'observation_api_called':False,
        'parent_html_evidence_id':parent['evidence_id'],'renderer_evidence_id':'expressway-original-document-script',
        'parent_column_definitions_inherited':False,'issues':[]}
    try:
        receipt=read(HERE/'evidence'/(parent['evidence_id']+'.json'))
        if receipt['status']!='fetched':raise ValueError('parent_html_not_observed')
        soup=BeautifulSoup(gzip.decompress((HERE/receipt['raw_file']).read_bytes()),'html.parser')
        hidden=soup.select_one('input#datasetId');table=soup.select_one('table#listTable2')
        if hidden is None or hidden.get('value')!=key or table is None or table.caption.get_text(' ',strip=True)!='원본 문서':
            raise ValueError('parent_identity_or_original_document_table_changed')
        body,r=fetch(d['evidence_id'],BASE+'/portal/docu/getList',form={'datasetId':key},accept='application/json')
        if body is None:dump(dest,d);return d
        rows=json.loads(body)
        if not isinstance(rows,list):raise ValueError('file_list_shape_changed')
        if len({x['fileId'] for x in rows})!=len(rows):raise ValueError('repeated_file_id_requires_review')
        for n,x in enumerate(rows):
            if x['datasetId']!=key or not x['fileId'].isdigit():raise ValueError('version_list_identity_changed')
            d['file_versions'].append({'evidence_id':d['evidence_id'],'locator':f'[{n}]',
                'file_id':x['fileId'],'dataset_id':x['datasetId'],'file_name':x['fileName'],
                'description':x['description'],'department_as_reported':x['department'],
                'update_date_as_reported':x['updateDate'],'converted_flag_as_reported':x['convertedYn'],
                'file_body_and_version_columns_not_fetched':True})
        d['source_file_list_row_count']=len(rows)
        linktable=soup.select_one('table#listTable3')
        if linktable is not None:
            if linktable.caption.get_text(' ',strip=True)!='원본 URL 링크':raise ValueError('link_table_caption_changed')
            eid='expressway-original-links-'+key
            b,r=fetch(eid,BASE+'/portal/docu/getDocuUrlLinkList',form={'datasetId':key},accept='application/json')
            d['external_link_list_evidence_id']=eid
            if b is None:d['issues'].append({'issue':'external_link_list_fetch_unresolved','evidence_id':eid})
            else:
                links=json.loads(b)
                if not isinstance(links,list):raise ValueError('external_link_list_shape_changed')
                d['source_external_link_rows']=links
                for n,x in enumerate(links):
                    url=x['linkUrl'];parsed=urlsplit(url)
                    if parsed.scheme not in ('http','https') or not parsed.hostname:
                        d['issues'].append({'issue':'unusable_source_link_url','evidence_id':eid,'locator':f'[{n}].linkUrl','value':url});continue
                    d['outgoing_links'].append({'url':url,'label':x.get('siteName'),
                        'organization_name_as_reported':x.get('orgName'),'evidence_id':eid,'locator':f'[{n}].linkUrl',
                        'same_dataset_asserted':False,'target_not_requested':True})
        d['dynamic_item_table_present']=soup.select_one('table#itemList') is not None
        if d['dynamic_item_table_present']:d['issues'].append({'issue':'additional_visible_item_table_requires_adapter'})
        d['status']='file_version_metadata_observed_partial' if d['issues'] else 'file_version_metadata_observed'
    except (ValueError,KeyError,TypeError) as exc:d.update(status='parse_unresolved',error=str(exc))
    dump(dest,d);return d

if __name__=='__main__':
    items=[x for x in read(HERE/'inventory/expressway-catalog.json') if x['kind']=='ORG']
    run_queue('expressway-files',items,collect,2)
