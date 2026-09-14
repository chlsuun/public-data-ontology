"""Read public SGIS API guide tables; no token issuance or API execution."""
from common import *
from catalog_storage import row,store_catalog
from urllib.parse import urlsplit
import re

EID='sgis-data-api-guide'
URL='https://sgis.mods.go.kr/developer/html/openApi/api/data.html'

def parse(raw):
    soup=BeautifulSoup(raw,'html.parser');items=soup.select('.apiItem');records=[];docs=[];navigation=[]
    for n,a in enumerate(soup.select('a[href]')):
        m=re.search(r"(?:^#|['\"]#)(\d+)",a['href'])
        if m:navigation.append({'target_anchor':m[1],'label':a.get_text(' ',strip=True),'evidence_id':EID,'locator':f'a[href][{n}]@href'})
    ids=set();all_tables=soup.select('table')
    table_positions={id(t):n for n,t in enumerate(all_tables)}
    for n,item in enumerate(items):
        title=item.select_one('dt.guide_title[id]');endpoint=item.select_one('dd.guide_url')
        if title is None or endpoint is None:raise ValueError('api_section_identity_missing')
        anchor=title['id'];name=title.get_text(' ',strip=True);url=endpoint.get_text(' ',strip=True)
        if anchor in ids or not re.fullmatch(r'\d+',anchor) or urlsplit(url).scheme not in ('https','http'):raise ValueError('api_section_identity_invalid')
        ids.add(anchor);key='data-guide-'+anchor;source_url=URL+'#'+anchor
        records.append(row('sgis',key,name,source_url,EID,locator=f'.apiItem[{n}] dt.guide_title',
            source_guide_anchor=anchor,source_guide_position=n,documented_api_url=url,
            identity_note='Guide anchor in source-document namespace, not an inferred API ID from example output.',
            source_description=title.find_next_sibling('dd').get_text(' ',strip=True)))
        d={'portal_id':'sgis','dataset_key':key,'evidence_id':EID,'source_url':source_url,
            'additional_evidence_ids':['sgis-developer-home-20260913'],'fields':[],'request_parameters':[],
            'response_artifacts':[],'unresolved_response_rows':[],'status':'response_definition_pending',
            'guide_anchor':anchor,'guide_position':n,'api_url_as_documented':url,'api_called':False,
            'human_approved':False,'raw_values_checked':False,'all_columns_complete':False,'collected_at':now()}
        captions=[]
        for table in item.select('table'):
            caption=table.caption.get_text(' ',strip=True) if table.caption else None;captions.append(caption)
            headers=[h.get_text(' ',strip=True) for h in table.select('thead th')];tn=table_positions[id(table)]
            expected=['요청변수','값','Optional','설명'] if caption=='요청정보' else ['출력 변수','값','설명'] if caption=='응답정보' else None
            if headers!=expected or expected is None:raise ValueError('unexpected_table_direction_or_headers')
            for rn,tr in enumerate(table.select('tbody tr')):
                cells=tr.find_all(['td','th'],recursive=False);texts=[c.get_text(' ',strip=True) for c in cells]
                observed={'table_index':tn,'row_index':rn,'source_cells':texts,'locator':f'table[{tn}] tbody tr[{rn}]'}
                if caption=='요청정보':d['request_parameters'].append(observed);continue
                if len(cells)!=3 or any(c.has_attr('colspan') or c.has_attr('rowspan') for c in cells):
                    d['unresolved_response_rows'].append({**observed,'error':'nonrectangular_response_row'});continue
                if texts[1]=='Javascript':d['response_artifacts'].append({**observed,'source_output_kind':'Javascript'});continue
                if not texts[0]:d['unresolved_response_rows'].append({**observed,'error':'response_name_empty'});continue
                datatype=texts[1] if texts[1] in ('String','Number','Integer','Float','Double','Boolean','Array','Object') else None
                d['fields'].append({**observed,'name':texts[0],'name_en':texts[0],'description':texts[2],
                    'datatype':datatype,'unit':None,'source_value_or_type':texts[1],'role':'api_response_parameter',
                    'guide_anchor':anchor,'scope_note':'Official response table row. Value column may contain precision/code references; units and nested paths are not inferred from examples.'})
        if captions!=['요청정보','응답정보']:raise ValueError('request_response_pair_missing_or_repeated')
        d['status']='response_definition_observed_partial' if d['unresolved_response_rows'] else 'response_definition_observed' if d['fields'] else 'response_artifact_descriptor_observed' if d['response_artifacts'] else 'response_definition_pending'
        docs.append(d)
    if not records:raise ValueError('no_api_sections')
    missing=[x for x in navigation if x['target_anchor'] not in ids]
    by_id={r['source_guide_anchor']:r for r in records}
    mismatches=[{**x,'section_title':by_id[x['target_anchor']]['title']} for x in navigation if x['target_anchor'] in ids and x['label']!=by_id[x['target_anchor']]['title']]
    return records,docs,{'navigation':navigation,'menu_targets_without_api_section':missing,'menu_title_mismatches':mismatches}

def main():
    raw,r=fetch(EID,URL)
    if raw is None:raise ValueError('public_guide_fetch_unresolved')
    records,docs,nav=parse(raw);store_catalog('sgis',records);dump(HERE/'inventory/sgis-catalog.json',records)
    for d in docs:
        path=HERE/'definitions'/('sgis-schema-'+d['dataset_key']+'.json')
        if path.exists():
            old=read(path)
            if old.get('code_list_reference_guide_sha256')==r['sha256']:
                d['code_list_references']=old.get('code_list_references',[]);d['code_list_reference_guide_sha256']=r['sha256']
        dump(path,d)
    dump(HERE/'sgis-catalog-report.json',{'generated_at':now(),'catalog_records':len(records),'unique_guide_anchors':len({d['guide_anchor'] for d in docs}),
        'guide_sections_read':len(docs),'guide_response_tables_read':len(docs),'snapshot_all_observed_body_sections_read':True,
        'all_navigation_targets_resolved':not nav['menu_targets_without_api_section'] and not nav['menu_title_mismatches'],
        'all_portal_catalogs_complete':False,'all_columns_complete':False,**nav})
    counts={}
    for d in docs:counts[d['status']]=counts.get(d['status'],0)+1
    report={'generated_at':now(),'scope':'SGIS public data API guide body only; map API/SDK, file dictionaries, code tables and unmatched menu targets remain pending',
        'target_count':len(docs),'processed':len(docs),'status_counts':counts,'documented_field_occurrences':sum(len(d['fields']) for d in docs),
        'request_rows':sum(len(d['request_parameters']) for d in docs),'response_artifact_rows':sum(len(d['response_artifacts']) for d in docs),
        'unresolved_response_rows':sum(len(d['unresolved_response_rows']) for d in docs),'queue_exhausted':True,'all_columns_complete':False}
    dump(HERE/'sgis-collection-report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
