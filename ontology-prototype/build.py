"""Build the RDF model, portable graph, and human handoff from reviewed metadata."""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '.prototype-tools'))
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD, SKOS, DCTERMS, FOAF

model = json.loads((HERE / 'model.json').read_text(encoding='utf-8'))
EX = Namespace(model['namespace'])
DCAT = Namespace('http://www.w3.org/ns/dcat#')
g = Graph()
for prefix, ns in [('ex', EX), ('dcat', DCAT), ('skos', SKOS), ('dcterms', DCTERMS), ('foaf', FOAF), ('owl', OWL)]:
    g.bind(prefix, ns)

class_defs = {
    'Portal': ('포털의 데이터 목록', DCAT.Catalog),
    'Organization': ('운영·제공·작성 기관', FOAF.Organization),
    'Dataset': ('자료 자체', DCAT.Dataset),
    'CatalogRecord': ('사이트에 등록된 자료 설명', DCAT.CatalogRecord),
    'Concept': ('분야·지표·공간의 개념', SKOS.Concept),
    'Source': ('확인한 근거 문서', None),
    'Claim': ('근거와 상태를 가진 관계 주장', RDF.Statement),
    'JoinAssessment': ('자료 간 결합 검토', None),
    'Mapping': ('원문 필드와 정규화 의미의 대응', None),
    'PolicyRule': ('프로토타입의 실행·추천 규칙', None),
}
for name, (label, parent) in class_defs.items():
    g.add((EX[name], RDF.type, OWL.Class))
    g.add((EX[name], RDFS.label, Literal(label, lang='ko')))
    if parent:
        g.add((EX[name], RDFS.subClassOf, parent))

properties = {
    'operatedBy': ('운영기관', 'Portal', 'Organization'),
    'refersToPortal': ('외부 포털로 안내', None, 'Portal'),
    'candidateTopic': ('등록정보 대응 후보', 'CatalogRecord', 'Dataset'),
    'successorCandidate': ('후속 자료 후보', 'Dataset', 'Dataset'),
    'analyticalComplement': ('분석 목적의 보완 자료', 'Dataset', 'Dataset'),
    'spatialConcept': ('공간 단위 개념', 'Dataset', 'Concept'),
    'leftDataset': ('왼쪽 자료', 'JoinAssessment', 'Dataset'),
    'rightDataset': ('오른쪽 자료', 'JoinAssessment', 'Dataset'),
    'sourceEvidence': ('검토 근거', None, 'Source'),
    'mappingScope': ('매핑 대상', 'Mapping', None),
}
for key, (label, domain, range_) in properties.items():
    g.add((EX[key], RDF.type, OWL.ObjectProperty))
    g.add((EX[key], RDFS.label, Literal(label, lang='ko')))
    if domain:
        g.add((EX[key], RDFS.domain, EX[domain]))
    if range_:
        g.add((EX[key], RDFS.range, EX[range_]))
for key in ['status', 'reviewedAt', 'lifecycle', 'productionEndedAfter', 'condition', 'blocker', 'joinKey', 'sourcePath', 'targetMeaning', 'transform', 'decision', 'temporalGrain', 'spatialGrain', 'rawRowsVerified', 'apiVerified', 'licenseDisplay', 'purpose']:
    g.add((EX[key], RDF.type, OWL.DatatypeProperty))

ontology = EX['ontology-v0-1']
g.add((ontology, RDF.type, OWL.Ontology))
g.add((ontology, OWL.versionInfo, Literal(model['version'])))
g.add((ontology, DCTERMS.description, Literal(model['verification_boundary'], lang='ko')))
g.add((ontology, EX.reviewedAt, Literal(model['reviewed_at'], datatype=XSD.date)))

nodes, edges = [], []
sources = {s['id']: s for s in model['sources']}
def add_node(item, type_):
    nodes.append({'id': item['id'], 'type': type_, **item})
    uri = EX[item['id']]
    g.add((uri, RDF.type, EX[type_]))
    parent = class_defs[type_][1]
    if parent:
        g.add((uri, RDF.type, parent))
    g.add((uri, RDFS.label, Literal(item.get('label', item.get('title', item['id'])), lang='ko')))
    for sid in item.get('source_ids', []):
        g.add((uri, EX.sourceEvidence, EX[sid]))
    if item.get('url'):
        g.add((uri, FOAF.page, URIRef(item['url'])))

