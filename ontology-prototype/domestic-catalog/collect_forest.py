"""Forest agency's explicit catalog tabs and public HTML API definitions."""
from common import *
from catalog_storage import row,store_catalog
from queue_runner import run_queue
from urllib.parse import urljoin,urlsplit,parse_qs
from collections import Counter
import re

BASE='https://www.forest.go.kr'
ENTRY=BASE+'/kfsweb/opda/dataMng/selectPblicDataList.do?mn=NKFS_06_08_02&tabs=1'

def clean_href(href):
    # Public pages add anonymous URL-session tokens; requests use the linked route without them.
    return re.sub(r';jsessionid=[^?&#/]+','',href,flags=re.I)

def catalog():
    b,r=fetch('forest-public-catalog-page1',ENTRY)
    if b is None:raise ValueError('entry_catalog_unresolved')
    s=BeautifulSoup(b,'html.parser');tabs={}
    for n,a in enumerate(s.select('a[href]')):
        url=urljoin(ENTRY,a['href']);q=parse_qs(urlsplit(url).query)
        if urlsplit(url).path.endswith('/selectPblicDataList.do') and 'tabs' in q:
            code=q['tabs'][0];tabs[code]={'code':code,'label':a.get_text(' ',strip=True),'url':url,'locator':f'a[href][{n}]'}
    if not tabs:raise ValueError('explicit_category_tabs_missing')
    items={};occurrences=[];pages=[]
    for code,tab in tabs.items():
        eid='forest-public-catalog-page1' if code=='1' else 'forest-public-catalog-tab'+code
        b,r=fetch(eid,tab['url'])
        if b is None:raise ValueError('catalog_tab_fetch_unresolved:'+code)
        s=BeautifulSoup(b,'html.parser');cards=s.select('.details_list > ul > li')
        selected=s.select_one('input[name=tabs]')
        if b'</html>' not in b.lower() or not cards or not selected or selected.get('value')!=code:raise ValueError('catalog_tab_body_or_identity_unresolved')
        paging=s.select('.paging a, .pagination a')
        if paging:raise ValueError('new_pagination_controls_require_review')
        pages.append({'tab':tab,'evidence_id':eid,'cards':len(cards),'body_complete':True,'pagination_controls_observed':False})
        for n,card in enumerate(cards):
            title=card.select_one('.sm_wrap a');links=card.select('a[href]')
            if title is None:raise ValueError('card_title_missing')
            href=clean_href(title['href']);url=urljoin(tab['url'],href)
            if urlsplit(url).scheme not in ('http','https'):raise ValueError('catalog_route_requires_review')
            q=parse_qs(urlsplit(url).query);native=q.get('pblicDataId',[None])[0]
            if native and not re.fullmatch(r'PBD[0-9]+',native):raise ValueError('unexpected_native_public_data_id')
            key=native if native else uid('linked-page',url)
            loc=f'.details_list > ul > li[{n}]'
            desc=next((a.get_text(' ',strip=True) for a in links if a.get('href')=='#;'),None)
            local_detail=urlsplit(url).hostname=='www.forest.go.kr' and bool(native)
            occurrence={'dataset_key':key,'tab_code':code,'tab_label':tab['label'],'evidence_id':eid,
                'locator':loc,'title':title.get_text(' ',strip=True),'description':desc,'linked_url':url,
                'link_occurrences':[{'locator':loc+f' a[href][{i}]','label':a.get_text(' ',strip=True),
                    'url_without_session_token':urljoin(tab['url'],clean_href(a['href']))} for i,a in enumerate(links) if a.get('href')!='#;']}
            occurrences.append(occurrence)
            item=row('forest',key,occurrence['title'],url if local_detail else tab['url'],eid,
                kind='public_api_or_data_guide' if local_detail else 'external_catalog_reference',locator=loc,
                description=desc,native_public_data_id=native,linked_resource_url=url,
                local_html_guide=local_detail,external_reference_url=None if local_detail else url,
                source_category_code=code,source_category_label=tab['label'],
                local_id_basis='Explicit pblicDataId in source link' if native else 'Project hash of exact linked URL; no source registration ID reported',
                description_is_not_column_definition=True,source_session_parameter_removed=True)
            if key in items:
                if items[key]['linked_resource_url']!=url:raise ValueError('same_native_id_has_different_link_requires_review')
                items[key]['catalog_occurrences'].append(occurrence)
            else:item['catalog_occurrences']=[occurrence];items[key]=item
    records=list(items.values());store_catalog('forest',records)
    dump(HERE/'inventory/forest-catalog.json',records)
    dump(HERE/'forest-catalog-report.json',{'generated_at':now(),'catalog_records':len(records),'catalog_card_occurrences':len(occurrences),
        'category_pages':pages,'local_html_guides':sum(i['local_html_guide'] for i in records),
        'external_reference_records':sum(not i['local_html_guide'] for i in records),
        'explicit_tab_documents_complete':True,'source_reported_total':None,'snapshot_pagination_complete':None,
        'scope':'Every card in all category tabs explicitly linked by this public page; no source global count or national completeness proof',
        'all_portal_catalogs_complete':False,'all_columns_complete':False})
    return records

