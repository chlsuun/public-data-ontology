"""Collect explicit public API parameter definitions, never observation API values."""
from common import *
from static_js_data import literal_value
from queue_runner import run_queue
from urllib.parse import urljoin,urlsplit,urlencode
import re,argparse

GENERIC_NAMES={'header','body','items','item','list','response','result'}

def visible_text(value):return ' '.join(value.split())

def original(eid):
    r=read(HERE/'evidence'/(eid+'.json'))
    if r.get('status')!='fetched':raise ValueError('parent_source_unresolved:'+eid)
    return gzip.decompress((HERE/r['raw_file']).read_bytes()),r

def parse_page(raw,item,eid):
    soup=BeautifulSoup(raw,'html.parser');native=item['source_native_id']
    hidden=soup.select_one('input[name=publicdatapk]')
    if hidden is None or hidden.get('value')!=native:raise ValueError('detail_parent_id_mismatch')
    h=soup.select_one('h4.h4BI-tit')
    if h is None:raise ValueError('detail_title_missing')
    h=BeautifulSoup(str(h),'html.parser').h4
    for span in h.select('span'):span.decompose()
    if h.get_text(' ',strip=True)!=item['title']:raise ValueError('detail_title_mismatch')
    values={};locations={}
    for sn,script in enumerate(soup.select('script:not([src])')):
        code=script.string or script.get_text()
        for key in ('publicdatadetailpk','oprtinnm','oprtinseqno'):
            for m in re.finditer(r'(?m)^\s*var\s+'+key+r'\s*=\s*',code):
                value,end=literal_value(code,m.end())
                if not isinstance(value,str) or not re.match(r'\s*;',code[end:]):raise ValueError('nonliteral_operation_identity')
                if key in values:raise ValueError('ambiguous_operation_identity')
                values[key]=value;locations[key]={'script_index':sn,'start_char':m.end(),'end_char':end}
    tabs=[]
    for n,li in enumerate(soup.select('.tabs_opnm li')):
        m=re.fullmatch(r"\s*javascript:selfCall\('([^']+)','(\d+)'\);\s*",li.get('onclick',''))
        if not m or m[1]!=native:raise ValueError('operation_tab_parent_or_navigation_mismatch')
        if not li.get('id') or not li.get_text(' ',strip=True):raise ValueError('operation_tab_identity_missing')
        tabs.append({'operation_id':li['id'],'operation_name':li.get_text(' ',strip=True),'sheetorder':m[2],
            'tab_position':n,'evidence_id':eid,'locator':f'.tabs_opnm li[{n}]'})
    if tabs and (set(values)!=set(('publicdatadetailpk','oprtinnm','oprtinseqno')) or not values['publicdatadetailpk']):raise ValueError('default_resource_identity_missing')
    if tabs and not any(t['operation_name']==visible_text(values['oprtinnm']) and t['operation_id']==values['oprtinseqno'] for t in tabs):raise ValueError('selected_operation_not_in_tabs')
    form=soup.select_one('form[name=frm]');navigation=None
    if form:
        action=urljoin(item['url'],form.get('action',''));parts=urlsplit(action)
        path=parts.path.split(';jsessionid=')[0]
        if parts.hostname=='alldam.chungnam.go.kr' and path=='/index.do' and form.get('method','get').lower()=='get':
            params={i['name']:i.get('value','') for i in form.select('input[type=hidden][name]') if i['name'] in ('menuCd','publicdatapk','sheetorder','serviceOrder','publicdatadetailpk','page')}
            if params.get('publicdatapk')==native:navigation={'url':parts.scheme+'://'+parts.netloc+path,'parameters':params,'locator':'form[name=frm] action/method/hidden inputs; selfCall sets sheetorder'}
    return {'tabs':tabs,'selected':values,'selected_value_locations':locations,'navigation':navigation}

def parse_parameters(raw,resource,operation,eid):
    data=json.loads(raw)
    if not isinstance(data,list):raise ValueError('parameter_response_not_array')
    fields=[];requests=[];responses=[];excluded=[]
    for n,r in enumerate(data):
        if not isinstance(r,dict) or r.get('publicdatadetail')!=resource or r.get('oprtinnm')!=operation:raise ValueError('parameter_parent_or_operation_mismatch')
        if r.get('paramtrse') not in ('요청변수','응답변수') or not isinstance(r.get('paramtrnm'),str) or not r['paramtrnm']:raise ValueError('parameter_direction_or_name_missing')
        observed={'source_row':r,'evidence_id':eid,'locator':f'[{n}]','source_resource_id':resource,'operation_name':operation}
        if r['paramtrse']=='요청변수':requests.append(observed);continue
        responses.append(observed)
        if r['paramtrnm'].lower() in GENERIC_NAMES:
            excluded.append({**observed,'reason':'Generic element name: container/scalar nature and hierarchy not declared in this parameter listing; withheld from field count.'});continue
        fields.append({'name':r.get('paramtrkornm') or r['paramtrnm'],'name_en':r['paramtrnm'],
            'description':r.get('paramtrid'),'datatype':None,'unit':None,'role':'api_response_parameter',
            'evidence_id':eid,'locator':f'[{n}]','source_resource_id':resource,'operation_name':operation,
            'source_parameter_record':r,'scope_note':'Explicit source response parameter; data/control semantics and nesting are not inferred. Request parameters excluded.'})
    return fields,requests,responses,excluded

