"""Build the question-centred discovery model from reviewed metadata, offline."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit, quote

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent.parent/'.prototype-tools'))
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, SKOS, DCTERMS, OWL

def load(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def save(name,value): (ROOT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    observations=load('source-observations.json');reviews=load('source-reviews.json')
    obs={r['id']:r for r in observations};rev={r['id']:r for r in reviews}
    registry=json.loads((ROOT.parent/'national-catalog/portal-registry.json').read_text(encoding='utf-8'))
    policy=load('harness-policy.json')
    providers=[
      {'id':'provider-mods','label':'국가데이터처','short':'국가데이터처','type':'provider','url':'https://kosis.kr/','country_of_data':['KR'],'role':'KOSIS 목록에 명시된 자료 제공기관','evidence_ids':['kosis-migration']},
      {'id':'provider-oecd','label':'OECD','short':'OECD','type':'provider','url':'https://www.oecd.org/en/data.html','country_of_data':None,'role':'국제 비교 데이터 제공기관; 국가별 계열 범위 추가 확인','evidence_ids':['oecd-unemployment-web','oecd-housing-web']},
      {'id':'provider-wb','label':'World Bank','short':'World Bank','type':'provider','url':'https://data.worldbank.org/','country_of_data':None,'role':'WDI 제공기관; 해당 노동지표의 원출처는 ILO','evidence_ids':['wb-unemployment','wb-employment']}
    ]
    concepts=[
      {'id':'c-migration','label':'인구이동','short':'인구이동','definition':'지역 간 전입·전출·순이동을 구분한다. 청년 집단의 연령은 질문과 자료 정의를 맞춘다.'},
      {'id':'c-employment','label':'고용','short':'고용','definition':'취업과 실업을 구분한다. 실업률의 분모는 노동력, 고용률의 분모는 해당 인구다.'},
      {'id':'c-housing','label':'주거','short':'주거','definition':'주택가격·임대료 지수와 실제 계약 금액을 구분한다.'},
      {'id':'c-education','label':'교육·노동시장 이행','short':'교육·진로','definition':'졸업 후 이동과 교육·취업 참여 상태는 서로 다른 지표다.'}
    ]
    for c in concepts:c.update(type='concept',evidence_ids=['user-requirements'],status='curated')
    indicators=[
      ('i-in','전입자수','전입자수','c-migration','명','지역·연령·집계 기간의 경계 정의 필요',False),
      ('i-out','전출자수','전출자수','c-migration','명','청년 정의와 이동의 범위·중복 산정 기준 확인 필요',False),
      ('i-net','순이동자수','순이동자수','c-migration','명','순이동은 전입에서 전출을 뺀 방향을 사용; 순유출과 부호 구분',False),
      ('i-unemployment','청년 실업률','청년 실업률','c-employment','%','15~24세 계열과 국내 청년 정의를 자동 일치시키지 않음',False),
      ('i-employment','청년 고용률','청년 고용률','c-employment','%','15~24세 인구 대비 취업자 비중; 실업률과 분모가 다름',False),
      ('i-house','주택가격지수','주택가격지수','c-housing','index','실질·명목·기준연도·국가별 집계 방법 구분',False),
      ('i-rent','주택 임대료 지수','임대료 지수','c-housing','index','원화 월세 금액과 다름; 제공 계열의 실제 코드 확인 필요',False),
      ('i-graduate','대학 졸업 후 지역 이동','졸업 후 이동','c-education',None,'출신·졸업·취업 지역과 추적 기간을 포함한 자료가 필요',True),
      ('i-neet','청년 NEET 비율','NEET 비율','c-education','%','교육·취업·훈련 미참여 비율; 졸업 후 지역 이동의 대리변수로 확정하지 않음',True)
    ]
    indicator_nodes=[{'id':i,'label':label,'short':short,'type':'indicator','concept_id':c,'unit':unit,'definition':definition,'data_gap':gap,'evidence_ids':['user-requirements'] if i=='i-graduate' else ['oecd-neet-web'] if i=='i-neet' else [],'status':'curated_definition'} for i,label,short,c,unit,definition,gap in indicators]
    datasets=[]
    def dataset(id,label,short,provider,portal,source_id,source_url,evidence,**kwargs):
        value={'id':id,'label':label,'short':short,'type':'dataset','provider_id':provider,'portal_id':portal,
          'source_identifier':source_id,'source_url':source_url,'metadata_api_url':None,'data_api_url':None,
          'countries':None,'country_scope_status':'not_enumerated','temporal_coverage':{'start':None,'end':None},
          'temporal_resolution':None,'spatial_resolution':None,'population_definition':None,'unit':None,
          'schema_summary':[],'schema_status':'summary_only_not_full_schema','concept_ids':[],
          'version':None,'license_raw':None,'license_decision':'not_reviewed','evidence_ids':evidence,
          'metadata_status':'description_observed','data_api_tested':False,'raw_rows_stored':0,
          'join_status':'not_verified','discovery_use':'context_candidate','limitations':[]}
        value.update(kwargs);datasets.append(value);return value
    tables={t['table_id']:t for t in obs['kosis-migration']['tables']}
    for suffix,tid,short in [('flows','DT_1B26001','KOSIS 이동자수'),('net','DT_1B26002','KOSIS 순이동')]:
        dataset('d-kosis-'+suffix,tables[tid]['title'],short,'provider-mods','kosis',tid,
          'https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId='+tid,['kosis-migration','kosis-table-access'],
          countries=['KR'],country_scope_status='source_scope_observed',temporal_resolution='monthly',
          spatial_resolution='시군구',population_definition='성·5세 연령구간별; 구간 코드와 청년 선택 범위 미검증',
          unit='명 (지표명에 따른 해석; 원본 단위 코드 미검증)',
          schema_summary=['시군구','성','5세 연령구간','월','이동 관련 측정값'],
          schema_status='dimensions_from_table_title_not_column_introspection',concept_ids=['c-migration'],
          metadata_status='official_listing_and_id_observed',discovery_use='direct_measure_candidate',
          catalog_latest_period='2026-07',limitations=['원본 통계표 직접 조회·전체 기간·코드·단위 미검증','연령구간과 행정구역 버전을 확인해야 결합 가능'])
    for sid,node_id,short,concept in [('wb-unemployment','d-wb-unemployment','WB 청년 실업률','c-employment'),('wb-employment','d-wb-employment','WB 청년 고용률','c-employment')]:
        metadata=obs[sid]['metadata'][0]
        dataset(node_id,metadata['name'],short,'provider-wb','worldbank',metadata['id'],
          'https://data.worldbank.org/indicator/'+metadata['id'],[sid],metadata_api_url=obs[sid]['url'],
          population_definition='15~24세; ILO 모형 추정 계열',unit='%',spatial_resolution='국가·경제권',
          source_organization_raw=metadata['sourceOrganization'],unit_raw=metadata['unit'],
          schema_summary=['지표 ID','정의','원출처','주제'],schema_status='indicator_metadata_response_verified_not_observation_schema',
          concept_ids=[concept],metadata_status='metadata_api_verified',
          limitations=['국가별 제공 기간·빈도·관측값 응답 구조 미검증','국내 시군구 이동 통계와 직접 결합할 수 없음','국가 추정치·연령 정의·집계 방법의 차이를 확인해야 함'])
    for sid,node_id,short,concept in [('oecd-unemployment-web','d-oecd-unemployment','OECD 실업 통계','c-employment'),('oecd-housing-web','d-oecd-housing','OECD 주택가격','c-housing')]:
        review=rev[sid];query=parse_qs(urlsplit(review['dataset_url']).query)
        dataset(node_id,'Monthly unemployment rates' if 'unemployment' in sid else 'Analytical house price indicators',short,
          'provider-oecd','oecd',query['df[id]'][0],review['dataset_url'],[sid],version=query['df[vs]'][0],
          spatial_resolution='국가·지역 계열별 확인 필요',concept_ids=[concept],
          schema_summary=['국가·지역','시점','선택 지표','연령·성 또는 가격 계열; 코드 미검증'],
          schema_status='definition_and_link_summary_only',metadata_status='source_dataset_referral_observed',
          temporal_resolution='monthly' if 'unemployment' in sid else None,
          population_definition='청년 계열 선택 필요; 기본 링크는 15세 이상' if 'unemployment' in sid else '주택 가격 집계; 청년 전용 자료 아님',
          unit='%' if 'unemployment' in sid else 'index; 계열별 기준연도 확인 필요',
          limitations=[review['caveat'],'원본 관측값·국가별 범위·결합 조건 미검증'])
    queries=[
      {'id':'q-migration','label':'청년 인구 유출과 관련된 데이터를 찾아줘','short':'청년 인구 유출','type':'query','seed_concept':'c-migration','country':None,'age_range':None,'period':None,'interpretation_status':'curated_demo_not_live_llm','ambiguities':['청년 연령','대상 지역','관측 기간','전출과 순유출의 구별']},
      {'id':'q-employment','label':'청년 고용과 관련된 데이터를 찾아줘','short':'청년 고용','type':'query','seed_concept':'c-employment','country':None,'age_range':None,'period':None,'interpretation_status':'curated_demo_not_live_llm','ambiguities':['청년 연령','비교 국가·지역','관측 기간']},
      {'id':'q-housing','label':'주거비와 관련된 데이터를 찾아줘','short':'주거비','type':'query','seed_concept':'c-housing','country':None,'age_range':None,'period':None,'interpretation_status':'curated_demo_not_live_llm','ambiguities':['가격 수준과 지수','매매와 임대','지역·기간']}
    ]
    nodes=queries+concepts+indicator_nodes+datasets+providers
    relations=[]
    def relation(a,p,b,label,status,evidence,cost=0,priority=10,role='structural',note=''):
        relations.append({'id':'r-'+sha256((a+'|'+p+'|'+b).encode()).hexdigest()[:12],
          'source':a,'predicate':p,'target':b,'label':label,'status':status,'evidence_ids':evidence,
          'semantic_cost':cost,'priority':priority,'role':role,'note':note,'correlation_coefficient':None,'causal_claim':False})
    for q in queries:relation(q['id'],'interpretedAs',q['seed_concept'],'질문에서 해석','curated',['user-requirements'],1,0,'query_interpretation')
    for target in ['c-employment','c-housing','c-education']:
        relation('c-migration','explorationHypothesis',target,'함께 탐색할 가설','candidate',['user-requirements'],1,20,'context_hypothesis','통계적 상관·인과관계를 검증한 연결이 아님')
    relation('c-employment','explorationHypothesis','c-education','교육·취업 이행 탐색','candidate',['user-requirements'],1,25,'context_hypothesis')
    relation('c-education','explorationHypothesis','c-employment','고용 지표 함께 탐색','candidate',['user-requirements'],1,25,'context_hypothesis')
    for i in indicator_nodes:relation(i['concept_id'],'hasIndicator',i['id'],'측정할 지표','curated',['user-requirements'],0,5,'indicator_definition',i['definition'])
    mapping=[('i-in','d-kosis-flows','candidate'),('i-out','d-kosis-flows','candidate'),('i-net','d-kosis-net','documented'),
      ('i-unemployment','d-wb-unemployment','documented'),('i-unemployment','d-oecd-unemployment','candidate'),
      ('i-employment','d-wb-employment','documented'),('i-house','d-oecd-housing','documented'),('i-rent','d-oecd-housing','candidate')]
    dmap={d['id']:d for d in datasets}
    for a,b,status in mapping:relation(a,'availableFrom',b,'관련 자료 안내',status,dmap[b]['evidence_ids'],0,8,'metadata_mapping','자료 설명·목록 수준의 대응. 필요한 하위계열 선택과 결합은 별도 검증.')
    for d in datasets:relation(d['id'],'providedBy',d['provider_id'],'제공기관','documented',d['evidence_ids'],0,5,'source_provenance')
    sources=[{'id':r['id'],'url':r.get('url'),'status':r['status'],'checked_at':r['retrieved_at'],'snapshot':'source-observations.json','sha256':r.get('sha256')} for r in observations]
    sources += [{'id':r['id'],'url':r['source'] if r['source'].startswith('https://') else None,'status':r['status'],'checked_at':r.get('observed_at'),'snapshot':'source-reviews.json','summary':r.get('summary',r.get('basis'))} for r in reviews]
    sources[ next(i for i,s in enumerate(sources) if s['id']=='user-requirements') ]['sha256']=sha256((ROOT/'requirements-v0.3.md').read_bytes()).hexdigest()
    model={'version':'0.3.0','scope':{'target':'domestic_and_international_all_topics','catalog_scope_complete':False,'existing_domestic_service_entries':len(registry['services']),'new_international_entries':2,'example_dataset_records':len(datasets),'example_is_product_scope_limit':False},
      'description':'질문 → 개념 → 지표 → 자료 → 제공기관; 출처·상태가 있는 자체 관계 DB',
      'nodes':nodes,'relations':relations,'queries':queries,'datasets':datasets,'source_evidence':sources,
      'policy':policy,'live_llm_enabled':False,'raw_rows_stored':0,'statistical_correlations_computed':0,
      'known_gaps':['전 세계 제공처 전수조사 미완료','국내 122개 항목 전체 자료·컬럼 미수집','졸업 후 지역 이동 자료 미확보','OECD NEET 링크와 하위계열 대응 미확정','연령·시간·공간 기준 검토 후에만 비교·결합 가능']}
    save('model.json',model)
    thin=[{k:s[k] for k in ['id','research_name','requested_url','region','topics','observation_status']}|{'scope_origin':'domestic_v0.2','dataset_catalog_collected':False} for s in registry['services']]
    thin += [{'id':'oecd','research_name':'OECD Data Explorer','requested_url':'https://data-explorer.oecd.org/','region':'국제','topics':['전분야'],'observation_status':'indicator_referrals_observed','scope_origin':'international_v0.3','dataset_catalog_collected':False},
      {'id':'worldbank','research_name':'World Bank Open Data','requested_url':'https://data.worldbank.org/','region':'국제','topics':['전분야'],'observation_status':'selected_indicator_metadata_verified','scope_origin':'international_v0.3','dataset_catalog_collected':False}]
    save('source-registry.json',{'entries':thin,'complete':False,'note':'국내 조사 122개를 유지하고 국제 제공처 2개를 추가. 예시 자료 6개는 제품 범위의 제한이 아님.'})
    export_rdf(model)
    print(json.dumps({'nodes':len(nodes),'relations':len(relations),'example_datasets':len(datasets),'registry_entries':len(thin)},ensure_ascii=False))

def export_rdf(model):
    ex=Namespace('https://example.org/public-data-discovery/');dcat=Namespace('http://www.w3.org/ns/dcat#');foaf=Namespace('http://xmlns.com/foaf/0.1/')
    graph=Graph();graph.bind('discovery',ex);graph.bind('dcat',dcat);graph.bind('skos',SKOS);graph.bind('dct',DCTERMS)
    for name,label in [('QueryTopic','질문 주제'),('Indicator','측정 지표'),('RecommendationPath','추천 경로'),('ResourcePolicy','자원 정책'),('BudgetRun','예산을 적용한 실행')]:
        graph.add((ex[name],RDF.type,OWL.Class));graph.add((ex[name],RDFS.label,Literal(label,lang='ko')))
    types={'query':ex.QueryTopic,'concept':SKOS.Concept,'indicator':ex.Indicator,'dataset':dcat.Dataset,'provider':foaf.Organization}
    for n in model['nodes']:
        node=ex[n['id']];graph.add((node,RDF.type,types[n['type']]));graph.add((node,RDFS.label,Literal(n['label'])))
        if n.get('source_url'):graph.add((node,DCTERMS.source,URIRef(quote(n['source_url'],safe="/:?#[]@!$&'()*+,;=%"))))
    for source in model['source_evidence']:
        node=ex['evidence/'+source['id']];graph.add((node,RDF.type,Namespace('http://www.w3.org/ns/prov#').Entity))
        if source.get('url'):graph.add((node,DCTERMS.source,URIRef(source['url'])))
    for relation in model['relations']:
        node=ex[relation['id']];a=ex[relation['source']];p=ex[relation['predicate']];b=ex[relation['target']]
        graph.add((node,RDF.type,RDF.Statement));graph.add((node,RDF.subject,a));graph.add((node,RDF.predicate,p));graph.add((node,RDF.object,b))
        graph.add((node,ex.reviewStatus,Literal(relation['status'])))
        for sid in relation['evidence_ids']:graph.add((node,ex.evidence,ex['evidence/'+sid]))
        if relation['status']=='documented':graph.add((a,p,b))
    graph.serialize(ROOT/'discovery-ontology.ttl',format='turtle')

if __name__=='__main__':main()
