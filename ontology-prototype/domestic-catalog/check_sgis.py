"""Check complete SGIS guide-body extraction against table cells and menu targets."""
from common import *
from collect_sgis import parse,EID,URL

def main():
    checks=[]
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    r=read(HERE/'evidence'/(EID+'.json'));raw=gzip.decompress((HERE/r['raw_file']).read_bytes());s=BeautifulSoup(raw,'html.parser');tables=s.select('table')
    check('source_sha256_matches',sha256(raw).hexdigest()==r['sha256'])
    records=read(HERE/'inventory/sgis-catalog.json');docs=[read(HERE/'definitions'/('sgis-schema-'+x['dataset_key']+'.json')) for x in records];report=read(HERE/'sgis-catalog-report.json')
    check('all_guide_body_sections_and_identifiers_retained',len(records)==len(docs)==len(s.select('.apiItem'))==68 and len({d['guide_anchor'] for d in docs})==68)
    errors=[];fields=0;requests=0;unresolved=0;artifacts=0
    for item,d in zip(records,docs):
        section=s.select('.apiItem')[d['guide_position']];title=section.select_one('dt.guide_title');endpoint=section.select_one('dd.guide_url').get_text(' ',strip=True)
        if title['id']!=d['guide_anchor'] or title.get_text(' ',strip=True)!=item['title'] or endpoint!=item['documented_api_url'] or d['source_url']!=URL+'#'+title['id']:errors.append(item['dataset_key'])
        for collection in ['fields','request_parameters','response_artifacts','unresolved_response_rows']:
            for row in d[collection]:
                table=tables[row['table_index']];tr=table.select('tbody tr')[row['row_index']];cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]
                if cells!=row['source_cells'] or section not in table.parents:errors.append(item['dataset_key'])
                direction='요청정보' if collection=='request_parameters' else '응답정보'
                if table.caption.get_text(' ',strip=True)!=direction:errors.append(item['dataset_key'])
                if collection=='fields' and (cells[0]!=row['name'] or cells[1]!=row['source_value_or_type'] or cells[2]!=row['description']):errors.append(item['dataset_key'])
        fields+=len(d['fields']);requests+=len(d['request_parameters']);unresolved+=len(d['unresolved_response_rows']);artifacts+=len(d['response_artifacts'])
    check('all_fields_requests_and_exceptions_trace_to_original_cells',not errors,{'fields':fields,'requests':requests,'unresolved_rows':unresolved,'artifact_rows':artifacts,'errors':errors})
    response_rows=sum(len(t.select('tbody tr')) for t in tables if t.caption and t.caption.get_text(' ',strip=True)=='응답정보')
    check('response_rows_accounted_for_without_missing_or_invented_cells',fields==618 and requests==244 and fields+unresolved+artifacts==response_rows==620)
    broken=[d for d in docs if d['unresolved_response_rows']]
    check('nonrectangular_type_row_retained_as_unresolved',len(broken)==1 and broken[0]['unresolved_response_rows'][0]['source_cells'][0]=='type' and len(broken[0]['unresolved_response_rows'][0]['source_cells'])==2)
    population=next(d for d in docs if d['guide_anchor']=='4')
    check('population_example_wrapper_not_added_to_response_schema',not ({'errCd','errMsg','trId'} & {f['name'] for f in population['fields']}) and any(f['name']=='tot_ppltn' for f in population['fields']))
    script=next(d for d in docs if d['guide_anchor']=='2')
    check('javascript_artifact_not_counted_as_physical_column',not script['fields'] and len(script['response_artifacts'])==1)
    check('menu_anchors_without_sections_remain_unresolved',len({x['target_anchor'] for x in report['menu_targets_without_api_section']})==8 and any(x['target_anchor']=='106' and x['label']=='도시권 목록' and x['section_title']=='소지역 코드찾기' for x in report['menu_title_mismatches']) and not report['all_navigation_targets_resolved'])
    rejected=False
    try:parse(raw.replace('응답정보'.encode(),'잘못된표제'.encode(),1))
    except ValueError:rejected=True
    # First text occurrence is a section label, so alter a table caption explicitly if needed.
    if not rejected:
        try:parse(raw.replace('<caption>응답정보</caption>'.encode(),'<caption>잘못된표제</caption>'.encode(),1))
        except ValueError:rejected=True
    check('unexpected_response_table_caption_rejected',rejected)
    check('no_api_execution_or_national_completion_claim',all(not d['api_called'] and not d['raw_values_checked'] and not d['all_columns_complete'] for d in docs) and not report['all_portal_catalogs_complete'])
    result={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'All 68 body sections of the saved public SGIS data API guide; no authenticated API calls and no claim that unresolved menu targets or other SGIS catalogs are complete.'}
    dump(HERE/'sgis-source-check.json',result);print(json.dumps({'passed':result['passed'],'checks':len(checks),'failures':[x for x in checks if not x['passed']]},ensure_ascii=False))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
