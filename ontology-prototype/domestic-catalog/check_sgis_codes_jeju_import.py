"""Verify code references and new Jeju schemas in real local search."""
from common import *
from urllib.request import urlopen
from urllib.parse import urlencode
import sqlite3

def request(params):
    with urlopen('http://127.0.0.1:8766/api/search?'+urlencode(params),timeout=60) as r:return json.load(r)

def main():
    checks=[]
    def check(name,ok,details=None):checks.append({'name':name,'passed':bool(ok),'details':details})
    db=sqlite3.connect(ROOT/'.local/domestic-catalog/catalog.sqlite3',timeout=60)
    check('jeju_all_1259_registrations_searchable',request({'portal':'jeju'})['total']==1259)
    check('jeju_only_93_registrations_have_documented_response_fields',request({'portal':'jeju','documented':'yes'})['total']==93)
    count=db.execute("SELECT count(*) FROM documented_fields f JOIN records r ON r.id=f.record_id WHERE r.portal_id='jeju'").fetchone()[0]
    check('jeju_686_response_fields_in_db',count==686,count)
    result=request({'id':'jeju-1362'});fs=result['definitions']
    check('jeju_input_parameters_not_in_response_fields',len(fs)==7 and not ({'startDate','endDate'} & {f['name'] for f in fs}) and all(f['raw_definition']['source_parameter_record']['type']=='response' for f in fs))
    check('jeju_each_output_has_catalog_array_provenance',all(f['evidence_id']=='jeju-public-catalog-page1' and f['raw_definition']['locator'].startswith('data[3].dataApi.dataApiElements[') for f in fs))
    result=request({'id':'jeju-1364'})
    check('jeju_file_versions_not_misrepresented_as_column_definitions',not result['definitions'] and any({f['source_role'] for f in d.get('file_versions',[])}=={'dataset_file','dataset_preview'} for d in result['schema_documents']))
    check('jeju_source_owner_not_inferred_as_producing_agency',result['provider_name'] is None and result['provider_id'] is None)
    refs=read(HERE/'inventory/sgis-code-list-references.json')['references'];tables=read(HERE/'inventory/sgis-code-lists.json')['code_tables'];ids={t['id'] for t in tables}
    check('all_35_code_edges_resolve_to_real_catalog_records_and_code_lists',len({r['id'] for r in refs})==35 and all(r['target_code_table_id'] in ids and db.execute('SELECT 1 FROM records WHERE id=?',(r['source_registration_id'],)).fetchone() and not r['same_code_system_as_other_portal_asserted'] for r in refs))
    count=db.execute("SELECT count(*) FROM documented_fields f JOIN records r ON r.id=f.record_id WHERE r.portal_id='sgis'").fetchone()[0]
    check('sgis_code_rows_do_not_inflate_column_counts',count==618,count)
    result=request({'id':'sgis-data-guide-5'});bindings=[r for d in result['schema_documents'] for r in d.get('code_list_references',[])]
    check('actual_http_detail_exposes_age_code_reference',any(r['source_parameter_label']=='age_type' and r['target_code_table_id']=='sgis:code-table:PplAgeCode' and r['source_direction_caption']=='요청정보' for r in bindings))
    model=read(HERE/'model.json');check('ontology_model_declares_code_list_relation_and_instance_files','CodeList' in model['entity_types'] and any(r['predicate']=='referencesCodeList' for r in model['relation_types']) and model['instance_files']['code_lists']=='inventory/sgis-code-lists.json')
    index=read(HERE/'index-progress-report.json');coverage=read(HERE/'coverage-report.json')
    check('no_orphan_documents_or_false_completion_flags',not index['parse_errors'] and not index['unmatched_definition_documents'] and not coverage['all_columns_complete'] and not coverage['all_domestic_portals_complete'])
    db.close();report={'checked_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,'index_generated_at':index['generated_at'],'scope':'Jeju metadata and SGIS code-reference imports only; not full historical or observation-data validation.'}
    dump(HERE/'sgis-codes-jeju-import-check.json',report);print(json.dumps({'passed':report['passed'],'checks':len(checks),'failures':[c for c in checks if not c['passed']]},ensure_ascii=False),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
