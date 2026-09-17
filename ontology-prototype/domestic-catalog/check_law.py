"""Audit the complete captured LAW guide snapshot against source HTML and DB.

This is metadata provenance QA, not a legal-content or statistical quality test.
No remote requests are made. --import also verifies the existing local HTTP API.
"""
from common import *
from collections import Counter
from urllib.request import urlopen
import argparse, sqlite3, re, hashlib


def main(imported=False):
    checks=[];receipts={};docs=[];qa_issues=[]
    def check(name, condition, **details):
        checks.append({'name':name,'passed':bool(condition),**details})
        if not condition:raise AssertionError(name)
    def source(eid):
        r=read(HERE/'evidence'/(eid+'.json'))
        data=gzip.decompress((HERE/r['raw_file']).read_bytes())
        assert r['http_status']==200 and r['bytes']==len(data) and r['sha256']==hashlib.sha256(data).hexdigest()
        assert r['retrieved_at'] and r['requested_url'].startswith('https://open.law.go.kr/LSO/openApi/')
        receipts[eid]=r
        return BeautifulSoup(data,'html.parser')
    records=read(HERE/'inventory/law-catalog.json');by_key={r['dataset_key']:r for r in records}
    soup=source('law-guide-list-20260914');table=soup.select_one('table.blist')
    assert soup.select('table')[0] is table
    source_links={}
    for rn,tr in enumerate(table.select('tbody tr')):
        for cn,c in enumerate(tr.find_all(['td','th'],recursive=False)):
            for an,a in enumerate(c.select('a[onclick]')):
                key=re.fullmatch(r"javascript:openApiGuide\('([A-Za-z0-9_]+)'\);?",a['onclick'].strip())[1]
                assert key not in source_links
                source_links[key]={'title':a.get_text(' ',strip=True),'locator':f'table[0].tbody.tr[{rn}].cell[{cn}].a[{an}]@onclick'}
    check('Every advertised guide identifier, label and locator retained', len(records)==len(by_key)==195 and set(by_key)==set(source_links)
          and all(all(by_key[k][f]==v for f,v in item.items()) for k,item in source_links.items()), count=len(records))
    for record in records:
        rr=record['source_catalog_row'];rn=int(re.search(r'tr\[(\d+)\]',rr['locator'])[1])
        cells=table.select('tbody tr')[rn].find_all(['td','th'],recursive=False)
        assert [(c.get_text(' ',strip=True),int(c.get('rowspan',1)),int(c.get('colspan',1))) for c in cells]==[
            (c['text'],c['rowspan'],c['colspan']) for c in rr['source_cells']]
        if len(rr['expanded_cells'])!=4:assert not record['source_category_labels'] and record['source_category_status']=='span_layout_unresolved'
    check('Physical catalog cells and anomalous spans preserved without guessed categories',True)
    check('Provider label is guide publisher rather than inferred source agency',
          any('Copyright(c) 법제처 All rights reserved.' in x.get_text(' ',strip=True) for x in soup.select('p'))
          and all(r['provider_name']=='법제처' and r['provider_id'] is None and 'original legal-record producing agency not reconciled' in r['provider_name_role'] for r in records))
    catalog_qa=read(HERE/'law-catalog-report.json')
    check('Displayed total mismatch remains unresolved', int(soup.select_one('span.strong').get_text(strip=True))==catalog_qa['reported_total']==191
          and catalog_qa['observed_unique_guide_links']==195 and not catalog_qa['all_portal_catalogs_complete'])
    counts=Counter();issue_counts=Counter();response_count=request_count=blank_rows=0
    for key,record in by_key.items():
        d=read(HERE/'definitions'/('law-schema-'+key+'.json'));docs.append(d)
        s=source(d['evidence_id']);r=receipts[d['evidence_id']]
        assert r['method']=='POST' and r['public_form_parameters']['htmlName']==key
        assert d['catalog_locator']==record['locator'] and d['dataset_kind']==record['kind']
        assert d['parser_version']==2 and d['previous_parser_attempt']['parser_version']==1
        assert not any(d.get(x) for x in ('human_approved','raw_values_checked','observation_api_called','all_columns_complete'))
        counts[d['status']]+=1
        if d['issues']:qa_issues.append({'dataset_key':key,'evidence_id':d['evidence_id'],'issues':d['issues']})
        issue_counts.update(i['issue'] for i in d['issues'])
        response=[];request=[]
        for tn,t in enumerate(s.select('table')):
            caption=t.caption.get_text(' ',strip=True) if t.caption else ''
            if 'guide_table' in t.get('class',[]) or caption=='샘플':continue
            heads=[c.get_text(' ',strip=True) for c in t.select('thead th')]
            assert heads in (['필드','값','설명'],['요청변수','값','설명'])
            role='response' if '출력' in caption or heads[0]=='필드' else 'request'
            saved=next(x for x in d['definition_tables'] if x['table_index']==tn)
            assert saved['caption']==caption and saved['headers']==heads and saved['role']==role
            trs=t.select('tbody tr');assert len(saved['rows'])==len(trs)
            for rn,tr in enumerate(trs):
                physical=tr.find_all(['td','th'],recursive=False);saved_row=saved['rows'][rn]
                assert saved_row['locator']==f'table[{tn}].tbody.tr[{rn}]'
                assert [c['text'] for c in saved_row['source_cells']]==[c.get_text(' ',strip=True) for c in physical]
                if not physical:
                    blank_rows+=1;assert not saved_row['expanded_cells'];continue
                # Actual response/request source rows have three cells and no spans.
                assert len(physical)==3 and all(c.get('rowspan','1')=='1' and c.get('colspan','1')=='1' for c in physical)
                cells=[c.get_text(' ',strip=True) for c in physical]
                assert saved_row['expanded_cells']==cells
                (response if role=='response' else request).append((saved_row['locator'],cells))
        for rows,fields in [(response,d['fields']),(request,d['request_parameters'])]:
            assert len(rows)==len(fields)
            for (locator,cells),f in zip(rows,fields):
                assert (f['locator'],f['name'],f['source_type_as_reported'],f['description'])==(locator,*cells)
                assert f['unit'] is None and f['schema_path_status']=='row_label_as_reported_no_inferred_nesting'
        assert bool(response)==(d['status']=='response_definition_observed')
        if not response:assert request and d['status']=='response_definition_not_observed'
        response_count+=len(response);request_count+=len(request)
    check('196 source receipts match exact byte counts and SHA256',len(receipts)==196)
    check('Every response field and request row matches physical source cells',response_count==3210 and request_count==1968,
          response_fields=response_count,request_parameters=request_count)
    check('No-schema guides remain unresolved and blank structural rows are preserved',
          counts=={'response_definition_observed':180,'response_definition_not_observed':15} and blank_rows==1,status_counts=dict(counts))
    check('All repeated response labels remain separate source rows', all(Counter(f['name'] for f in d['fields'])==Counter(
          row['expanded_cells'][0] for t in d['definition_tables'] if t['role']=='response' for row in t['rows'] if row['expanded_cells']) for d in docs))
    report=read(HERE/'law-collection-report.json')
    check('Collection report reconciles with all captured guide documents',report['status_counts']==dict(counts) and report['documented_field_occurrences']==response_count
          and report['request_parameter_occurrences']==request_count and report['queue_exhausted'] and not report['all_columns_complete'])
    qa={'generated_at':now(),'portal_id':'law','scope':'195 explicit operation guide links in one captured public listing',
        'source_url':receipts['law-guide-list-20260914']['requested_url'],'listing_evidence_id':'law-guide-list-20260914',
        'collection_report':'law-collection-report.json','catalog_report':'law-catalog-report.json',
        'reported_total':191,'observed_guide_links':195,'official_total_reconciled':False,'status_counts':dict(counts),
        'response_field_occurrences':response_count,'request_parameter_occurrences':request_count,
        'measured_metadata_qa':{'guide_fetch_success':{'numerator':195,'denominator':195},
            'response_schema_observed':{'numerator':180,'denominator':195},
            'source_receipt_integrity':{'numerator':196,'denominator':196}},
        'issue_counts':dict(issue_counts),'guide_issues':qa_issues,
        'unresolved_response_guides':[{'dataset_key':d['dataset_key'],'title':by_key[d['dataset_key']]['title'],
            'evidence_id':d['evidence_id'],'next_action':'Investigate other official documentation or linked formal schemas; do not infer fields from examples.'}
            for d in docs if d['status']=='response_definition_not_observed'],
        'registration_identity_note':'Guide IDs identify documentation operations, not individual legal-content records.',
        'field_count_note':'Response-row occurrences include repeated names and API control fields, not unique analytical variables.',
        'raw_data_quality_scores':None,'license_reuse_review':'not_reviewed','semantic_approvals':0,'statistical_analyses':0,
        'all_portal_catalogs_complete':False,'all_columns_complete':False}
    dump(HERE/'law-source-qa.json',qa)
    source_check={'generated_at':now(),'passed':all(x['passed'] for x in checks),'checks':checks,
        'scope':qa['scope'],'source_receipts_verified':len(receipts),'observation_api_called':False}
    dump(HERE/'law-source-check.json',source_check)
    if imported:
        # The existing watcher imports definitions. This audit never writes the DB.
        dbpath=ROOT/'.local/domestic-catalog/catalog.sqlite3'
        db=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True,timeout=30);db.execute('BEGIN')
        before=len(checks)
        check('All LAW registrations equal the captured source catalog',
              [json.loads(x[0]) for x in db.execute("SELECT metadata_json FROM records WHERE portal_id='law' ORDER BY dataset_key")]
              ==sorted(records,key=lambda r:r['dataset_key']))
        expected=[]
        for d in docs:
            path='law-schema-'+d['dataset_key']+'.json'
            stored=db.execute('SELECT status,field_count,metadata_json FROM schema_documents WHERE path=?',(path,)).fetchone()
            assert stored and stored[0]==d['status'] and stored[1]==len(d['fields'])
            assert json.loads(stored[2])=={k:v for k,v in d.items() if k!='fields'}
            rid=by_key[d['dataset_key']]['id']
            rows=db.execute('SELECT definition_json FROM documented_fields WHERE record_id=? ORDER BY ordinal',(rid,)).fetchall()
            assert len(rows)==len(d['fields'])
            for ordinal,((text,),f) in enumerate(zip(rows,d['fields']),1):
                item=json.loads(text);assert item['raw_definition']==f and item['ordinal']==ordinal and item['evidence_id']==d['evidence_id']
                expected.append(item)
        check('All imported response rows and metadata equal version 2 documents',len(expected)==3210)
        dest=HERE/'inventory/law-columns-snapshot.jsonl.gz';tmp=dest.with_suffix('.gz.tmp')
        with gzip.open(tmp,'wt',encoding='utf8') as out:
            for item in expected:out.write(json.dumps(item,ensure_ascii=False)+'\n')
        tmp.replace(dest)
        with gzip.open(dest,'rt',encoding='utf8') as inp:actual=[json.loads(x) for x in inp]
        check('Portable LAW response-column export matches all imported rows',actual==expected)
        db.close()
        def http(path):
            with urlopen('http://127.0.0.1:8766'+path,timeout=30) as resp:return json.load(resp)
        check('Live search reports every guide and only observed-schema guides',
              http('/api/search?portal=law')['total']==195 and http('/api/search?portal=law&documented=yes')['total']==180)
        for key in ('lsEfYdListGuide','cgmExpcKcsListGuide','lsEngInfoGuide'):
            d=next(x for x in docs if x['dataset_key']==key);r=http('/api/search?id='+by_key[key]['id'])
            assert [x['raw_definition'] for x in r['definitions']]==d['fields']
            assert r['schema_documents'][0]['status']==d['status']
        check('Live detail preserves normal, header-conflict and missing-schema cases',True)
        check('Live progress includes LAW collection report',http('/api/progress')['reports']['law-collection-report.json']==report)
        coverage=http('/api/coverage');law=next(x for x in coverage['portal_counts'] if x['portal_id']=='law')
        check('Coverage and registry expose the latest LAW count',law['catalog_records']==195 and law['documented_columns']==3210
              and next(x for x in http('/api/portals')['portals'] if x['id']=='law')['current_collection']==law)
        dump(HERE/'law-import-check.json',{'generated_at':now(),'passed':True,'checks':checks[before:],
            'scope':'LAW 195 guides and 3210 response rows; no claim about other sources',
            'coverage_snapshot':coverage,'portable_export':'inventory/law-columns-snapshot.jsonl.gz'})
    print(json.dumps({'passed':True,'checks':len(checks),'status_counts':dict(counts),
          'response_fields':response_count,'request_parameters':request_count,'import_checked':imported},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser();ap.add_argument('--import',dest='imported',action='store_true')
    main(ap.parse_args().imported)
