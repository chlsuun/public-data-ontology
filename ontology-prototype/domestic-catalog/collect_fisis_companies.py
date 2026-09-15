"""Preserve public company selector codes, including aggregate/group nodes.

No company financial values or contact details are requested. Selector rows are
kept separate from public-data publishing institutions and individual companies.
"""
from common import *
from collections import Counter


def main():
    url='https://fisis.fss.or.kr/page/fsv302.jsp';body,r=fetch('fisis-fsv302-20260914',url)
    if body is None:raise ValueError('Public company selector page unavailable')
    soup=BeautifulSoup(body,'html.parser');script='\n'.join(s.get_text() for s in soup.select('script:not([src])'))
    assert '/fss/wa/fsv302_getPartDiv.do' in script and '/fss/wa/fsv302_getFinanceList.do' in script
    assert "$('#slt0').val().substr(1)" in script and 'data: {partDiv: partDiv, baseMonth: baseMonth}' in script
    b,r=fetch('fisis-company-sectors-20260914','https://fisis.fss.or.kr/fss/wa/fsv302_getPartDiv.do',form={},referer=url)
    if b is None:raise ValueError('Company sector selector unavailable')
    obj=json.loads(b);assert obj['err_cd']==0;sectors=obj['dataset'][0]['rows'];records=[];failures=[];requests=[]
    for sector in sectors:
        part=sector['PART_DIV'];month=sector['ED_MONTH'];params={'partDiv':part[1:],'baseMonth':month}
        eid=f'fisis-companies-{part}-{month}-20260914';endpoint='https://fisis.fss.or.kr/fss/wa/fsv302_getFinanceList.do'
        b,r=fetch(eid,endpoint,form=params,referer=url);requests.append({'sector':sector,'params':params,'evidence_id':eid})
        if b is None:failures.append({'evidence_id':eid,'status':r['status']});continue
        try:
            obj=json.loads(b);assert obj['err_cd']==0
            ds=obj['dataset'][0];assert ds['id']=='ds_financeList' and ds['cols']==['FINANCE_CD','FINANCE_NM','FINANCE_DIV','LVL','STAT']
            for rn,raw in enumerate(ds['rows']):
                records.append({'portal_id':'fisis','selector_code':raw['FINANCE_CD'],'name_as_reported':raw['FINANCE_NM'],
                    'sector_code':part,'base_month':month,'raw_source_row':raw,'evidence_id':eid,'source_url':endpoint,
                    'source_page_url':url,'locator':f'/dataset/0/rows/{rn}',
                    'entity_type':'source_company_selector_node_not_individually_classified',
                    'source_code_namespace':'FISIS company selector FINANCE_CD','publishing_provider_identity_asserted':False,
                    'cross_portal_identity_approved':False,'parent_relation_inferred':False})
        except (ValueError,KeyError,AssertionError) as exc:failures.append({'evidence_id':eid,'status':'parse_unresolved','issue':str(exc)})
    dest=HERE/'inventory/fisis-company-selector-records.jsonl.gz';tmp=dest.with_suffix('.gz.tmp')
    with gzip.open(tmp,'wt',encoding='utf8') as out:
        for row in records:out.write(json.dumps(row,ensure_ascii=False)+'\n')
    tmp.replace(dest)
    dump(HERE/'inventory/fisis-company-selector-requests.json',requests)
    report={'generated_at':now(),'scope':'Latest stated month per sector in the public company selector; not all historical periods',
        'target_count':len(sectors),'processed':len(sectors),'remaining':0,'status_counts':{'sector_lists_observed':len(sectors)-len(failures),'unresolved':len(failures)},
        'selector_row_occurrences':len(records),'distinct_selector_codes':len({x['selector_code'] for x in records}),
        'finance_div_counts_as_reported':dict(Counter(x['raw_source_row']['FINANCE_DIV'] for x in records)),
        'observed_base_months':sorted({x['base_month'] for x in records}),'failures':failures,
        'queue_exhausted':True,'all_historical_company_lists_complete':False,'all_columns_complete':False,
        'company_values_requested':False,'count_note':'Company selection contains grouping/aggregate nodes; row count is not an independently verified company count.',
        'script_evidence_id':'fisis-fsv302-20260914','inventory':'inventory/fisis-company-selector-records.jsonl.gz'}
    dump(HERE/'fisis-companies-collection-report.json',report);print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