def collect(item):
    key=item['dataset_key'];path=HERE/'definitions'/('chungnam-operations-'+key+'.json')
    prior=read(path) if path.exists() else None
    if prior and not (prior.get('error')=='selected_operation_not_in_tabs' and prior.get('parser_version',0)<2):return prior
    parent='chungnam-schema-'+key
    d={'portal_id':'chungnam','dataset_key':key,'evidence_id':parent,'source_url':item['url'],
        'additional_evidence_ids':[parent],'fields':[],'operations':[],'status':'operation_discovery_unresolved',
        'human_approved':False,'raw_values_checked':False,'all_columns_complete':False,'all_versions_complete':False,
        'collected_at':now(),'parser_version':2}
    if prior:d['prior_parse_outcomes']=[{'status':prior['status'],'error':prior.get('error'),'parser_version':prior.get('parser_version'),'collected_at':prior['collected_at']}]
    try:
        raw,receipt=original(parent);page=parse_page(raw,item,parent);d['operation_tabs']=page['tabs'];d['initial_selection']=page['selected'];d['initial_selection_locations']=page['selected_value_locations']
        if not page['tabs']:d['error']='no_operation_tabs_observed';dump(path,d);return d
        seen={};errors=[]
        for tab in page['tabs']:
            selected=page['selected'];page_eid=parent;page_url=receipt['requested_url']
            # Every repeated tab is inspected; a shared number/name is not a version identity.
            if tab['tab_position']!=0:
                nav=page['navigation']
                if not nav:errors.append({'tab':tab,'error':'public_navigation_form_unresolved'});continue
                page_eid=f"chungnam-operation-page-{item['source_native_id']}-{tab['sheetorder']}"
                url=nav['url']+'?'+urlencode({**nav['parameters'],'sheetorder':tab['sheetorder']})
                body,rec=fetch(page_eid,url);d['additional_evidence_ids'].append(page_eid)
                if body is None:errors.append({'tab':tab,'evidence_id':page_eid,'error':'operation_page_fetch_unresolved'});continue
                try:
                    response=parse_page(body,item,page_eid);selected=response['selected'];page_url=rec['requested_url']
                except (ValueError,KeyError,TypeError) as exc:errors.append({'tab':tab,'evidence_id':page_eid,'error':str(exc)});continue
            if selected['oprtinseqno']!=tab['operation_id'] or visible_text(selected['oprtinnm'])!=tab['operation_name']:
                errors.append({'tab':tab,'evidence_id':page_eid,'error':'returned_selected_operation_mismatch'});continue
            resource=selected['publicdatadetailpk'];name=selected['oprtinnm'];identity=(resource,name)
            mapping={**tab,'selection_evidence_id':page_eid,'source_resource_id':resource}
            if identity in seen:
                d['operations'][seen[identity]]['tab_occurrences'].append(mapping);continue
            eid=uid('chungnam-operation-parameters',item['source_native_id'],resource,name)
            # Reuse the earlier public probe when it is exactly the same metadata request.
            if item['source_native_id']=='15157561' and resource=='uddi:ca11c87e-c5f1-4f27-8db6-a206ae96ff5b' and name=='충청남도 보령시 관광지유입인구및총매출액조회':eid='chungnam-entity-metadata-probe-15157561'
            body,rec=fetch(eid,'https://alldam.chungnam.go.kr/dataSet/entityDataAll.do',form={'publicdatadetailpk':resource,'oprtinnm':name},referer=page_url)
            op={'source_resource_id':resource,'operation_name':name,'tab_occurrences':[mapping],'evidence_id':eid,'status':'fetch_unresolved'}
            seen[identity]=len(d['operations']);d['operations'].append(op);d['additional_evidence_ids'].append(eid)
            if body is None:continue
            try:
                fs,request,response,excluded=parse_parameters(body,resource,name,eid)
                op.update(status='response_definition_observed' if response else 'no_response_parameters_observed',request_parameters=request,response_elements=response,
                    excluded_generic_elements=excluded,field_count=len(fs))
                d['fields'].extend(fs)
            except (ValueError,KeyError,TypeError) as exc:op.update(status='parse_unresolved',error=str(exc))
        d['discovery_errors']=errors
        complete=not errors and all(o['status']=='response_definition_observed' for o in d['operations'])
        d['all_visible_operation_tabs_inspected']=not errors
        d['status']='operation_definitions_observed' if complete else 'operation_definitions_observed_partial' if d['fields'] else 'operation_definitions_unresolved'
        if d['operations']:d['evidence_id']=d['operations'][0]['evidence_id']
        d['additional_evidence_ids']=list(dict.fromkeys(d['additional_evidence_ids']))
    except (ValueError,KeyError,TypeError,OSError) as exc:d['error']=str(exc)
    dump(path,d);return d

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);args=ap.parse_args()
    rows=[r for r in read(HERE/'inventory/chungnam-catalog.json') if r['source_registration_key']=='publicdatapk' and 'API' in r['source_service_types']]
    run_queue('chungnam-operations',rows[:args.limit] if args.limit else rows,collect,2,bool(args.limit))

if __name__=='__main__':main()