predicate_uris = {
    'catalogRecord': DCAT.record,
    'primaryTopic': FOAF.primaryTopic,
    'publisher': DCTERMS.publisher,
    'creator': DCTERMS.creator,
    'theme': DCAT.theme,
    'broader': SKOS.broader,
    'relatedConcept': SKOS.related,
}
predicate_labels = {
    'catalogRecord':'수록', 'primaryTopic':'설명 대상', 'publisher':'제공기관', 'creator':'작성기관',
    'theme':'주제', 'broader':'상위 개념', 'relatedConcept':'관련 개념',
    **{k: v[0] for k, v in properties.items()}
}
def claim(subject, predicate, object_, status, source_ids, note='', id_=None):
    edge = {'id': id_ or f'claim-{len(edges)+1:03}', 'subject':subject, 'predicate':predicate, 'label':predicate_labels[predicate], 'object':object_, 'status':status, 'source_ids':source_ids, 'note':note}
    edges.append(edge)
    uri, pred = EX[edge['id']], predicate_uris.get(predicate, EX[predicate])
    for triple in [(uri, RDF.type, EX.Claim), (uri, RDF.type, RDF.Statement), (uri, RDF.subject, EX[subject]), (uri, RDF.predicate, pred), (uri, RDF.object, EX[object_]), (uri, EX.status, Literal(status)), (uri, EX.reviewedAt, Literal(model['reviewed_at'], datatype=XSD.date))]:
        g.add(triple)
    if note:
        g.add((uri, RDFS.comment, Literal(note, lang='ko')))
    for sid in source_ids:
        g.add((uri, EX.sourceEvidence, EX[sid]))
    if status in ['documented', 'curated']:
        g.add((EX[subject], pred, EX[object_]))

for source in model['sources']:
    add_node(source, 'Source')
    g.add((EX[source['id']], EX.status, Literal(source['access'])))
    g.add((EX[source['id']], EX.reviewedAt, Literal(model['reviewed_at'], datatype=XSD.date)))
    g.add((EX[source['id']], DCTERMS.description, Literal(source['note'], lang='ko')))
for org in model['organizations']:
    add_node(org, 'Organization')
for portal in model['portals']:
    add_node(portal, 'Portal')
    g.add((EX[portal['id']], FOAF.homepage, URIRef(portal['url'])))
    if portal['operator']:
        claim(portal['id'], 'operatedBy', portal['operator'], 'documented', portal['source_ids'])
scheme = EX['concept-scheme']
g.add((scheme, RDF.type, SKOS.ConceptScheme))
for concept in model['concepts']:
    add_node(concept, 'Concept')
    g.add((EX[concept['id']], SKOS.inScheme, scheme))
    g.add((EX[concept['id']], SKOS.prefLabel, Literal(concept['label'], lang='ko')))
    g.add((EX[concept['id']], SKOS.definition, Literal(concept['definition'], lang='ko')))
    for alias in concept['aliases']:
        g.add((EX[concept['id']], SKOS.altLabel, Literal(alias, lang='ko')))
    if concept['broader']:
        claim(concept['id'], 'broader', concept['broader'], 'curated', concept['source_ids'])
    for related in concept['related']:
        claim(concept['id'], 'relatedConcept', related, 'curated', concept['source_ids'])
