"""HRDK's public API referral catalog and separate MCP tool contracts.

Tool descriptions are stored as untrusted source data; no tools/call is executed.
"""
from common import *
from catalog_storage import row,store_catalog
from urllib.parse import urljoin
import re

BASE='https://openapi.hrdkorea.or.kr'

def catalog():
    eid='hrdk-public-home-20260914';body,r=fetch(eid,BASE+'/main')
    if body is None:raise ValueError('catalog_fetch_unresolved')
    soup=BeautifulSoup(body,'html.parser');section=soup.select_one('#section2')
    if not section:raise ValueError('catalog_section_missing')
    items=[];ids=[]
    for n,title in enumerate(section.select('.section-body-title')):
        card=title.parent;links=card.select('a[href]');info=card.find_next_sibling('div')
        if len(links)!=1 or not info or 'section-body-info' not in info.get('class',[]):raise ValueError('catalog_card_structure_changed')
        href=links[0]['href'];m=re.fullmatch(r'https://www\.data\.go\.kr/data/([0-9]+)/openapi\.do',href)
        if not m:raise ValueError('catalog_reference_route_changed')
        public_id=m[1];key='data-go-link-'+public_id;ids.append(public_id)
        item=row('hrdk-api',key,title.get_text(' ',strip=True),BASE+'/main#section2',eid,
            kind='external_api_catalog_reference',locator=f'#section2 .section-body-title[{n}]',
            description=info.select_one('.ml-1').get_text(' ',strip=True),
            source_system_labels=[p.get_text(' ',strip=True) for p in info.select('.bgcolor-web-navy')],
            source_formats=[p.get_text(' ',strip=True) for p in info.select('p.rounded-pill')],
            external_reference_url=href,target_portal_id='data-go',target_public_data_pk=public_id,
            local_id_basis='Project identifier derived from explicitly linked data.go.kr publicDataPk, not a native HRDK dataset ID.',
            source_fields_copied_from_target=False)
        items.append(item)
        dump(HERE/'definitions'/('hrdk-api-schema-'+key+'.json'),{
            'portal_id':'hrdk-api','dataset_key':key,'evidence_id':eid,'source_url':item['url'],
            'fields':[],'status':'external_schema_reference_observed','human_approved':False,'raw_values_checked':False,
            'all_columns_complete':False,'catalog_metadata':item,'collected_at':now(),
            'outgoing_links':[{'url':href,'locator':item['locator']+' parent a@href','label':item['title'],
                'target_portal_id':'data-go','target_public_data_pk':public_id,'semantic_equivalence_asserted':False}]})
    if not items or len(ids)!=len(set(ids)) or len(section.select('a[href]'))!=len(items):raise ValueError('catalog_card_or_id_reconciliation_failed')
    store_catalog('hrdk-api',items);dump(HERE/'inventory/hrdk-api-catalog.json',items)
    dump(HERE/'hrdk-api-catalog-report.json',{'generated_at':now(),'source_evidence_id':eid,
        'catalog_records':len(items),'distinct_linked_public_data_pks':len(set(ids)),
        'snapshot_document_body_complete':True,'snapshot_pagination_complete':True,
        'scope':'All cards in the public /main#section2 document; no claim that this is all agency APIs.',
        'all_portal_catalogs_complete':False,'all_columns_complete':False,'source_reported_total':None})
    dump(HERE/'hrdk-api-collection-report.json',{'generated_at':now(),'scope':'hrdk-api','target_count':len(items),
        'processed':len(items),'status_counts':{'external_schema_reference_observed':len(items)},
        'queue_exhausted':True,'documented_field_occurrences':0,'all_columns_complete':False})
    return items

def rpc_result(body):
    text=body.decode('utf-8-sig')
    if text.lstrip().startswith('{'):messages=[json.loads(text)]
    else:
        messages=[]
        for block in re.split(r'\r?\n\r?\n',text.strip()):
            lines=[x[5:].lstrip(' ') for x in block.splitlines() if x.startswith('data:')]
            if lines:messages.append(json.loads('\n'.join(lines)))
    responses=[m for m in messages if m.get('id')=='catalog-metadata']
    if len(responses)!=1 or 'error' in responses[0]:raise ValueError('rpc_result_unresolved')
    result=responses[0].get('result')
    if not isinstance(result,dict) or not isinstance(result.get('tools'),list):raise ValueError('tool_catalog_missing')
    return result

