"""Collect referenced SGIS code tables and attach source-grounded parameter references."""
from common import *
import re

BASE='https://sgis.mods.go.kr/developer/html/openApi/api/dataCode/'

def parse_table(raw,name,eid):
    s=BeautifulSoup(raw,'html.parser');tables=s.select('table')
    if len(tables)!=1:raise ValueError('code_table_count_unexpected')
    t=tables[0];headers=[h.get_text(' ',strip=True) for h in t.select('thead th')]
    if not headers or not any('코드' in h for h in headers):raise ValueError('code_headers_missing')
    spans={};rows=[];trs=t.select('tbody tr');width=len(headers)
    for rn,tr in enumerate(trs):
        cells=tr.find_all(['td','th'],recursive=False);expanded=[];col=0;raw_cells=[]
        for cn,c in enumerate(cells):
            while col in spans and spans[col]['until']>rn:
                expanded.append(spans[col]['cell']);col+=1
            cs=int(c.get('colspan',1));rs=int(c.get('rowspan',1))
            if cs!=1 or rs<1 or rn+rs>len(trs) or col>=width:raise ValueError('unsupported_or_out_of_bounds_span')
            cell={'text':c.get_text(' ',strip=True),'source_row':rn,'source_cell':cn,'rowspan':rs,'colspan':cs,
                'locator':f'table[0] tbody tr[{rn}] cell[{cn}]'}
            raw_cells.append(cell);expanded.append(cell)
            if rs>1:spans[col]={'until':rn+rs,'cell':cell}
            col+=1
        while col in spans and spans[col]['until']>rn:expanded.append(spans[col]['cell']);col+=1
        if len(expanded)!=width:raise ValueError('expanded_code_row_width_mismatch')
        rows.append({'source_row':rn,'raw_cells':raw_cells,'logical_cells':expanded,'values':[c['text'] for c in expanded]})
    return {'id':'sgis:code-table:'+name,'source_name':name,'evidence_id':eid,'source_url':BASE+name+'.html',
        'title':s.title.get_text(' ',strip=True) if s.title else None,'headers':headers,'rows':rows,
        'status':'public_code_rows_observed','code_values_split_or_coerced':False,'same_code_system_as_other_portal_asserted':False,
        'scope_note':'Rows from a referenced public code table; merged-cell labels resolved by explicit HTML rowspan. Code strings, leading zeros, years and ranges remain unchanged.'}

def main():
    frontier=read(HERE/'inventory/sgis-code-table-frontier.json');lists=[];errors=[]
    for name in frontier['unique_code_table_names']:
        eid='sgis-code-table-'+name;raw,r=fetch(eid,BASE+name+'.html')
        if raw is None:errors.append({'name':name,'evidence_id':eid,'error':'code_table_fetch_unresolved'});continue
        try:lists.append(parse_table(raw,name,eid))
        except (ValueError,KeyError,TypeError) as exc:errors.append({'name':name,'evidence_id':eid,'error':str(exc)})
    by_name={c['source_name']:c for c in lists};r=read(HERE/'evidence/sgis-data-api-guide.json')
    guide=gzip.decompress((HERE/r['raw_file']).read_bytes());s=BeautifulSoup(guide,'html.parser');bindings=[]
    tables=s.select('table');table_positions={id(t):n for n,t in enumerate(tables)}
    for n,a in enumerate(s.select('a[onclick]')):
        match=re.match(r"\s*popup\('([^']+)'",a['onclick'])
        if not match:continue
        section=a.find_parent(class_='apiItem');tr=a.find_parent('tr');table=a.find_parent('table')
        if section is None or tr is None or table is None:raise ValueError('code_reference_not_in_api_parameter_row')
        title=section.select_one('dt.guide_title[id]');cells=tr.find_all(['th','td'],recursive=False);rn=next(i for i,x in enumerate(table.select('tbody tr')) if x is tr)
        name=match[1];code=by_name.get(name)
        bindings.append({'id':uid('code-ref','sgis',r['sha256'],title['id'],n),'source_portal_id':'sgis',
            'source_registration_id':'sgis-data-guide-'+title['id'],'source_dataset_key':'data-guide-'+title['id'],'source_guide_anchor':title['id'],
            'source_parameter_label':cells[0].get_text(' ',strip=True),'source_direction_caption':table.caption.get_text(' ',strip=True),
            'source_table_index':table_positions[id(table)],'source_row_index':rn,'evidence_id':'sgis-data-api-guide',
            'locator':f'a[onclick][{n}]@onclick','source_onclick':a['onclick'],'source_sha256':r['sha256'],
            'predicate':'referencesCodeList','target_code_table_id':'sgis:code-table:'+name,
            'target_evidence_id':code['evidence_id'] if code else None,'target_source_url':BASE+name+'.html',
            'status':'source_reference_observed' if code else 'code_table_unresolved','same_code_system_as_other_portal_asserted':False})
    for path in (HERE/'definitions').glob('sgis-schema-*.json'):
        d=read(path);d['code_list_references']=[b for b in bindings if b['source_dataset_key']==d['dataset_key']]
        d['code_list_reference_guide_sha256']=r['sha256'];dump(path,d)
    dump(HERE/'inventory/sgis-code-lists.json',{'generated_at':now(),'code_tables':lists,'errors':errors,'total_source_rows':sum(len(c['rows']) for c in lists),
        'all_referenced_public_tables_read':len(lists)==len(frontier['unique_code_table_names']) and not errors,'all_sgis_code_lists_complete':False})
    dump(HERE/'inventory/sgis-code-list-references.json',{'generated_at':now(),'references':bindings,'scope':'Explicit guide parameter references only, not cross-dataset code equivalence.'})
    report={'generated_at':now(),'scope':'SGIS public code tables explicitly referenced by DATA API guide','target_count':len(frontier['unique_code_table_names']),
        'processed':len(lists)+len(errors),'status_counts':{'code_tables_observed':len(lists),'unresolved':len(errors)},
        'code_rows':sum(len(c['rows']) for c in lists),'parameter_reference_occurrences':len(bindings),'columns_added':0,'queue_exhausted':True,
        'all_columns_complete':False,'all_sgis_code_lists_complete':False}
    dump(HERE/'sgis-codes-collection-report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