def parse(body):
    s=BeautifulSoup(body,'html.parser');content=s.select_one('#txt')
    if content is None or b'</html>' not in body.lower():raise ValueError('detail_content_incomplete')
    d={'fields':[],'request_parameters':[],'definition_tables':[],'other_table_headers':[],'issues':[],
        'api_endpoint_texts':[],'outgoing_links':[],'download_link_metadata':[],
        'public_usage_note_candidates':[],'guide_identity_observations':{
            'headings':[h.get_text(' ',strip=True) for h in content.select('h3,h4')],
            'hidden_public_data_ids':[x.get('value') for x in content.select('input[name=pblicDataId]')]}}
    for tn,t in enumerate(s.select('table')):
        prev=t.find_previous(['h2','h3','h4','h5']);heading=prev.get_text(' ',strip=True) if prev else ''
        caption=t.caption.get_text(' ',strip=True) if t.caption else ''
        head=[c.get_text(' ',strip=True) for c in t.select('thead th')]
        role='response' if 'Response Parameter' in heading or '결과파라미터' in caption.replace(' ','') else ('request' if 'Request Parameter' in heading or '요청파라미터' in caption.replace(' ','') else None)
        if role:
            table={'table_index':tn,'heading':heading,'caption':caption,'headers':head,'role':role,'rows':[]}
            d['definition_tables'].append(table)
            if head!=['Parameter','데이터 타입','내용']:
                d['issues'].append({'issue':'unrecognized_parameter_headers','table_index':tn,'headers':head});continue
            for rn,tr in enumerate(t.select('tbody tr')):
                cells=tr.find_all(['td','th'],recursive=False);values=[c.get_text(' ',strip=True) for c in cells]
                raw={'source_cells':values,'locator':f'table[{tn}].tbody.tr[{rn}]','table_index':tn,'row_index':rn}
                table['rows'].append(raw)
                if len(cells)!=3 or any(c.has_attr('rowspan') or c.has_attr('colspan') for c in cells) or not values[0]:
                    d['issues'].append({'issue':'unresolved_parameter_row_shape',**raw});continue
                v={**raw,'name_en':values[0],'name':values[0],'description':values[2],
                    'datatype':values[1] or None,'unit':None,'source_type_as_reported':values[1]}
                if role=='response':v['role']='api_response_column';d['fields'].append(v)
                else:d['request_parameters'].append(v)
        elif 'OPEN API URL' in heading or 'OPEN API URL' in t.get_text(' ',strip=True)[:100]:
            d['api_endpoint_texts'].append({'locator':f'table[{tn}]','text_as_reported':t.get_text(' ',strip=True),'endpoint_called':False})
        else:d['other_table_headers'].append({'table_index':tn,'heading':heading,'caption':caption,'headers':head,'rows_not_promoted_to_columns':True})
    for n,a in enumerate(content.select('a[href]')):
        href=clean_href(a['href']);url=urljoin(BASE,href);label=a.get_text(' ',strip=True)
        if urlsplit(url).hostname in ('www.data.go.kr','data.go.kr') and re.search(r'/(?:data|dataset)/[0-9]+/',url):
            d['outgoing_links'].append({'url':url,'label':label,'locator':f'#txt a[href][{n}]','same_dataset_asserted':False})
        elif re.search(r'(?:download|filedown|\.pdf(?:\?|$)|\.hwp(?:\?|$)|\.zip(?:\?|$)|\.shp(?:\?|$))',href,re.I) or '다운로드' in label:
            d['download_link_metadata'].append({'url_as_reported_without_session':url,'label':label,'locator':f'#txt a[href][{n}]',
                'onclick_as_reported':a.get('onclick'),'file_downloaded':False})
        elif urlsplit(url).scheme in ('https','http') and urlsplit(url).hostname not in ('www.forest.go.kr','api.forest.go.kr'):
            d['outgoing_links'].append({'url':url,'label':label,'locator':f'#txt a[href][{n}]','same_dataset_asserted':False})
    for n,p in enumerate(content.select('p')):
        text=p.get_text(' ',strip=True)
        if any(term in text for term in ('비영리','목적으로','주의사항','무료신청','신청목적','신청사유')):
            d['public_usage_note_candidates'].append({'text_as_reported':text,'locator':f'#txt p[{n}]',
                'selection_method':'literal_keyword_match_for_human_review','license_or_reuse_approval_inferred':False})
    return d