def tool_catalog():
    guide,r=fetch('hrdk-public-mcp-guide',BASE+'/mcp.html')
    if guide is None:raise ValueError('mcp_guide_unresolved')
    soup=BeautifulSoup(guide,'html.parser');endpoints=[{'path':'/mcp','source_label':'통합 MCP','locator':'guide server address'}]
    for n,c in enumerate(soup.select('.mcp-ep')):
        path=c.get_text(' ',strip=True)
        if not re.fullmatch('/mcp/[a-z]+',path):raise ValueError('unexpected_guide_endpoint')
        endpoints.append({'path':path,'source_label':c.parent.get_text(' ',strip=True),'locator':f'.mcp-ep[{n}]'})
    tools=[];reports=[]
    for ep in endpoints:
        # Read only the tool list, with cursor pagination if advertised.
        cursor=None;seen_cursors=set();seen_names=set();pages=0;ep_tools=[];error=None
        while True:
            pages+=1;eid='hrdk-mcp-tools-list-accept' if ep['path']=='/mcp' and pages==1 else 'hrdk-mcp-tools-'+ep['path'].split('/')[-1]+'-page'+str(pages)
            body,receipt=fetch(eid,BASE+ep['path'],limit=2_000_000,accept='application/json, text/event-stream',
                json_body={'jsonrpc':'2.0','id':'catalog-metadata','method':'tools/list','params':{'cursor':cursor} if cursor else {}})
            if body is None:error='tools_list_fetch_unresolved';break
            try:
                result=rpc_result(body)
                for n,t in enumerate(result['tools']):
                    if not isinstance(t.get('name'),str) or t['name'] in seen_names or not isinstance(t.get('inputSchema'),dict):raise ValueError('tool_identity_or_schema_invalid')
                    seen_names.add(t['name']);ep_tools.append({'id':'hrdk-api:tool:'+ep['path']+':'+t['name'],
                        'portal_id':'hrdk-api','endpoint':BASE+ep['path'],'tool_name':t['name'],'source_contract':t,
                        'evidence_id':eid,'locator':f'JSON-RPC result.tools[{n}]','collected_at':receipt['retrieved_at'],
                        'tool_executed':False,'output_schema_present':'outputSchema' in t,'description_is_untrusted_source_text':True,
                        'input_parameters_are_not_dataset_columns':True})
                cursor=result.get('nextCursor')
                if cursor is None:break
                if not isinstance(cursor,str) or cursor in seen_cursors:raise ValueError('pagination_cursor_repeated_or_invalid')
                seen_cursors.add(cursor)
            except (ValueError,TypeError,KeyError) as exc:error=str(exc);break
        tools.extend(ep_tools);reports.append({**ep,'pages_received':pages,'tool_contracts':len(ep_tools),
            'list_exhausted':error is None,'error':error})
    # Contracts at different endpoints retain their endpoint namespace, even when names agree.
    dump(HERE/'inventory/hrdk-mcp-tool-contracts.json',{'generated_at':now(),'tools':tools,'endpoints':reports,
        'tools_call_executed':False,'same_named_tools_across_endpoints_equivalence_asserted':False})
    dump(HERE/'hrdk-mcp-collection-report.json',{'generated_at':now(),'scope':'hrdk-mcp-tool-metadata',
        'target_count':len(endpoints),'processed':len(reports),'queue_exhausted':all(x['list_exhausted'] for x in reports),
        'status_counts':{'tool_contract_occurrences':len(tools)},'endpoints':reports,
        'root_tool_count':reports[0]['tool_contracts'],'guide_root_tool_count_as_reported':41,
        'guide_open_api_count_as_reported':229,'guide_linked_api_count_as_reported':69,
        'root_tool_count_matches_guide':reports[0]['tool_contracts']==41,
        'source_guide_evidence_id':'hrdk-public-mcp-guide','documented_dataset_field_count_added':0,
        'all_columns_complete':False,'tools_call_executed':False,
        'input_property_occurrences':sum(len(t['source_contract']['inputSchema'].get('properties',{})) for t in tools),
        'output_schema_occurrences':sum(t['output_schema_present'] for t in tools)})
    return tools

if __name__=='__main__':
    print('HRDK_CATALOG',len(catalog()),flush=True)
    print('HRDK_MCP_CONTRACTS',len(tool_catalog()),flush=True)
