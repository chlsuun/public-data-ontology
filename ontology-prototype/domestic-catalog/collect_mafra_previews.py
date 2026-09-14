"""Public file preview headers, with file-version provenance; never bulk files."""
from common import *
from queue_runner import run_queue
import re

ROUTE='https://data.mafra.go.kr/opendata/data/previewOpenDataWebFile.do'

def targets():
    dest=HERE/'inventory/mafra-preview-targets.json'
    if dest.exists():return read(dest)['datasets']
    rows=[];errors=[]
    for item in read(HERE/'inventory/mafra-catalog.json'):
        if item['kind']!='FILE':continue
        eid='mafra-schema-'+item['dataset_key'];receipt=read(HERE/'evidence'/(eid+'.json'))
        target={'dataset_key':item['dataset_key'],'source_data_id':item['source_data_id'],
            'detail_evidence_id':eid,'source_url':item['url'],'previews':[]}
        if receipt.get('status')!='fetched':
            target['discovery_status']='detail_fetch_unresolved';rows.append(target);continue
        soup=BeautifulSoup(gzip.decompress((HERE/receipt['raw_file']).read_bytes()),'html.parser')
        identity=soup.select_one('input#data_id')
        if not identity or identity.get('value')!=item['source_data_id']:
            target['discovery_status']='detail_identity_unresolved';rows.append(target);continue
        seen={}
        for pos,a in enumerate(soup.select('[onclick]')):
            if 'filePreview(' not in a['onclick']:continue
            m=re.fullmatch(r"filePreview\('([0-9]+)',\s*'([a-zA-Z0-9_]+)',\s*'([0-9]+)'\);?",a['onclick'].strip())
            if not m or m[1]!=item['source_data_id'] or '미리보기' not in a.get_text(' ',strip=True):
                errors.append({'dataset_key':item['dataset_key'],'onclick_index':pos,'issue':'unexpected_preview_button'});continue
            key=tuple(m.groups())
            if key in seen:
                seen[key]['repeated_button_occurrences'].append({'locator':f'[onclick][{pos}]@onclick','source_onclick':a['onclick']})
                continue
            target['previews'].append({'data_id':m[1],'file_ty_code':m[2],'file_sn':m[3],
                'locator':f'[onclick][{pos}]@onclick','source_onclick':a['onclick'],
                'source_file_row_text':a.parent.get_text(' ',strip=True),'repeated_button_occurrences':[]})
            seen[key]=target['previews'][-1]
        target['discovery_status']='preview_buttons_observed' if target['previews'] else 'no_preview_button_observed'
        rows.append(target)
    if errors:raise ValueError('preview_discovery_errors:'+json.dumps(errors))
    dump(dest,{'generated_at':now(),'datasets':rows,'dataset_count':len(rows),
        'preview_count':sum(len(r['previews']) for r in rows),'discovery_errors':errors,
        'request_method_evidence_id':'mafra-common-renewal-js','all_file_versions_complete':False})
    return rows

def collect(item):
    path=HERE/'definitions'/('mafra-file-previews-'+item['dataset_key']+'.json')
    if path.exists():return read(path)
    d={'portal_id':'mafra','dataset_key':item['dataset_key'],'dataset_kind':'FILE',
        # Distinct document evidence group avoids replacing the original detail schema.
        'evidence_id':item['detail_evidence_id'] if not item['previews'] else 'mafra-preview-'+
            '-'.join(item['previews'][0][k] for k in ('data_id','file_ty_code','file_sn')),
        'additional_evidence_ids':[item['detail_evidence_id'],'mafra-common-renewal-js'],
        'source_url':item['source_url'],'fields':[],'header_candidates':[],'preview_headers':[],
        'human_approved':False,'raw_values_checked':False,'all_columns_complete':False,
        'bulk_file_downloaded':False,'header_is_official_column_definition':False,'header_candidate_kind':'public_file_preview_thead',
        'status':'file_preview_not_available','discovery_status':item['discovery_status'],'collected_at':now(),'parser_version':2}
    # Without a preview, the original detail document already represents this outcome.
    if not item['previews']:
        if 'unresolved' in item['discovery_status']:d['status']=item['discovery_status']
        return d
    for version in item['previews']:
        if (ROOT/'.local/domestic-catalog/mafra-previews.stop').exists():
            d['status']='interrupted_before_preview_queue_finished'
            return d  # Receipts remain resumable; do not cache this as a finished dataset.
        eid='mafra-preview-'+'-'.join(version[k] for k in ('data_id','file_ty_code','file_sn'))
        body,r=fetch(eid,ROUTE,limit=2_000_000,form={k:version[k] for k in ('data_id','file_sn','file_ty_code')})
        out={**version,'evidence_id':eid,'status':'preview_fetch_unresolved','headers':[]}
        if eid not in d['additional_evidence_ids']:d['additional_evidence_ids'].append(eid)
        if body:
            try:
                x=json.loads(body)
                if isinstance(x,dict) and x.get('numberOfCells')==0 and x.get('listHead') is None and x.get('listRow') is None:
                    out.update(number_of_cells_as_reported=0,source_preview_row_count=0,source_head_is_null=True,source_rows_are_null=True,status='preview_header_empty')
                    d['preview_headers'].append(out)
                    continue
                if not isinstance(x,dict) or not isinstance(x.get('numberOfCells'),int) or not isinstance(x.get('listHead'),list) or not isinstance(x.get('listRow'),list):raise ValueError('unexpected_preview_structure')
                out.update(number_of_cells_as_reported=x['numberOfCells'],source_preview_row_count=len(x['listRow']))
                # Only listHead is rendered into <thead> by the official callback.
                for rn,cells in enumerate(x['listHead']):
                    if not isinstance(cells,list) or any(not isinstance(c,str) for c in cells):raise ValueError('non_string_header_cell')
                    for cn,c in enumerate(cells):
                        out['headers'].append({'value':c,'locator':f'listHead[{rn}][{cn}]','header_row':rn,'cell':cn,'evidence_id':eid})
                out['status']='preview_header_candidates_observed' if out['headers'] else 'preview_header_empty'
                d['header_candidates'].extend(h['value'] for h in out['headers'])
            except (ValueError,TypeError,KeyError) as exc:out.update(status='preview_parse_unresolved',error=str(exc),headers=[])
        d['preview_headers'].append(out)
    unresolved=any('unresolved' in x['status'] for x in d['preview_headers'])
    d['status']='preview_header_candidates_partial' if unresolved else 'preview_header_candidates_observed'
    if not d['header_candidates']:d['status']='preview_unresolved' if unresolved else 'preview_header_empty'
    dump(path,d);return d

if __name__=='__main__':run_queue('mafra-previews',targets(),collect,2)
