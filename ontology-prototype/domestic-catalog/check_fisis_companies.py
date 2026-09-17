"""Verify all latest-month public company selector nodes against source JSON."""
from common import *
from collections import defaultdict,Counter


def main():
    receipts=[]
    def source(eid):
        r=read(HERE/'evidence'/(eid+'.json'));b=gzip.decompress((HERE/r['raw_file']).read_bytes())
        assert r['http_status']==200 and sha256(b).hexdigest()==r['sha256'] and len(b)==r['bytes']
        receipts.append(r);return b,r
    b,r=source('fisis-fsv302-20260914');s=BeautifulSoup(b,'html.parser')
    script='\n'.join(x.get_text() for x in s.select('script:not([src])'))
    assert "$('#slt0').val().substr(1)" in script and 'data: {partDiv: partDiv, baseMonth: baseMonth}' in script
    b,r=source('fisis-company-sectors-20260914');obj=json.loads(b);assert obj['err_cd']==0;sectors=obj['dataset'][0]['rows']
    requests=read(HERE/'inventory/fisis-company-selector-requests.json');assert [x['sector'] for x in requests]==sectors
    with gzip.open(HERE/'inventory/fisis-company-selector-records.jsonl.gz','rt',encoding='utf8') as inp:rows=[json.loads(x) for x in inp]
    expected=[]
    for req in requests:
        b,r=source(req['evidence_id']);o=json.loads(b);assert o['err_cd']==0;sec=req['sector']
        assert r['public_form_parameters']==req['params']=={'partDiv':sec['PART_DIV'][1:],'baseMonth':sec['ED_MONTH']}
        assert r['method']=='POST' and r['requested_url']=='https://fisis.fss.or.kr/fss/wa/fsv302_getFinanceList.do'
        d=o['dataset'][0];assert d['id']=='ds_financeList' and d['cols']==['FINANCE_CD','FINANCE_NM','FINANCE_DIV','LVL','STAT']
        for i,x in enumerate(d['rows']):expected.append((req['evidence_id'],f'/dataset/0/rows/{i}',x,sec['PART_DIV'],sec['ED_MONTH']))
    assert expected==[(x['evidence_id'],x['locator'],x['raw_source_row'],x['sector_code'],x['base_month']) for x in rows]
    assert all(not x['publishing_provider_identity_asserted'] and not x['cross_portal_identity_approved'] and not x['parent_relation_inferred'] for x in rows)
    duplicates=defaultdict(list)
    for x in rows:duplicates[x['selector_code']].append({'sector_code':x['sector_code'],'name':x['name_as_reported'],'locator':x['locator'],'evidence_id':x['evidence_id']})
    report=read(HERE/'fisis-companies-collection-report.json')
    assert len(rows)==report['selector_row_occurrences']==1468 and len(duplicates)==report['distinct_selector_codes']==1466
    assert dict(Counter(x['raw_source_row']['FINANCE_DIV'] for x in rows))==report['finance_div_counts_as_reported']
    result={'generated_at':now(),'passed':True,'checks':[
        'All 16 public selector sector/month pairs match observed source data and JavaScript request construction',
        'All 1468 selector occurrences equal raw JSON rows and exact source positions',
        'All 18 source receipts match SHA256 and byte counts',
        '1466 distinct source codes and source FINANCE_DIV counts reconcile; group rows preserved',
        'No individual-company classification, publishing-provider identity or cross-portal identity was asserted'],
        'source_receipts':[r['id'] for r in receipts],'row_occurrences':len(rows),'distinct_source_codes':len(duplicates),
        'codes_in_multiple_sector_positions':{code:items for code,items in duplicates.items() if len(items)>1},
        'base_month':'202603','historical_coverage_complete':False,'observation_values_requested':False}
    assert len(receipts)==18;dump(HERE/'fisis-companies-source-check.json',result)
    print(json.dumps({'passed':True,'checks':len(result['checks']),'receipts':len(receipts),'rows':len(rows),'codes':len(duplicates)},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