for dataset in model['datasets']:
    add_node(dataset, 'Dataset')
    uri = EX[dataset['id']]
    for p, value in [(DCTERMS.title, dataset['label']), (DCTERMS.identifier, dataset['identifier']), (EX.lifecycle, dataset['lifecycle']), (EX.temporalGrain, dataset['temporal_grain']), (EX.spatialGrain, dataset['spatial_grain']), (EX.licenseDisplay, dataset['license_display'])]:
        g.add((uri, p, Literal(value)))
    g.add((uri, DCAT.landingPage, URIRef(dataset['url'])))
    g.add((uri, EX.rawRowsVerified, Literal(dataset['row_data_verified'])))
    g.add((uri, EX.apiVerified, Literal(dataset['api_verified'])))
    if dataset['production_ended_after']:
        g.add((uri, EX.productionEndedAfter, Literal(dataset['production_ended_after'], datatype=XSD.date)))
    if dataset.get('publisher_id'):
        claim(dataset['id'], 'publisher', dataset['publisher_id'], 'documented', dataset['source_ids'])
    if dataset.get('creator_id'):
        claim(dataset['id'], 'creator', dataset['creator_id'], 'documented', dataset['source_ids'])
    for cid in dataset['themes']:
        claim(dataset['id'], 'theme', cid, 'curated', dataset['source_ids'], '프로토타입에서 정의한 개념 분류')
    for cid in dataset['spatial_concepts']:
        claim(dataset['id'], 'spatialConcept', cid, 'curated', dataset['source_ids'])
    for fmt in dataset['distribution_formats']:
        distribution = EX[dataset['id'] + '-' + fmt.lower()]
        g.add((uri, DCAT.distribution, distribution))
        g.add((distribution, RDF.type, DCAT.Distribution))
        g.add((distribution, DCTERMS.format, Literal(fmt)))
        g.add((distribution, DCAT.accessURL, URIRef(dataset['url'])))
        g.add((distribution, RDFS.comment, Literal('형식별 제공 경로. 특정 파일 버전·다운로드 URL은 미확인.', lang='ko')))
for record in model['records']:
    add_node(record, 'CatalogRecord')
    claim(record['portal_id'], 'catalogRecord', record['id'], 'documented', record['source_ids'])
    if record['dataset_id']:
        claim(record['id'], 'primaryTopic', record['dataset_id'], 'documented', record['source_ids'])
for rel in model['relationships']:
    claim(rel['subject'], rel['predicate'], rel['object'], rel['status'], rel['source_ids'], rel['note'], rel['id'])
for assessment in model['join_assessments']:
    add_node(assessment, 'JoinAssessment')
    uri = EX[assessment['id']]
    g.add((uri, EX.leftDataset, EX[assessment['left']]))
    g.add((uri, EX.rightDataset, EX[assessment['right']]))
    g.add((uri, EX.status, Literal(assessment['status'])))
    g.add((uri, EX.purpose, Literal(assessment['purpose'], lang='ko')))
    for field, prop in [('conditions', EX.condition), ('blockers', EX.blocker), ('keys', EX.joinKey)]:
        for value in assessment[field]:
            g.add((uri, prop, Literal(value, lang='ko')))
for mapping in model['mappings']:
    add_node(mapping, 'Mapping')
    uri = EX[mapping['id']]
    g.add((uri, EX.mappingScope, EX[mapping['scope']]))
    for field, prop in [('status', EX.status), ('source_path', EX.sourcePath), ('target', EX.targetMeaning), ('transform', EX.transform)]:
        if mapping[field] is not None:
            g.add((uri, prop, Literal(mapping[field])))
for rule in model['rules']:
    add_node(rule, 'PolicyRule')
    for field, prop in [('condition', EX.condition), ('decision', EX.decision)]:
        g.add((EX[rule['id']], prop, Literal(rule[field], lang='ko')))

g.serialize(HERE / 'ontology.ttl', format='turtle')
graph = {'version':model['version'], 'reviewed_at':model['reviewed_at'], 'nodes':nodes, 'edges':edges, 'predicate_labels':predicate_labels}
(HERE / 'graph.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')

def source_links(ids):
    return ', '.join(f"[{sid}]({sources[sid]['url']})" for sid in ids)

