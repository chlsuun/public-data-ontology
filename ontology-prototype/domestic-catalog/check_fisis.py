"""Audit a captured FISIS metadata snapshot; no external requests or DB writes."""
from common import *
from collections import Counter,defaultdict
from urllib.request import urlopen
import argparse,re


def main(imported=False):
    checks=[];receipts={};sources={}
    def check(name,condition,**details):
        checks.append({'name':name,'passed':bool(condition),**details})
        if not condition:raise AssertionError(name)
    def source(eid):
        if eid in sources:return sources[eid]
        r=read(HERE/'evidence'/(eid+'.json'));receipts[eid]=r
        if r['status']!='fetched':return None
        body=gzip.decompress((HERE/r['raw_file']).read_bytes())
        assert len(body)==r['bytes'] and sha256(body).hexdigest()==r['sha256'] and r['http_status']==200
        assert r['retrieved_at'] and r['requested_url'].startswith('https://fisis.fss.or.kr/')
        sources[eid]=body;return body
    def js(eid):return json.loads(source(eid))
    paths=read(HERE/'inventory/fisis-catalog-paths.json');records=read(HERE/'inventory/fisis-catalog.json')
    queue=read(HERE/'inventory/fisis-definition-queue.json');catalog=read(HERE/'fisis-catalog-report.json')
    script=source('fisis-stats-ui-101-20260914').decode('utf8')
    intro=BeautifulSoup(source('fisis-api-intro-20260914'),'html.parser')
    page=BeautifulSoup(source('fisis-fsv101-20260914'),'html.parser')
    check('Catalog and metadata request paths originate in the public selector script',
          any(t.get('src')=='../js/stats-ui-101.js?v=202606221702' for t in page.select('script[src]'))
          and all('/fss/wa/'+x+'.do' in script for x in catalog['request_paths_allowlisted']))
    sectors=js('fisis-sectors-20260914')['dataset'][0]['rows']
    check('Every public financial sector is retained',sectors==paths['sectors'] and len(sectors)==22)
    expected_categories=[]
    for sector in sectors:
        eid='fisis-categories-'+sector['GROUP_LRG_DIV']+'-20260914';obj=js(eid);assert obj['err_cd']==0
        for i,row in enumerate(obj['dataset'][0]['rows']):expected_categories.append((eid,f'/dataset/0/rows/{i}',row))
    check('All public category rows have exact source locations',expected_categories==[
          (x['evidence_id'],x['locator'],x['category']) for x in paths['category_paths']] and len(expected_categories)==241)
    actual_requests={tuple(x['params'].items()) for x in paths['catalog_requests']}
    check('Every observed category selector has a catalog request',actual_requests=={
          tuple(x['request'].items()) for x in paths['category_paths']} and len(actual_requests)==241)
    by_source=defaultdict(list)
    for occurrence in paths['occurrences']:by_source[occurrence['evidence_id']].append(occurrence)
    for request in paths['catalog_requests']:
        obj=js(request['evidence_id']);assert obj['err_cd']==0;rows=obj['dataset'][0]['rows']
        observed=by_source[request['evidence_id']]
        assert rows==[x['source'] for x in observed] and len(rows)==request['row_count']
        assert [x['locator'] for x in observed]==[f'/dataset/0/rows/{i}' for i in range(len(rows))]
    expected=defaultdict(list)
    for x in paths['occurrences']:expected[x['source']['FORM_NO']].append(x)
    check('All 1205 catalog-path occurrences retained in 736 report identities',len(paths['occurrences'])==1205
          and len(records)==736 and {r['dataset_key']:r['catalog_source_rows'] for r in records}==dict(expected))
    variants=defaultdict(list)
    for x in paths['occurrences']:
        s=x['source'];variants[(s['FORM_NO'],s['ST_DAY'][:6],s['ED_DAY'][:6])].append(x)
    check('Definition queue uses exact published report identifiers and periods',len(queue)==736 and dict(variants)=={
          (q['form_no'],q['start_month'],q['end_month']):q['source_rows'] for q in queue})
    check('Exhausted selectors are not presented as a reconciled portal census',catalog['selector_traversal_exhausted']
          and not catalog['failures'] and not catalog['official_total_available'] and not catalog['all_portal_catalogs_complete'])
    spec=BeautifulSoup(source('fisis-api-spec-20260914'),'html.parser');tables=spec.select('table');api_docs=[];api_count=0;request_count=0
    for f in sorted((HERE/'definitions').glob('fisis-api-schema-*.json')):
        d=read(f);api_docs.append(d);assert not d['sample_response_promoted_to_fields'] and not d['keyed_api_called']
        for table in d['definition_tables']:
            t=tables[table['table_index']];assert t.caption.get_text(' ',strip=True)==table['caption']
            trs=t.select('tbody tr');assert len(trs)==len(table['rows'])
            for tr,row in zip(trs,table['rows']):
                assert [c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]==[c['text'] for c in row['source_cells']]
        fields=[]
        for table in d['definition_tables']:
            if table['caption'].startswith('결과변수 표:'):
                for row in table['rows']:
                    cs=row['expanded_cells'];fields.append((cs[0] or cs[1],cs[2],row['locator']))
        assert fields==[(f['name'],f['description'],f['locator']) for f in d['fields']]
        assert all(f['datatype'] is None and f['unit'] is None for f in d['fields'])
        api_count+=len(fields);request_count+=len(d['request_parameters'])
    check('Four API documents retain exact response rows and separate inputs',len(api_docs)==4 and api_count==41 and request_count==19)
    broken=next(d for d in api_docs if d['dataset_key']=='api-statisticsListSearch')
    check('Malformed API classification rowspan remains unresolved',broken['status']=='response_definition_observed_code_table_partial'
          and len(broken['issues'])==1 and broken['issues'][0]['table_index']==8 and tables[8].select('tbody tr')[-1].td.get('rowspan')=='2')
    docs=[];statuses=Counter();metadata_statuses=Counter();issues=Counter();field_count=glossary_count=0
    # Files are captured once so a running collector does not expand this audit mid-run.
    snapshot_paths=sorted((HERE/'definitions').glob('fisis-schema-*.json'))
    for path in snapshot_paths:
        d=read(path);docs.append((path.name,d));body=source(d['evidence_id'])
        assert not d['observation_values_requested'] and not d['human_approved'] and not d['all_columns_complete']
        if body and d['status'] not in ('parse_unresolved','fetch_unresolved'):
            obj=json.loads(body);assert obj['err_cd']==0 and obj['dataset']==d['item_response_datasets']
            fields=[]
            for di,ds in enumerate(obj['dataset']):
                if ds['id'] not in ('ds_rowItem','ds_colItem'):continue
                rn_axis=ds['id']=='ds_rowItem'
                for ri,s in enumerate(ds['rows']):
                    code=s.get('ROW_CD' if rn_axis else 'DB_COL_NM');name=s.get('ROW_NM' if rn_axis else 'COL_NM')
                    if code and name:fields.append((name,code,f'/dataset/{di}/rows/{ri}',s))
            assert fields==[(x['name'],x['name_en'],x['locator'],x['raw_source_row']) for x in d['fields']]
            assert all(x['unit'] is None and x['datatype'] is None and not x['parent_inferred']
                       and x['source_data_type_code']==x['raw_source_row'].get('DATA_TYPE') for x in d['fields'])
        b=source(d['metadata_evidence_id'])
        if b and d.get('metadata_status')=='metadata_document_observed':
            s=BeautifulSoup(b,'html.parser');ts=s.select('table');terms=[]
            assert len(ts)==len(d['metadata_tables'])
            for table,t in zip(d['metadata_tables'],ts):
                assert table['caption']==(t.caption.get_text(' ',strip=True) if t.caption else '')
                rows=[tr for tr in t.select('tr') if tr.find_parent('table') is t]
                assert len(rows)==len(table['rows'])
                for rn,(rr,tr) in enumerate(zip(table['rows'],rows)):
                    cells=tr.find_all(['td','th'],recursive=False)
                    assert [c['text'] for c in rr['cells']]==[c.get_text(' ',strip=True) for c in cells]
                    assert rr['locator']==f"table[{table['table_index']}].tr[{rn}]"
                    if table['caption']=='용어해설' and len(cells)==2 and any(c.name=='td' for c in cells) and cells[0].get_text(' ',strip=True):
                        terms.append((cells[0].get_text(' ',strip=True),cells[1].get_text(' ',strip=True),rr['locator']))
            assert terms==[(x['term_as_reported'],x['definition_as_reported'],x['locator']) for x in d['glossary_terms']]
            assert all(x['mapping_to_statistical_item']=='not_approved' for x in d['glossary_terms'])
        statuses[d['status']]+=1;metadata_statuses[d.get('metadata_status')]+=1;issues.update(x['issue'] for x in d.get('item_issues',[]))
        field_count+=len(d['fields']);glossary_count+=len(d.get('glossary_terms',[]))
    check('Captured statistical items, periods and metadata cells match public sources',bool(docs),documents=len(docs),items=field_count,glossary_terms=glossary_count)
    endpoints={'fsv101_getLrgDiv.do','fsv101_getSmlDiv.do','fsv101_getReportList.do','fsv102_getRowList.do','fsv102_metadata.do'}
    check('Verified receipts cover documentation and allowed public metadata only',all('/openapi/' not in r['requested_url'] and
          ('/fss/wa/' not in r['requested_url'] or urlsplit(r['requested_url']).path.rsplit('/',1)[-1] in endpoints) for r in receipts.values()),receipts=len(receipts))
    notes=[p.get_text(' ',strip=True) for p in intro.select('p') if '국가승인통계' in p.get_text() or '업무보고서' in p.get_text()]
    qa={'generated_at':now(),'scope':'Captured FISIS public metadata snapshot; concurrent worker may have progressed further',
        'catalog_report':'fisis-catalog-report.json','report_count':736,'api_operation_count':4,
        'audited_statistical_documents':len(docs),'statistical_item_occurrences':field_count,'glossary_term_occurrences':glossary_count,
        'api_response_field_occurrences':api_count,'api_request_parameter_occurrences':request_count,
        'status_counts':dict(statuses),'metadata_status_counts':dict(metadata_statuses),'item_issue_counts':dict(issues),
        'source_integrity_receipts_verified':len(sources),'source_failure_receipts':[eid for eid,r in receipts.items() if r['status']!='fetched'],
        'source_cautions_as_reported':notes,'source_cautions_evidence_id':'fisis-api-intro-20260914',
        'api_classification_issues':broken['issues'],'raw_data_quality_scores':None,'license_reuse_review':'not_reviewed',
        'code_identity_note':'Public UI sector/report/account IDs and Open API codes are not equated automatically. DATA_TYPE and CAL_UNIT remain source codes, not inferred storage types or units.',
        'semantic_approvals':0,'statistical_analyses':0,'all_columns_complete':False,'all_domestic_portals_complete':False}
    dump(HERE/'fisis-source-qa.json',qa)
    dump(HERE/'fisis-source-check.json',{'generated_at':now(),'passed':True,'checks':checks,'snapshot_definition_files':[n for n,d in docs],
        'definition_sha256':{n:sha256((HERE/'definitions'/n).read_bytes()).hexdigest() for n,d in docs},'receipt_ids':sorted(receipts)})
    if imported:
        start=len(checks);dbfile=ROOT/'.local/domestic-catalog/catalog.sqlite3';db=sqlite3.connect(dbfile.as_uri()+'?mode=ro',uri=True,timeout=30);db.execute('BEGIN')
        check('DB contains every statistical report and documented API operation',db.execute("SELECT count(*) FROM records WHERE portal_id='fisis'").fetchone()[0]==740)
        export=[]
        for name,d in docs+[(f'fisis-api-schema-{x["dataset_key"][4:]}.json',x) for x in api_docs]:
            stored=db.execute('SELECT field_count,metadata_json FROM schema_documents WHERE path=?',(name,)).fetchone()
            assert stored and stored[0]==len(d['fields']) and json.loads(stored[1])=={k:v for k,v in d.items() if k!='fields'},name
            rid='fisis-'+d['dataset_key'];found=[json.loads(x[0]) for x in db.execute('SELECT definition_json FROM documented_fields WHERE record_id=? AND evidence_id=? ORDER BY ordinal',(rid,d['evidence_id']))]
            assert [x['raw_definition'] for x in found]==d['fields'],name
            export.extend(found)
        db.close()
        check('Every audited item and metadata document matches the live DB',len(export)==field_count+api_count)
        dest=HERE/'inventory/fisis-audited-columns-snapshot.jsonl.gz';tmp=dest.with_suffix('.gz.tmp')
        with gzip.open(tmp,'wt',encoding='utf8') as out:
            for item in export:out.write(json.dumps(item,ensure_ascii=False)+'\n')
        tmp.replace(dest)
        with gzip.open(dest,'rt',encoding='utf8') as inp:assert [json.loads(line) for line in inp]==export
        check('Portable snapshot retains every audited response/statistical item',True,rows=len(export))
        glossary=[]
        for name,d in docs:
            for ordinal,term in enumerate(d.get('glossary_terms',[]),1):
                glossary.append({'portal_id':'fisis','dataset_key':d['dataset_key'],'stated_period':d['stated_period'],
                    'entry_kind':'source_glossary_entry','ordinal':ordinal,**term,
                    'source_url':d['metadata_source_url'],'evidence_id':d['metadata_evidence_id'],
                    'collected_at':d['collected_at'],'is_approved_ontology_concept':False})
        dest=HERE/'inventory/fisis-glossary-snapshot.jsonl.gz';tmp=dest.with_suffix('.gz.tmp')
        with gzip.open(tmp,'wt',encoding='utf8') as out:
            for item in glossary:out.write(json.dumps(item,ensure_ascii=False)+'\n')
        tmp.replace(dest)
        with gzip.open(dest,'rt',encoding='utf8') as inp:assert [json.loads(line) for line in inp]==glossary
        check('Separate glossary export retains source, period and unapproved status',len(glossary)==glossary_count,rows=len(glossary))
        def http(path):
            with urlopen('http://127.0.0.1:8766'+path,timeout=30) as r:return json.load(r)
        check('Live HTTP search includes 740 FISIS registrations',http('/api/search?portal=fisis')['total']==740)
        sample=http('/api/search?id=fisis-SDSA001V');d=next(d for n,d in docs if d['dataset_key']=='SDSA001V')
        check('Live HTTP item and glossary details retain source text',
              [f['raw_definition'] for f in sample['definitions']]==d['fields'] and sample['schema_documents'][0]['glossary_terms']==d['glossary_terms'])
        dump(HERE/'fisis-import-check.json',{'generated_at':now(),'passed':True,'checks':checks[start:],
            'audited_statistical_documents':len(docs),'field_occurrences':len(export),
            'scope':'Exact source-check snapshot; newer worker documents may not yet be indexed','source_check':'fisis-source-check.json'})
    print(json.dumps({'passed':True,'checks':len(checks),'documents':len(docs),'statistical_items':field_count,'glossary_terms':glossary_count,
        'receipts':len(receipts),'import_checked':imported},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');ap=argparse.ArgumentParser();ap.add_argument('--import',dest='imported',action='store_true');main(ap.parse_args().imported)
