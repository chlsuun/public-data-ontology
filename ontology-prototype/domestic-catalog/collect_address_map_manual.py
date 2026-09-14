"""Preserve the downloadable map guide's input contract, without inventing outputs."""
from common import *
import io,zipfile,re
from pypdf import PdfReader

def main():
    path=HERE/'definitions/address-schema-c61cabf478ee5db6569a.json';definition=read(path)
    url=definition['guide_download_links_as_reported'][0]
    archive,receipt=fetch('address-map-guide-2021',url,limit=30_000_000)
    if not archive or not archive.startswith(b'PK'):raise ValueError('public_manual_archive_not_observed')
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        members=[m for m in zipped.infolist() if m.filename.endswith('.pdf')]
        if len(members)!=1 or members[0].file_size>10_000_000:raise ValueError('unexpected_manual_member')
        data=zipped.read(members[0]);member=members[0].filename
    eid='address-map-guide-pdf-2021';raw_file='evidence/'+eid+'.raw.gz'
    (HERE/raw_file).write_bytes(gzip.compress(data,mtime=0))
    dump(HERE/'evidence'/(eid+'.json'),{'id':eid,'requested_url':url,'retrieved_at':receipt['retrieved_at'],
        'status':'fetched','acquisition_method':'archive_member_extraction','derived_at':now(),
        'derived_from_evidence_id':receipt['id'],'archive_member':member,'content_type':'application/pdf',
        'sha256':sha256(data).hexdigest(),'bytes':len(data),'raw_file':raw_file})
    pages=[p.extract_text() or '' for p in PdfReader(io.BytesIO(data)).pages]
    if len(pages)!=29 or '파라미터 정보' not in pages[9]:raise ValueError('manual_layout_requires_review')
    inputs=[]
    pattern=re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s+(String|Integer)\s+([YN])\s+(\S+)\s+(.+)$',re.M)
    matches=list(pattern.finditer(pages[9]))
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(pages[9])
        inputs.append({'name':m[1],'datatype':m[2],'required_as_reported':m[3],'default_as_reported':m[4],
            'description':' '.join(pages[9][m.start(5):end].split()),'role':'request_parameter',
            'evidence_id':eid,'locator':f'PDF page 10, extracted text characters {m.start()}:{end}',
            'source_text':pages[9][m.start():end]})
    if len(inputs)!=14 or not any(p['name']=='confmKey' for p in inputs):raise ValueError('manual_request_table_incomplete')
    dump(HERE/'inventory/address-map-guide-text.json',{'evidence_id':eid,'archive_evidence_id':receipt['id'],
        'archive_member':member,'pages':[{'page':i+1,'text':t} for i,t in enumerate(pages)],
        'request_table':inputs,'output_schema_not_inferred_from_examples':True})
    definition['request_parameters']=inputs
    definition['additional_evidence_ids']=[receipt['id'],eid]
    definition['status']='public_manual_observed_output_schema_pending'
    definition['manual_review']={'evidence_id':eid,'pages':29,'page10_request_parameter_count':14,
        'response_field_table_observed':False,'delivery_description_as_reported':pages[2],
        'coordinate_reference_mentions':[{'page':13,'text':pages[12],'evidence_id':eid}],
        'identifier_case_note':'10페이지 표의 Keyword와 15페이지 예시의 keyword 표기를 그대로 보존; 동일 이름으로 임의 수정하지 않음',
        'data_api_called':False,'archive_members_executed':False}
    definition['manual_reviewed_at']=now();dump(path,definition)
    report=read(HERE/'address-collection-report.json');counts={};nfields=0
    for file in (HERE/'definitions').glob('address-schema-*.json'):
        d=read(file);counts[d['status']]=counts.get(d['status'],0)+1;nfields+=len(d['fields'])
    report.update(generated_at=now(),status_counts=counts,documented_field_occurrences=nfields)
    dump(HERE/'address-collection-report.json',report)
    print(json.dumps({'manual_pages':len(pages),'request_parameters':len(inputs),'documented_output_fields_added':0,'status':definition['status'],'sha256':sha256(data).hexdigest()},ensure_ascii=False))

if __name__=='__main__':main()