readme = f'''# 공공데이터 온톨로지 프로토타입 v{model['version']}

최신 설계와 질문 중심 그래프는 [Discovery Platform v0.3](discovery-platform/README.md)에 있다.

전국·전 분야로 확장한 현재 작업은 [제공처 조사·공통 온톨로지 v0.2](national-catalog/README.md)에서 확인한다. 아래 모델은 기존 시연용 사례다.

검토 기준일: {model['reviewed_at']}. 범위: 포털 3곳 / 자료 6개 / 등록정보 7개 / 개념 11개.

사용자 질문에 필요한 자료를 찾고, 출처·측정 의미·결합 조건을 설명하기 위한 지식 구조다. 자연어 LLM, 실데이터 조회·결합, 거래 기능은 이번 산출물에 포함되지 않는다.

## 읽는 순서

1. 이 설명서에서 범위와 주의할 관계를 확인한다.
2. `model.json`의 데이터 목록·개념·관계·매핑·질문을 수정한다.
3. `ontology.ttl`은 RDF 도구로, `graph.json`은 일반 앱에서 읽는다.
4. `validation-report.json`은 구조·질의 검증 결과이며 실제 데이터 품질 인증이 아니다.

## 구조

```mermaid
flowchart LR
  P[포털] -->|등록정보 수록| R[등록정보]
  R -->|설명 대상| D[자료]
  D -->|제공·작성기관| O[기관]
  D -->|주제·공간 단위| C[개념]
  C -->|상위·관련 개념| C2[다른 개념]
  J[결합 검토] -->|검토 대상| D
  E[근거·상태를 가진 관계 주장] -->|근거| S[공식 문서]
```

포털은 `dcat:Catalog`, 등록정보는 `dcat:CatalogRecord`, 자료는 `dcat:Dataset`, 파일 제공 형식은 `dcat:Distribution`, 개념은 `skos:Concept`에 맞춰 표현했다. 완전한 외부 인증 프로파일이 아니라 DCAT·SKOS를 활용한 로컬 설계다. namespace의 example.org는 발급 전 임시 식별자이며 실제 서비스 주소가 아니다.

근거 표준: {source_links(['S11','S12'])}.

## 포털과 기관

| 포털 | 역할 | 운영기관 |
|---|---|---|
'''
orgs = {o['id']:o for o in model['organizations']}
for p in model['portals']:
    readme += f"| [{p['label']}]({p['url']}) | {p['role']} | {orgs[p['operator']]['label'] if p['operator'] else '이번 범위에서 미확정'} |\n"
readme += '''
포털 간 직접 안내 관계는 특정 등록정보의 근거를 갖는 관계다. 포털 전체가 동기화되거나 모든 데이터가 중복 수록된다는 뜻은 아니다. KOSIS와 서울 포털은 이번 모델에서 인구 분석에 함께 활용할 수 있는 자료의 제공처이며 시스템 간 연동을 확인한 것은 아니다.

## 자료 목록

| 자료 | 식별자 | 시간·공간 단위 | 상태 | 근거 |
|---|---|---|---|---|
'''
for d in model['datasets']:
    state = '생산 종료 안내' if d['lifecycle']=='production_ended' else '공식 목록·설명 확인'
    readme += f"| [{d['label']}]({d['url']}) | {d['identifier']} | {d['temporal_grain']} / {d['spatial_grain']} | {state} | {source_links(d['source_ids'])} |\n"
readme += '''
자료별 상세 제한과 미확인 항목은 model.json의 caveats, missing에 보존했다. 자료에 접근 가능한 설명 페이지와 API 동작 여부는 별개다. 페이지 갱신일, 실제 관측 시점, 파일 게시일을 동일하게 취급하지 않는다.

## 개념 사전

아래 정의와 분류는 출처를 참고한 프로토타입의 편집 판단(curated)이다. 특정 기관이 이 온톨로지를 공식 승인했다는 뜻이 아니다.

| 개념 | 정의 |
|---|---|
'''
for c in model['concepts']:
    readme += f"| {c['label']} | {c['definition']} |\n"
