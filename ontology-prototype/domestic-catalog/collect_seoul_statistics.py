"""Recover Seoul S/2 statistical definitions through their public iframe chain."""
from common import *
from queue_runner import run_queue
from urllib.parse import urlencode,urlparse,parse_qs,urljoin
from openapi_schema import javascript_literal
import argparse,re

BASE='https://data.seoul.go.kr'

def scalar(source,name):
    match=re.search(r'\bvar\s+'+re.escape(name)+r'\s*=\s*',source)
    if not match:return None
    value,end=javascript_literal(source,match.end())
    if not source[end:].lstrip().startswith(';'):raise ValueError('scalar_assignment_boundary_unresolved')
    return value

def parse(data,org,tbl):
    text=data.decode('utf-8-sig');soup=BeautifulSoup(text,'html.parser')
    form=soup.select_one('form#ParamInfo')
    if not form:raise ValueError('statistics_form_not_observed')
    hidden={i.get('name'):i.get('value','') for i in form.select('input[type=hidden][name]')}
    if hidden.get('orgId')!=org or hidden.get('tblId')!=tbl:raise ValueError('statistics_identity_mismatch')
    axes={}
    for li in soup.select('#ulLeft > li, #ulRight > li'):
        key=li.select_one('input[type=hidden]');label=li.get_text(' ',strip=True)
        if key and label:
            code=key.get('value')
            if code in axes:raise ValueError('duplicate_axis_code')
            axes[code]={'name':label,'selector':'li#'+li.get('id','')}
    fields=[];issues=[]
    def field(name,code,role,selector,**extra):
        return dict(name=name,name_en=None,code=code,role=role,datatype=None,unit=None,description=None,
                    locator=selector,source_selector=selector,**extra)
    dimensions=soup.select('#tabMenu li[id^=tabClassText_]')
    expected=scalar(text,'g_classTabCnt')
    if expected is None or not expected.isdigit() or int(expected)!=len(dimensions):raise ValueError('dimension_count_mismatch')
    for tab in dimensions:
        inp=tab.select_one('input[name=naviInfo]');code=inp.get('value') if inp else None
        if code not in axes:
            issues.append({'dimension_code':code,'issue':'dimension_label_not_observed'});continue
        observed=[]
        for box in soup.select('input[type=checkbox][onclick]'):
            match=re.match(r"fn_classLvlChk\('([^']+)',\s*(\d+),\s*(\d+),\s*'([^']+)'",box['onclick'])
            if match and match[1]==code:
                observed.append({'code':match[4],'name':box.get('title'),'level_as_reported':match[3],
                    'value_as_reported':box.get('value'),'locator':'input#'+box.get('id','')})
        fields.append(field(axes[code]['name'],code,'statistical_dimension',axes[code]['selector'],
            observed_codes=observed,declared_code_count=None,code_list_complete=False,
            code_coverage_note='Only codes rendered in the initial public HTML; deeper levels may load on demand.'))
    measures=soup.select('input[name=itemChkLi]')
    declared=scalar(text,'g_tabItemCnt')
    for measure in measures:
        if not measure.get('title') or not measure.get('value'):raise ValueError('measure_label_or_code_missing')
        fields.append(field(measure['title'],measure['value'],'statistical_measure','input#'+measure['id'],
            source_attribute='title'))
    if declared is None or not declared.isdigit() or int(declared)!=len(measures):issues.append({'issue':'measure_list_count_unresolved','declared':declared,'observed':len(measures)})
    periods=[]
    for box in soup.select('input[name=headCheck]'):
        label=soup.find('label',attrs={'for':box.get('id')})
        if label:periods.append({'code':box.get('value'),'label_as_reported':label.get_text(' ',strip=True),
            'locator':'label[for="'+box['id']+'"]'})
    if periods:
        label=axes.get('TIME')
        if not label:raise ValueError('period_label_not_observed')
        fields.append(field(label['name'],'TIME','statistical_period',label['selector'],periods=periods))
    if not fields:raise ValueError('no_statistical_fields_observed')
    metadata={k:hidden.get(k) for k in ('orgId','tblId','tblNm','tblEngNm','statId','dbUser','periodStr')}
    metadata.update(table_unit_as_reported=scalar(text,'g_unitNm'),periods=periods,
        declared_dimension_count=int(expected),observed_dimension_count=len(dimensions),
        declared_measure_count=int(declared) if declared and declared.isdigit() else None,
        observed_measure_count=len(measures),measure_list_complete=declared==str(len(measures)),
        all_dimension_code_lists_complete=False)
    return fields,metadata,issues

