"""Collect explicitly advertised LAW OPEN DATA guides, never legal-content APIs.

Guide IDs identify documentation operations, not individual laws or decisions.
The source's reported total, malformed spans and repeated field names remain QA
observations; they do not become invented catalog rows or approved relationships.
"""
from common import *
from catalog_storage import row, store_catalog
from collect_grac import grid
from collections import Counter
from urllib.parse import urljoin
import re

LIST_URL='https://open.law.go.kr/LSO/openApi/guideList.do'
LIST_EID='law-guide-list-20260914'
PORTAL='law'
PARSER_VERSION=2


def catalog(body):
    soup=BeautifulSoup(body,'html.parser')
    form=soup.select_one('form#openApiForm')
    script='\n'.join(s.get_text() for s in soup.select('script:not([src])'))
    if form is None or form.get('method','').lower()!='post' or '"action","guideResult.do"' not in script:
        raise ValueError('Unrecognized documentation form')
    if form.select_one('input[name=htmlName]') is None or 'function openApiGuide(htmlName)' not in script:
        raise ValueError('Guide parameter not documented by source UI')
    table=soup.select_one('table.blist')
    physical=table.select('tbody tr');expanded=grid(table,0)
    records=[];issues=[];seen=set()
    for rn,tr in enumerate(physical):
        rr=expanded[rn]
        if len(rr['expanded_cells'])!=4:
            issues.append({'issue':'catalog_source_span_width_differs_from_four_column_header','locator':rr['locator'],
                'expanded_width':len(rr['expanded_cells']),'raw_source_row':rr,'automatic_category_correction':False})
        for cn,cell in enumerate(tr.find_all(['td','th'],recursive=False)):
            for an,a in enumerate(cell.select('a[onclick]')):
                match=re.fullmatch(r"javascript:openApiGuide\('([A-Za-z0-9_]+)'\);?",a['onclick'].strip())
                if not match:raise ValueError('Unrecognized guide onclick')
                key=match[1]
                if key in seen:raise ValueError('Duplicate guide key needs explicit reconciliation')
                seen.add(key)
                records.append(row(PORTAL,key,a.get_text(' ',strip=True),LIST_URL,LIST_EID,
                    kind='public_api_operation_definition',provider_name='법제처',
                    locator=f'table[0].tbody.tr[{rn}].cell[{cn}].a[{an}]@onclick',
                    source_guide_key=key,source_onclick=a['onclick'],source_catalog_row=rr,
                    provider_name_role='guide_publisher_as_reported_in_footer; original legal-record producing agency not reconciled',
                    source_category_labels=rr['expanded_cells'][:2] if len(rr['expanded_cells'])==4 else [],
                    source_category_status='explicit_html_spans_not_semantically_approved' if len(rr['expanded_cells'])==4 else 'span_layout_unresolved',
                    documentation_request={'url':urljoin(LIST_URL,'guideResult.do'),'method':'POST',
                        'form':{'openApi':'','htmlName':key}},
                    registration_identity_basis='htmlName documentation identifier; not a law/decision/dataset instance identifier'))
    reported=soup.select_one('span.strong')
    reported_total=int(reported.get_text(strip=True)) if reported and reported.get_text(strip=True).isdigit() else None
    if reported_total!=len(records):
        issues.append({'issue':'displayed_total_differs_from_explicit_guide_links','reported_total':reported_total,
            'observed_unique_guide_links':len(records),'missing_or_extra_rows_invented':False})
    return records,{'reported_total':reported_total,'observed_unique_guide_links':len(records),
        'all_explicit_table_links_captured':len(records)==len(table.select('a[onclick]')),'issues':issues}


