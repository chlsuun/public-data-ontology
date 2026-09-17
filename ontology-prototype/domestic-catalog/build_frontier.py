"""Turn observed external references into an evidence-backed follow-up queue."""
from common import *
from urllib.parse import urlsplit
from collections import Counter
import sqlite3

def main():
    started=time.monotonic()
    registry=read(HERE/'inventory/domestic-portals.json')
    known={}
    for p in registry['portals']:
        for k in ('requested_url','observed_final_url'):
            if p.get(k):known.setdefault(urlsplit(p[k]).hostname,[]).append(p['id'])
    references={};host_counts=Counter()
    def add(portal,dataset,url,eid,locator,label=None,schema_missing=None):
        parsed=urlsplit(url);host=parsed.hostname
        if parsed.scheme not in ('https','http') or not host:return
        license_page=host in ('www.kogl.or.kr','kogl.or.kr','ccl.cckorea.org','creativecommons.org')
        key=uid('external-ref',portal,dataset,url)
        references[key]={'id':key,'source_portal':portal,'source_dataset_key':dataset,
            'predicate':'referencesExternalPage','target_url':url,'target_host':host,
            'target_portal_candidates':sorted(set(known.get(host,[]))),
            'link_label':label,'evidence_id':eid,'locator':locator,
            'reference_kind':'license_reference' if license_page else 'external_page_reference',
            'same_dataset_asserted':False,'joinability_asserted':False,
            'source_schema_missing':schema_missing}
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3',timeout=60)
    source_portals=('data-go','daegu','mafra','busan','chungnam','jeonbuk','jeju','hrdk-api','foodsafety','forest','expressway','kspo')
    # The index already stores the original metadata without large field arrays.
    # Keep the same document scope and locators, and use its field_count directly.
    query='SELECT path,portal_id,field_count,metadata_json FROM schema_documents WHERE portal_id IN ('+','.join('?' for _ in source_portals)+')'
    for path,portal,field_count,metadata in db.execute(query,source_portals):
        if not path.startswith(portal+'-schema-'):continue
        d=json.loads(metadata)
        for link in d.get('outgoing_links',[]):
            add(d['portal_id'],d['dataset_key'],link['url'],link.get('evidence_id',d['evidence_id']),
                link.get('locator') or ('dataSetDetailListInfo.dataSetDetailList[].'+link['source_property'] if link.get('source_property') else '.value a[href]'),
                link.get('label'),not bool(field_count))
    for portal,key,eid,metadata in db.execute("SELECT portal_id,dataset_key,evidence_id,metadata_json FROM records WHERE portal_id IN ('incheon','daegu','mafra','ulsan')"):
        d=json.loads(metadata);url=d.get('external_reference_url')
        if url and url.startswith(('https://','http://')):
            add(portal,key,url,eid,d['locator']+({'incheon':'.pageUrl','daegu':'.dataUrl','mafra':'.exchn_data_url','ulsan':' .rsltit_box a@href'}[portal]))
    db.close()
    for item in references.values():
        if item['reference_kind']!='license_reference':host_counts[item['target_host']]+=1
    dest=HERE/'inventory/external-references.jsonl.gz';temp=dest.with_suffix('.gz.tmp')
    with gzip.open(temp,'wt',encoding='utf-8') as out:
        for item in references.values():out.write(json.dumps(item,ensure_ascii=False)+'\n')
    temp.replace(dest)
    frontier=[{'host':host,'observed_reference_count':n,'registered_portal_candidates':sorted(set(known.get(host,[]))),
        'status':'target_dataset_mapping_pending' if host in known else 'domestic_public_provider_classification_pending',
        'source_referral_is_not_ownership_or_dataset_identity_proof':True} for host,n in host_counts.most_common()]
    dump(HERE/'inventory/provider-discovery-frontier.json',{'generated_at':now(),'national_census_complete':False,
        'external_page_references':len(references),'non_license_hosts':len(frontier),'hosts':frontier,
        'source_mode':'indexed_schema_metadata_and_catalog_rows','elapsed_seconds':round(time.monotonic()-started,3)})
    print('External references',len(references),'non-license hosts',len(frontier),flush=True)

if __name__=='__main__':main()