readme += '''
## 관계 상태

- documented: 공식 자료에서 해당 사실을 확인했다. 원본 행 검증과 구별한다.
- curated: 공식 자료를 근거로 이번 프로토타입에서 정의한 분류·분석 관계다.
- candidate: 추가 확인이 필요한 관계다. RDF에서 직접 사실 트리플로 내보내지 않고 상태를 가진 Claim으로만 저장한다.

`relatedConcept`는 주제 연관, `analyticalComplement`는 분석에 함께 참고할 관계다. 둘 다 조인 가능성·동일성·인과관계를 뜻하지 않는다. 조인 가능 여부는 별도의 JoinAssessment로 관리한다. 이 버전에는 검증 완료된 조인이 없다.

## 확인 과정에서 발견한 사례

1. 공공데이터포털의 버스 등록정보에는 일별 갱신 설명과 수시 갱신 표기가 함께 있다. 어느 하나로 덮어쓰지 않고 등록정보별로 보존했다.
2. 15051734 → OA-12912의 정확한 대응은 검색 색인에서 확인했지만 현재 상세페이지 직접 열기에 실패했다. 따라서 확정 동일성 관계를 만들지 않았다.
3. OA-14991은 2026-07-31 이후 기존 자료 생산 종료를 명시한다. 최신 자료 추천에서는 제외하며 실제 마지막 관측일을 임의로 기입하지 않았다.
4. OA-23016은 250m 격자에서 행정동으로 집계한 자료다. 파일명이 바뀐 동일 자료라고 단정하지 않고 후속 자료 후보로 연결했다.
5. 월별 파일 배포와 월별 관측은 다르다. 일별 버스·지하철 자료가 월 파일로 제공되어도 관측 단위는 일이다.
6. 페이지에 공통으로 들어 있는 숨겨진 ‘서비스 종료’ 팝업 문구는 종료 판정의 근거로 쓰지 않았다. OA-14991의 구체적 전환 안내만 사용했다.

## 연결 조건

'''
datasets = {d['id']:d for d in model['datasets']}
for j in model['join_assessments']:
    readme += f"### {datasets[j['left']]['short_label']} ↔ {datasets[j['right']]['short_label']}\n\n"
    readme += f"목적: {j['purpose']}. 상태: `{j['status']}`.\n\n"
    readme += '\n'.join('- '+x for x in j['conditions'] + ['미해결: '+v for v in j['blockers']]) + '\n\n'
readme += '''## 필드 매핑

실제 확인한 메타데이터 필드와 아직 확인하지 못한 원본 데이터 필드를 분리했다. `source_path: null`인 필드는 정규화 목표만 정한 상태이므로 실제 API 필드처럼 사용하면 안 된다. 현재 데이터셋 원본의 컬럼·자료형·키 유일성·결측률은 모두 미검증이다.

| 대상 | 원문 경로 | 정규화 목표 | 상태 |
|---|---|---|---|
'''
for m in model['mappings']:
    readme += f"| {m['scope']} | {m['source_path'] or '미확인'} | {m['target']} | {m['status']} |\n"
readme += '''
## 대표 질문과 기대 결과

이 질문들은 온톨로지의 범위를 확인하는 사례다. 자연어 질의 엔진을 구현했다는 뜻은 아니다.

'''
for q in model['questions']:
    readme += f"- **{q['id']} · {q['question']}** — {q['answer']}\n"
readme += '''
## 개발자가 이어서 할 일

1. 원본 파일 또는 적법하게 발급한 API 접근으로 컬럼·키·관측 기간을 확인한다.
2. 버스정류장·역 좌표, 기준일별 행정동 경계와 코드 대응표를 추가 등록한다.
3. 후보 매핑·조인마다 파일 버전, 표본 수, 실패·누락 비율, 검토자를 기록한다.
4. 생활인구 구·신 방식 비교를 완료하기 전에는 장기 시계열을 자동 접속하지 않는다.
5. 추천 화면의 허용과 원본 파일 재배포·거래의 허용을 별도 정책으로 구현한다.

## 재생성 및 검증

Python 3와 rdflib 7.6.0을 사용했다. `python -m pip install -r ontology-prototype/requirements.txt`로 설치한다.

```powershell
python ontology-prototype/build.py
python ontology-prototype/validate.py
```

model.json이 편집 원본이며 ontology.ttl, graph.json, README.md는 build.py가 생성한다. 시각 탐색용 fragment는 model.json만 포함하며 네트워크·LLM 호출을 하지 않는다.

## 근거 목록

'''
for s in model['sources']:
    readme += f"- **{s['id']}** [{s['title']}]({s['url']}) · `{s['access']}` — {s['note']}\n"
(HERE / 'README.md').write_text(readme, encoding='utf-8')

template = HERE / 'explorer.template.html'
if template.exists():
    out_dir = HERE.parent / '.local' / 'legacy-visualizations'
    out_dir.mkdir(parents=True, exist_ok=True)
    # Inject only serialized data into an authored literal markup template.
    payload = json.dumps(model, ensure_ascii=False).replace('<', '\\u003c')
    fragment = template.read_text(encoding='utf-8').replace('__ONTOLOGY_DATA__', payload)
    (out_dir / 'public-data-ontology.html').write_text(fragment, encoding='utf-8')
print(json.dumps({'datasets':len(model['datasets']), 'concepts':len(model['concepts']), 'edges':len(edges), 'rdf_triples':len(g)}, ensure_ascii=False))
