"""Verify public schema variants and Seoul statistical navigation against sources."""
from common import *
from static_js_data import literal_value
from collect_seoul_statistics import parse
from check_finance_address_adapters import source
from urllib.parse import urlparse,parse_qs

def main():
    checks=[]
    def check(name,ok,details=None):checks.append(dict(name=name,passed=bool(ok),details=details))
    rejected=[]
    for expression in ('[{name:run()}]','[{name:unknown}]','[{name:1+2}]','[{name:`${run()}`}]','[{a:1,a:2}]','[trueThing]'):
        try:literal_value(expression)
        except ValueError:rejected.append(expression)
    check('expressions_identifiers_templates_and_duplicate_keys_rejected',len(rejected)==6)
    value,end=literal_value('[{no:1,column:"법정동코드",format:"문자",pk:!0,note:null}]')
    check('static_literals_preserve_korean_and_boolean_values',value[0]['column']=='법정동코드' and value[0]['pk'] is True)
    catalog=read(HERE/'inventory/address-db-catalog.json');docs=[read(p) for p in (HERE/'definitions').glob('address-db-schema-*.json')]
    check('address_all_public_categories_have_schema_documents',len(catalog)==len(docs)==31 and {d['dataset_key'] for d in docs}=={r['dataset_key'] for r in catalog})
    count=0;failures=[]
    for d in docs:
        raw,_=source(d['evidence_id']);text=raw.decode('utf-8');arrays={}
        for f in d['fields']:
            start=f['literal_start']
            if start not in arrays:arrays[start]=literal_value(text,start)
            values,end=arrays[start];item=values[f['array_ordinal']]
            if item!=f['source_definition'] or end!=f['literal_end'] or f['name']!=(item.get('comment') or item['column']) or f['datatype']!=item.get('format') or f['size_as_reported']!=item.get('size') or f['primary_key_annotation_as_reported']!=item.get('pk'):failures.append((d['dataset_key'],f['locator']))
            count+=1
    check('address_all_fields_resolve_to_exact_source_literals',not failures and count==1117,dict(fields_checked=count,failures=failures))
    by={d['dataset_key']:d for d in docs}
    check('address_two_layouts_not_flattened_into_one_file',[a['field_count'] for a in by['db/1']['schema_arrays']]==[24,14] and len({f['schema_variant_locator'] for f in by['db/1']['fields']})==2)
    check('address_grouped_spatial_layouts_preserved',len(by['db/25']['fields'])==44 and len({f['schema_variant_locator'] for f in by['db/25']['fields']})==11 and all(f['datatype'] is None and f['size_as_reported'] is None for f in by['db/25']['fields']))
    check('agency_classification_array_excluded_from_columns',len(by['db/30']['fields'])==9 and bool(by['db/30']['supporting_metadata_arrays']))
    check('release_flags_not_interpreted_as_download_permission',{r['release_flag_as_reported'] for r in catalog}=={'Y','N'} and all(r['download_access_review']=='not_inferred_from_metadata_visibility' for r in catalog))
    statdocs=[read(p) for p in (HERE/'definitions').glob('seoul-statistics-*.json') if read(p).get('fields')]
    failures=[];count=0
    for d in statdocs:
        raw,_=source(d['evidence_id']);soup=BeautifulSoup(raw,'html.parser')
        iframe,_=source(d['public_route_evidence_id']);node=BeautifulSoup(iframe,'html.parser').select_one('iframe#IframeRequest')
        if node['src']!=d['source_url']:failures.append((d['dataset_key'],'iframe_link'))
        query=parse_qs(urlparse(node['src']).query)
        if query['tblId']!=[d['source_statistical_table_id']] or not d['dataset_key'].startswith('OA-'):failures.append((d['dataset_key'],'identity'))
        for f in d['fields']:
            node=soup.select_one(f['source_selector'])
            label=node.get(f['source_attribute']) if f.get('source_attribute') else node.get_text(' ',strip=True)
            if label!=f['name']:failures.append((d['dataset_key'],f['locator']))
            count+=1
    check('seoul_fields_and_iframe_reference_match_real_html',bool(statdocs) and not failures,dict(documents_checked=len(statdocs),fields_checked=count,failures=failures))
    known=read(HERE/'definitions/seoul-statistics-OA-996.json');dim=next(f for f in known['fields'] if f['role']=='statistical_dimension')
    check('initial_dimension_codes_not_claimed_complete',dim['name']=='에너지종류별' and len(dim['observed_codes'])==4 and not dim['code_list_complete'] and known['dataset_metadata']['all_dimension_code_lists_complete'] is False)
    check('statistical_controls_excluded_from_fields',not any(f['name'] in ('orgId','tblId','view','dbUser','file') for d in statdocs for f in d['fields']) and all(not d['observation_queries_executed'] for d in statdocs))
    raw,_=source(known['evidence_id']);rejected=False
    try:parse(raw,'999','WRONG_TABLE')
    except ValueError as exc:rejected=str(exc)=='statistics_identity_mismatch'
    check('wrong_statistical_table_response_rejected',rejected)
    report=dict(checked_at=now(),passed=all(c['passed'] for c in checks),checks=checks,
        scope='Saved public schema literals, layout boundaries, statistical labels and navigation identity; not semantic or observation quality validation.')
    dump(HERE/'address-db-seoul-adapter-check.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
