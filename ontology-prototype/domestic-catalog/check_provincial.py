"""Point-in-time source and boundary QA for the two provincial adapters."""
from common import *
from collect_provincial import parse_catalog,parse_chungnam_detail
from urllib.parse import urlsplit,parse_qs,urljoin
import re

def source(eid):
    receipt=read(HERE/'evidence'/(eid+'.json'))
    raw=gzip.decompress((HERE/receipt['raw_file']).read_bytes())
    if sha256(raw).hexdigest()!=receipt['sha256']:raise ValueError('source_hash_mismatch:'+eid)
    return raw,receipt

def main():
    checks=[];source_ids=set()
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    def get(eid):source_ids.add(eid);return source(eid)
    snapshots={}
    for portal in ('chungnam','jeonbuk'):
        report=read(HERE/(portal+'-catalog-report.json'));items=read(HERE/'inventory'/(portal+'-catalog.json'));snapshots[portal]=report
        pages={};errors=[];seen=[]
        for r in items:
            eid=r['evidence_id']
            if eid not in pages:
                raw,receipt=get(eid);pages[eid]=(BeautifulSoup(raw,'html.parser'),receipt)
            soup,receipt=pages[eid];tr=soup.select('table.list01 tbody tr' if portal=='chungnam' else 'table.list tbody tr')[int(r['locator'].split('[')[-1].split(']')[0])]
            a=tr.select_one('td.title strong a' if portal=='chungnam' else 'td.subject a');url=urljoin(receipt['requested_url'],a['href']);query=parse_qs(urlsplit(url).query)
            if portal=='chungnam':
                field='apiIdx' if 'apiIdx' in query else 'publicdatapk';native=query[field][0]
                key=native if field=='apiIdx' else 'publicdatapk-'+native
            else:field='pId';key=native=query[field][0]
            seen.append(key)
            if r['dataset_key']!=key or r['source_registration_key']!=field or r['source_native_id']!=native or r['url']!=url or r['source_catalog_cells']!=[c.get_text(' ',strip=True) for c in tr.find_all('td',recursive=False)]:errors.append(r['id'])
        check(portal+'_all_catalog_rows_match_saved_originals',not errors and len(pages)==report['pages_received'],{'rows':len(items),'pages':len(pages),'failures':errors})
        check(portal+'_complete_catalog_reconciles_total_unique_ids_and_pages',report['snapshot_pagination_complete'] and len(seen)==len(set(seen))==report['reported_total'] and report['pages_received']==report['pages_expected'] and not report['errors'] and not report['duplicate_observations'])
        raw,receipt=get(portal+'-catalog-page');rejected=False
        try:parse_catalog(portal,raw,2,'test',receipt['requested_url'])
        except ValueError:rejected=True
        check(portal+'_wrong_page_rejected',rejected)
    raw,_=get('chungnam-schema-3199');soup,fields,issues,_=parse_chungnam_detail(raw,'3199')
    check('chungnam_literal_grid_has_four_explicit_columns',not issues and [(f['name'],f['name_en']) for f in fields]==[('연도','yr'),('시군명','sigun'),('성별','sx'),('선정 인원수','nope')])
    rejected=False
    try:parse_chungnam_detail(raw,'999999')
    except ValueError:rejected=True
    check('chungnam_wrong_detail_identity_rejected',rejected)
    text=raw.decode('utf-8-sig');first=fields[0]['source_literal'];push='columns.push('+first+');'
    # Source formatting varies outside the literal; derive the complete first push.
    pattern=r'columns\.push\(\s*'+re.escape(first)+r'\s*\)\s*;';match=re.search(pattern,text)
    if not match:raise ValueError('test_fixture_push_not_found')
    push=match[0]
    commented=text.replace(push,'/*\ncolumns.push({header:"FAKE",name:"fake"});\n*/\n'+push,1)
    _,fs,err,_=parse_chungnam_detail(commented.encode(),'3199')
    check('commented_columns_not_promoted',not err and len(fs)==4 and not any(f['name_en']=='fake' for f in fs))
    conditional=text.replace(push,'if (someRuntimeCondition) {\n'+push+'\n}',1)
    _,fs,err,_=parse_chungnam_detail(conditional.encode(),'3199')
    check('conditional_grid_setup_left_unresolved',not fs and bool(err))
    dynamic=text.replace(first,'makeColumnsAtRuntime()',1)
    _,fs,err,_=parse_chungnam_detail(dynamic.encode(),'3199')
    check('dynamic_grid_expression_never_executed_or_promoted',not fs and bool(err))
    docs=[read(p) for portal in ('chungnam','jeonbuk') for p in (HERE/'definitions').glob(portal+'-schema-*.json')]
    errors=[];count=0;versions=0;multiple_versions=0
    for d in docs:
        receipt=read(HERE/'evidence'/(d['evidence_id']+'.json'))
        if receipt['status']!='fetched':
            if d['fields']:errors.append(d['evidence_id'])
            continue
        raw,_=get(d['evidence_id']);s=BeautifulSoup(raw,'html.parser')
        scripts=s.select('script:not([src])');anchors=s.select('a[href]')
        for f in d['fields']:
            code=scripts[f['script_index']].string or scripts[f['script_index']].get_text();literal=code[f['start_char']:f['end_char']]
            if literal!=f['source_literal'] or f['source_grid_definition']['header']!=f['name'] or f['source_grid_definition']['name']!=f['name_en'] or f['role']!='displayed_sheet_column':errors.append(d['evidence_id'])
            count+=1
        for link in d.get('outgoing_links',[]):
            n=int(link['locator'].split('[')[-1].split(']')[0]);a=anchors[n]
            if urljoin(d['source_url'],a['href'])!=link['url'] or not (a.find_parent(class_='bbs_skin') or a.find_parent('article',class_='s_con')):errors.append(d['evidence_id'])
        original=[h['id'] for h in s.select('div#info_wrap > h4[id]')]
        stored=[x['source_resource_id'] for x in d.get('resource_versions',[])]
        if original!=stored or (d['portal_id']=='jeonbuk' and d['fields']) or d.get('all_file_versions_schema_complete'):errors.append(d['evidence_id'])
        versions+=len(stored);multiple_versions+=len(stored)>1
    check('current_fields_links_and_version_ids_trace_to_originals',not errors,{'documents':len(docs),'fields':count,'resource_versions':versions,'datasets_with_multiple_versions':multiple_versions,'failures':errors})
    check('multiple_versions_retained_and_not_asserted_same_schema',multiple_versions>0 and all(not x['schema_observed'] for d in docs for x in d.get('resource_versions',[])))
    check('national_and_all_column_completion_remain_false',all(not r['all_columns_complete'] and not r['all_portal_catalogs_complete'] for r in snapshots.values()))
    result={'checked_at':now(),'passed':all(x['passed'] for x in checks),'checks':checks,'source_receipts_checked':len(source_ids),
        'scope':'Saved catalog snapshots and currently stored provincial documents only; no observation quality, legal approval or statistical relationship validation.',
        'catalog_snapshot_times':{p:r['generated_at'] for p,r in snapshots.items()},'documents_checked':[d['evidence_id'] for d in docs]}
    dump(HERE/'provincial-adapter-check.json',result);print(json.dumps({'passed':result['passed'],'checks':len(checks),'failed':[x for x in checks if not x['passed']]},ensure_ascii=False),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