def collect(item):
    key=item['dataset_key'];p=HERE/'definitions'/('forest-schema-'+key+'.json')
    if p.exists() and read(p).get('parser_version')==2:return read(p)
    eid='forest-detail-'+key if item['local_html_guide'] else item['evidence_id']
    d={'portal_id':'forest','dataset_key':key,'evidence_id':eid,'source_url':item['url'],'fields':[],
        'additional_evidence_ids':[item['evidence_id']],'status':'fetch_unresolved','collected_at':now(),
        'human_approved':False,'raw_values_checked':False,'all_columns_complete':False,'observation_api_called':False,'parser_version':2}
    if not item['local_html_guide']:
        d.update(status='external_reference_observed_schema_pending',outgoing_links=[{'url':item['linked_resource_url'],
            'label':item['title'],'locator':item['locator']+' .sm_wrap a@href','same_dataset_asserted':False}])
    else:
        b,r=fetch(eid,item['url'])
        d['source_url']=r['requested_url']
        d['catalog_guide_link_url']=item['url']
        if b:
            try:
                d.update(parse(b))
                observed=d['guide_identity_observations']['hidden_public_data_ids']
                if observed and set(observed)!={key}:raise ValueError('guide_hidden_identity_mismatch')
                d['status']='response_definition_observed_partial' if d['fields'] and d['issues'] else ('response_definition_observed' if d['fields'] else 'public_metadata_observed_schema_pending')
            except (ValueError,TypeError,KeyError) as exc:d.update(status='parse_unresolved',error=str(exc),fields=[])
    dump(p,d);return d

def summarize():
    records=read(HERE/'inventory/forest-catalog.json')
    docs=[read(HERE/'definitions'/('forest-schema-'+r['dataset_key']+'.json')) for r in records]
    fields=[f for d in docs for f in d['fields']]
    qa={'generated_at':now(),'portal_id':'forest',
        'qa_scope':'Public catalog and documentation availability, source usage-note candidates; not live values or legal reuse approval',
        'catalog_records':len(records),'local_html_guide_records':sum(r['local_html_guide'] for r in records),
        'external_reference_records':sum(not r['local_html_guide'] for r in records),
        'with_response_definition':sum(bool(d['fields']) for d in docs),'documented_response_fields':len(fields),
        'input_parameter_rows':sum(len(d.get('request_parameters',[])) for d in docs),
        'field_datatype_present':sum(bool(f['datatype']) for f in fields),'unit_explicitly_documented':sum(bool(f['unit']) for f in fields),
        'usage_note_candidates':[{'dataset_key':d['dataset_key'],'evidence_id':d['evidence_id'],'notes':d['public_usage_note_candidates']}
            for d in docs if d.get('public_usage_note_candidates')],
        'all_columns_complete':False,'quality_scores_assigned':False,'raw_values_checked':False,
        'source_reported_global_catalog_total':None,'national_census_complete':False,
        'remaining_scope':['External linked resources and original schemas','Map/file attribute dictionaries',
            'All file versions and code lists','Other agency catalogs beyond these five category pages'],
        'source_field_types_preserved_without_correction':True,'map_listing_rows_not_counted_as_dataset_registrations':True}
    attributes=HERE/'forest-attribute-summary.json'
    if attributes.exists():
        qa['additional_file_attribute_summary']=read(attributes)
        qa['documented_file_attribute_fields']=qa['additional_file_attribute_summary']['attribute_fields']
        qa['file_layer_dictionary_scope_note']='Do not add API output fields and file-layer attributes as if all describe a single table.'
    dump(HERE/'forest-source-qa.json',qa)

if __name__=='__main__':
    run_queue('forest',catalog(),collect,2)
    summarize()