def collect_one(original):
    key=original['dataset_key'];eid='seoul-statistics-'+key;path=HERE/'definitions'/(eid+'.json')
    if path.exists():return read(path)
    result={'portal_id':'seoul','dataset_key':key,'source_url':original['source_url'],
        'evidence_id':original['evidence_id'],'additional_evidence_ids':[original['evidence_id']],
        'fields':[],'status':'statistical_route_unresolved','human_approved':False,'raw_values_checked':False,
        'collected_at':now(),'parser_version':1,'previous_schema_file':'definitions/seoul-schema-'+key+'.json',
        'original_schema_status':original['status'],'javascript_executed':False,'observation_queries_executed':False}
    try:
        source,rc=fetch(original['evidence_id'],original['source_url'])
        if not source:raise ValueError('catalog_page_fetch_unresolved')
        soup=BeautifulSoup(source,'html.parser');form=soup.select_one('form#frm')
        if not form:raise ValueError('catalog_form_unresolved')
        inputs={i['name']:i.get('value','') for i in form.select('input[name]')}
        services=[v for v in original.get('advertised_services',[]) if v[1:] in (['S','2'],('S','2'))]
        if len(services)!=1 or inputs.get('infId')!=services[0][0]:raise ValueError('statistical_service_identity_unresolved')
        route=BASE+'/dataList/statSheetView.do?'+urlencode({'infId':services[0][0],'obj_var_id':'','up_itm_id':'','srvType':'S'})
        if '/dataList/statSheetView.do?infId=' not in source.decode('utf-8-sig'):raise ValueError('public_stat_route_not_in_source')
        body,rc=fetch(eid+'-view',route,form=inputs,referer=original['source_url'])
        result['attempted_view_evidence_id']=rc['id']
        if not body:raise ValueError('statistical_view_fetch_unresolved')
        result['additional_evidence_ids'].append(rc['id'])
        iframe=BeautifulSoup(body,'html.parser').select_one('iframe#IframeRequest[src]')
        if not iframe:raise ValueError('public_statistics_iframe_not_observed')
        url=urljoin(route,iframe['src']);parsed=urlparse(url);query=parse_qs(parsed.query)
        if parsed.scheme!='https' or parsed.hostname!='stat.eseoul.go.kr' or parsed.path!='/statHtml/statHtml.do':raise ValueError('unreviewed_statistical_iframe_location')
        org=query.get('orgId',[]);tbl=query.get('tblId',[])
        if len(org)!=1 or len(tbl)!=1 or tbl[0]!=inputs.get('tblId'):raise ValueError('iframe_table_identity_unresolved')
        result.update(source_url=url,evidence_id=eid+'-iframe',source_iframe_locator='iframe#IframeRequest@src',
            public_route_evidence_id=eid+'-view',source_institution_id=org[0],source_statistical_table_id=tbl[0],
            source_service_id=services[0][0],identity_relation_status='observed_navigation_reference_only')
        html,rc=fetch(result['evidence_id'],url,referer=route)
        if not html:raise ValueError('statistical_iframe_fetch_unresolved')
        fields,metadata,issues=parse(html,org[0],tbl[0]);result.update(fields=fields,dataset_metadata=metadata,issues=issues,
            status='statistical_definition_observed' if not issues else 'statistical_definition_observed_partial')
    except (ValueError,TypeError,KeyError) as exc:result.update(error=str(exc))
    dump(path,result);return result

def targets():
    result=[]
    for path in sorted((HERE/'definitions').glob('seoul-schema-*.json')):
        item=read(path)
        if not item.get('fields') and any(s[1:]==['S','2'] for s in item.get('advertised_services',[])):result.append(item)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);ap.add_argument('--workers',type=int,default=2);args=ap.parse_args()
    rows=targets();run_queue('seoul-statistics',rows[:args.limit] if args.limit else rows,collect_one,min(2,max(1,args.workers)),bool(args.limit))

if __name__=='__main__':main()