def parse(body):
    soup=BeautifulSoup(body,'html.parser')
    result={'fields':[],'request_parameters':[],'definition_tables':[],'issues':[],
        'guide_headings':[h.get_text(' ',strip=True) for h in soup.select('h3')],
        'example_urls_not_requested':[],'sample_content_promoted_to_fields':False}
    response_tables=0
    for tn,table in enumerate(soup.select('table')):
        caption=table.caption.get_text(' ',strip=True) if table.caption else ''
        headers=[c.get_text(' ',strip=True) for c in table.select('thead th')]
        if '샘플' in caption or 'guide_table' in table.get('class',[]):
            result['example_urls_not_requested'] += [a.get('href') for a in table.select('a[href]') if a['href'].startswith(('http://','https://'))]
            continue
        if '출력' in caption and headers in (['필드','값','설명'],['요청변수','값','설명']):
            role='response';response_tables+=1
            if headers[0]=='요청변수':
                result['issues'].append({'issue':'response_caption_request_header_conflict','table_index':tn,
                    'caption':caption,'headers':headers,'classification_basis':'explicit output caption; source header preserved'})
        elif headers==['요청변수','값','설명'] and ('요청' in caption or not caption):role='request'
        elif headers==['필드','값','설명'] and not caption:role='response';response_tables+=1
        else:
            result['issues'].append({'issue':'unclassified_documentation_table','table_index':tn,'caption':caption,'headers':headers,
                'text_as_reported':table.get_text(' ',strip=True)})
            continue
        rows=grid(table,tn)
        result['definition_tables'].append({'table_index':tn,'caption':caption,'headers':headers,'role':role,'rows':rows})
        for source in rows:
            cells=source['expanded_cells']
            if not source['source_cells'] and not cells:
                result['issues'].append({'issue':'empty_source_table_row_preserved','role':role,'source_row':source})
                continue
            if len(cells)!=3 or not cells[0]:
                result['issues'].append({'issue':'unexpected_definition_row_shape','role':role,'source_row':source});continue
            token=re.match(r'^(string|String|int|integer|long|char|float|double|boolean|date)\b',cells[1])
            name=cells[0]
            f={**source,'name':name,'name_en':name if re.fullmatch(r'[A-Za-z0-9_ .\-/]+',name) else None,
                'datatype':token[1] if token else None,'source_type_as_reported':cells[1],
                'description':cells[2],'unit':None,'schema_path_status':'row_label_as_reported_no_inferred_nesting'}
            if role=='request':result['request_parameters'].append(f)
            else:
                f['role']='api_response_control' if name in ('target','section','page','totalCnt','totalCount','numOfRows','resultCode','resultMsg') else 'api_response_column'
                result['fields'].append(f)
    repeated={k:n for k,n in Counter(f['name'] for f in result['fields']).items() if n>1}
    if repeated:result['issues'].append({'issue':'repeated_response_labels_preserved_by_source_row','labels':repeated,'nested_paths_invented':False})
    if not response_tables:result['issues'].append({'issue':'response_definition_table_not_observed'})
    structural_observations={'repeated_response_labels_preserved_by_source_row',
        'response_caption_request_header_conflict','empty_source_table_row_preserved'}
    unresolved=[i for i in result['issues'] if i['issue'] not in structural_observations]
    if not response_tables and result['request_parameters'] and all(i['issue']=='response_definition_table_not_observed' for i in unresolved):
        result['status']='response_definition_not_observed'
        result['schema_gap_note']='The captured guide documents requests but no response field table. This is unresolved coverage, not proof that no schema exists elsewhere.'
    else:
        result['status']='response_definition_observed' if response_tables and not unresolved else 'response_definition_partial' if result['fields'] else 'parse_unresolved'
    return result


def main():
    started=now();body,receipt=fetch(LIST_EID,LIST_URL)
    if body is None:raise ValueError('LAW guide listing unavailable; no catalog replaced')
    records,qa=catalog(body)
    store_catalog(PORTAL,records)
    dump(HERE/'inventory/law-catalog.json',records)
    dump(HERE/'law-catalog-report.json',{'generated_at':now(),'evidence_id':LIST_EID,'source_url':LIST_URL,**qa,
        'all_portal_catalogs_complete':False,'scope':'All explicit API guide links in the captured public guide table, not all legal-content records'})
    statuses=Counter();fields=inputs=0;done=0
    def report():
        result={'generated_at':now(),'started_at':started,'scope':'law-public-api-documentation-guides','target_count':len(records),
            'processed':done,'remaining':len(records)-done,'status_counts':dict(statuses),'documented_field_occurrences':fields,
            'request_parameter_occurrences':inputs,'queue_exhausted':done==len(records),'all_columns_complete':False,'pid':os.getpid()}
        dump(HERE/'law-collection-report.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
    report()
    for record in records:
        if (ROOT/'.local/domestic-catalog/law.stop').exists():break
        key=record['dataset_key'];path=HERE/'definitions'/('law-schema-'+key+'.json')
        old=read(path) if path.exists() else None
        if old and old.get('parser_version')==PARSER_VERSION:d=old
        else:
            eid='law-guide-'+key+'-20260914';req=record['documentation_request']
            data,r=fetch(eid,req['url'],form=req['form'],referer=LIST_URL)
            d={'portal_id':PORTAL,'dataset_key':key,'dataset_kind':record['kind'],'source_url':req['url'],'evidence_id':eid,
                'catalog_evidence_id':LIST_EID,'catalog_locator':record['locator'],'documentation_request':req,
                'collected_at':now(),'parser_version':PARSER_VERSION,'fields':[],'request_parameters':[],
                'status':'fetch_unresolved','human_approved':False,'raw_values_checked':False,'observation_api_called':False,
                'all_columns_complete':False}
            if data is not None:
                try:d.update(parse(data))
                except (ValueError,IndexError) as exc:d.update(status='parse_unresolved',error=str(exc)[:400])
            else:d['fetch_issue']={k:r.get(k) for k in ['status','http_status','error']}
            if old:
                d['previous_parser_attempt']={k:old.get(k) for k in ('parser_version','collected_at','status','issues')}
                d['previous_parser_attempt']['field_count']=len(old.get('fields',[]))
                d['previous_parser_attempt']['request_parameter_count']=len(old.get('request_parameters',[]))
            dump(path,d)
        statuses[d['status']]+=1;fields+=len(d.get('fields',[]));inputs+=len(d.get('request_parameters',[]));done+=1
        if done%10==0:report()
    report()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
