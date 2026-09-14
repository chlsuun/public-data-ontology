"""Validate response direction, navigation identity and original field provenance."""
from common import *
from collect_chungnam_operations import parse_page,parse_parameters,GENERIC_NAMES
import copy,re

def main():
    checks=[];sources={}
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    def source(eid):
        if eid not in sources:
            r=read(HERE/'evidence'/(eid+'.json'));raw=gzip.decompress((HERE/r['raw_file']).read_bytes())
            if sha256(raw).hexdigest()!=r['sha256']:raise ValueError('source_hash_mismatch:'+eid)
            sources[eid]=(raw,r)
        return sources[eid]
    items={r['dataset_key']:r for r in read(HERE/'inventory/chungnam-catalog.json')}
    eid='chungnam-entity-metadata-probe-15157561';raw,r=source(eid);resource=r['public_form_parameters']['publicdatadetailpk'];name=r['public_form_parameters']['oprtinnm']
    fs,req,res,ex=parse_parameters(raw,resource,name,eid)
    check('first_api_response_request_and_generic_elements_separated',len(req)==1 and len(res)==22 and len(fs)==18 and len(ex)==4 and req[0]['source_row']['paramtrnm']=='serviceKey' and all(f['name_en']!='serviceKey' for f in fs))
    for label,payload,rid,op in [('wrong_resource',raw,'wrong',name),('wrong_operation',raw,resource,'wrong'),('unexpected_response_shape',b'{}',resource,name)]:
        rejected=False
        try:parse_parameters(payload,rid,op,eid)
        except ValueError:rejected=True
        check(label+'_rejected',rejected)
    data=json.loads(raw);data[1]['paramtrse']='unknown';rejected=False
    try:parse_parameters(json.dumps(data).encode(),resource,name,eid)
    except ValueError:rejected=True
    check('unknown_parameter_direction_rejected',rejected)
    parent='chungnam-schema-publicdatapk-15001170';raw,r=source(parent);item=items['publicdatapk-15001170'];page=parse_page(raw,item,parent)
    check('repeated_tab_ids_preserve_all_navigation_occurrences',len(page['tabs'])==16 and len({t['operation_id'] for t in page['tabs']})==4 and len({t['sheetorder'] for t in page['tabs']})==16)
    eid='chungnam-operation-page-probe-15001170-1';selected_raw,_=source(eid);p=parse_page(selected_raw,item,eid)
    check('actual_second_tab_selects_matching_operation',p['selected']['oprtinseqno']=='36293' and p['selected']['oprtinnm']=='청양 자동차통계')
    bad=copy.deepcopy(item);bad['source_native_id']='wrong';rejected=False
    try:parse_page(raw,bad,parent)
    except ValueError:rejected=True
    check('wrong_catalog_parent_rejected',rejected)
    text=raw.decode('utf-8-sig');text=re.sub(r'var\s+oprtinnm\s*=\s*"[^"\n]*";', 'var oprtinnm = runSomething();',text,count=1);rejected=False
    try:parse_page(text.encode(),item,parent)
    except ValueError:rejected=True
    check('dynamic_identity_expression_rejected_without_execution',rejected)
    docs=[read(p) for p in (HERE/'definitions').glob('chungnam-operations-*.json')];errors=[];counts={'documents':len(docs),'operations':0,'fields':0,'request_rows':0,'response_rows':0,'generic_elements_withheld':0,'repeated_tabs':0}
    for d in docs:
        raw,_=source('chungnam-schema-'+d['dataset_key']);page=parse_page(raw,items[d['dataset_key']],'chungnam-schema-'+d['dataset_key'])
        if d.get('operation_tabs')!=page['tabs']:errors.append((d['dataset_key'],'tab_list'))
        identities=[];mapped=[]
        for op in d['operations']:
            identities.append((op['source_resource_id'],op['operation_name']));counts['operations']+=1;counts['repeated_tabs']+=len(op['tab_occurrences'])-1
            for tab in op['tab_occurrences']:
                mapped.append(tab['tab_position']);raw,_=source(tab['selection_evidence_id']);page2=parse_page(raw,items[d['dataset_key']],tab['selection_evidence_id'])
                expected=page2['selected']
                if expected['publicdatadetailpk']!=op['source_resource_id'] or expected['oprtinnm']!=op['operation_name'] or expected['oprtinseqno']!=tab['operation_id']:errors.append((d['dataset_key'],'selected_identity'))
            receipt=read(HERE/'evidence'/(op['evidence_id']+'.json'))
            if receipt['status']!='fetched':continue
            raw,_=source(op['evidence_id']);rows=json.loads(raw)
            if op['status']!='response_definition_observed':continue
            counts['request_rows']+=len(op['request_parameters']);counts['response_rows']+=len(op['response_elements']);counts['generic_elements_withheld']+=len(op['excluded_generic_elements'])
            selected=[f for f in d['fields'] if f['evidence_id']==op['evidence_id']]
            if len(selected)!=op['field_count']:errors.append((d['dataset_key'],'field_count'))
            for f in selected:
                n=int(f['locator'][1:-1]);row=rows[n]
                if row!=f['source_parameter_record'] or row['paramtrse']!='응답변수' or row['paramtrnm']!=f['name_en'] or row['paramtrnm'].lower() in GENERIC_NAMES or row['publicdatadetail']!=f['source_resource_id']:errors.append((d['dataset_key'],'field_source'))
                counts['fields']+=1
        if len(identities)!=len(set(identities)) or len(mapped)!=len(set(mapped)):errors.append((d['dataset_key'],'duplicate_definition_or_tab'))
        if d.get('all_visible_operation_tabs_inspected') and len(mapped)!=len(d['operation_tabs']):errors.append((d['dataset_key'],'missing_tabs'))
        if d['all_columns_complete'] or d['all_versions_complete'] or d['human_approved']:errors.append((d['dataset_key'],'unsupported_completion'))
    check('stored_operation_fields_and_all_tab_occurrences_match_originals',not errors,{**counts,'errors':errors})
    result={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,'source_receipts_checked':len(sources),'documents_checked':[d['dataset_key'] for d in docs],
        'scope':'Point-in-time public operation metadata and original source identity checks. No observation quality, semantic joins or correlation validation.'}
    dump(HERE/'chungnam-operations-source-check.json',result);print(json.dumps({'passed':result['passed'],'checks':len(checks),'counts':counts,'failures':[c for c in checks if not c['passed']]},ensure_ascii=False),flush=True)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
