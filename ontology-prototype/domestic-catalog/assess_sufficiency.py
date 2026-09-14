"""Assess this prototype's metadata readiness, not national completeness. No network."""
from collections import Counter
import sqlite3
from common import HERE, ROOT, read, dump, now

DB = ROOT / '.local/domestic-catalog/catalog.sqlite3'


def main():
    concepts = read(HERE / 'concepts/concept-model.json')
    graph = read(HERE / 'concepts/graph-overview.json')
    coverage = read(HERE / 'coverage-report.json')
    db = sqlite3.connect(f'file:{DB.as_posix()}?mode=ro', uri=True)
    db.execute('BEGIN')
    total, urls, receipts, locators, providers = db.execute("""
        SELECT count(*), sum(coalesce(url,'')<>''),
          sum(coalesce(evidence_id,'')<>''), sum(coalesce(locator,'')<>''),
          sum(coalesce(provider_name,'')<>'') FROM records
    """).fetchone()
    fields, descriptions, units, datatypes, field_receipts = db.execute("""
        SELECT count(*),sum(coalesce(description,'')<>''),sum(coalesce(unit,'')<>''),
          sum(coalesce(datatype,'')<>''),sum(coalesce(evidence_id,'')<>'')
        FROM documented_fields
    """).fetchone()
    kinds = [{'kind': k, 'documents': n, 'source_field_occurrences': f}
             for k,n,f in db.execute('SELECT kind,count(*),sum(field_count) FROM schema_documents GROUP BY kind')]
    topics = [{'id': c['id'], 'label': c['label'],
               'candidate_occurrences': c.get('candidate_occurrences_in_index', 0),
               'selected_source_examples': c.get('displayed_evidence_examples', 0)}
              for c in concepts['concepts'] if c['kind'] == 'Topic']
    facets = dict(Counter(c['kind'] for c in concepts['concepts']))
    evidenced = dict(Counter(c['kind'] for c in concepts['concepts']
                            if c.get('displayed_evidence_examples', 0) > 0))
    missing_mapping_records = [m['id'] for m in concepts['mappings']
        if not db.execute('SELECT 1 FROM records WHERE id=?',
                          (m['evidence']['record_id'],)).fetchone()]
    db.close()
    receipt_issues = []
    for e in concepts['evidence']:
        p = HERE / 'evidence' / (e['id'] + '.json')
        if not p.exists():
            receipt_issues.append(e['id']); continue
        r = read(p)
        if not all(r.get(k) for k in ['requested_url','retrieved_at','sha256','raw_file']):
            receipt_issues.append(e['id'])
        elif not (HERE / r['raw_file']).exists():
            receipt_issues.append(e['id'])
    prior_checks = {}
    for f in ['concepts/validation-report.json', 'concepts/graph-validation.json',
              'law-source-check.json', 'fisis-source-check.json']:
        r = read(HERE / f)
        prior_checks[f] = {'generated_at': r.get('generated_at'),
                          'passed': r.get('passed', r.get('status') == 'passed')}
    checks = [
        {'criterion': '선정한 16개 탐색 분야 각각에 검토할 출처 사례가 있다.',
         'passed': len(topics) == 16 and all(t['selected_source_examples'] > 0 for t in topics)},
        {'criterion': '8개 개념 역할(분야·지표·대상·분류·공간·시간·식별자·단위)에 출처 사례가 있다.',
         'passed': len(facets) == 8 and set(evidenced) == set(facets)},
        {'criterion': '포털→등록정보→명세→근거 구조를 추적하고 제공기관의 원문 표기를 검토할 수 있다.',
         'passed': total == urls == receipts == locators and fields == field_receipts and providers > 0},
        {'criterion': '파일·API·통계표의 서로 다른 명세 형식을 비교할 수 있다.',
         'passed': all(any(k['kind'] == typ and k['source_field_occurrences'] > 0 for k in kinds)
                       for typ in ['FILE', 'API', 'statistical_table'])},
        {'criterion': '기존 개념 사례의 등록정보와 근거 파일이 유지되며 출처 대조 보고서가 있다.',
         'passed': not missing_mapping_records and not receipt_issues and
                   all(c['passed'] for c in prior_checks.values())},
        {'criterion': '미완료 범위와 의미 관계 승인 전 상태를 구분해 보존한다.',
         'passed': coverage['all_domestic_portals_complete'] is False and
                   coverage['all_columns_complete'] is False and
                   coverage['semantic_relationships_approved'] == 0}
    ]
    report = {
        'generated_at': now(), 'decision_authority': 'Codex; user delegated sufficiency judgment on 2026-09-15 KST',
        'purpose': '국내 전 분야 공공데이터 탐색 온톨로지 프로토타입의 개념·관계 설계를 시작할 자료 확보',
        'decision': 'sufficient_for_prototype' if all(c['passed'] for c in checks) else 'targeted_gaps_need_review',
        'decision_basis': '현재 프로젝트 목적에 대한 설계 판단이다. 국가 전체 수집률이나 통계적 대표성을 판정하는 기준이 아니다.',
        'recommended_collection_action': 'stop_bulk_collection_and_use_targeted_followup' if all(c['passed'] for c in checks) else 'review_failed_criteria',
        'criteria': checks, 'national_complete': False, 'all_columns_complete': False,
        'ontology_complete': False, 'production_ready': False,
        'catalog_snapshot_at': coverage['generated_at'],
        'counts': {k: coverage[k] for k in ['registered_portal_candidates','portals_with_catalog_acquisition',
                   'total_catalog_records','fields_in_source_definition_documents','documented_column_occurrences']},
        'record_provenance': {'total': total, 'url_present': urls, 'receipt_id_present': receipts,
                              'locator_present': locators, 'reported_provider_name_present': providers},
        'field_metadata_presence': {'occurrences': fields, 'description': descriptions, 'unit': units,
                                   'datatype': datatypes, 'receipt_id': field_receipts,
                                   'note': '필드 출현 기준이며 정확성·완전성 품질 점수나 고유 변수 수가 아니다.'},
        'schema_formats': kinds, 'concept_snapshot_at': concepts['generated_at'],
        'concept_facets': facets, 'facets_with_selected_source_examples': evidenced, 'topics': topics,
        'selected_mappings_checked': len(concepts['mappings']), 'missing_mapping_records': missing_mapping_records,
        'selected_receipt_files_checked': len(concepts['evidence']), 'receipt_issues': receipt_issues,
        'prior_source_checks': prior_checks,
        'graph_snapshot_at': graph.get('generated_at', graph.get('snapshot_started_at')),
        'graph_counts': graph['counts'],
        'limitations': [
            '125개 후보는 국내 모든 포털의 확정 모집단이 아니며 34개 수집 포털도 부분 수집이다.',
            '16개 분야와 88개 개념은 프로젝트 초안이다. 출처 사례 확보는 분야 내 모든 개념·기관·자료의 포괄을 뜻하지 않는다.',
            '개념 사례는 이름·문서 기반 후보이며 사람의 의미 검증은 남아 있다. 일부 과거 사례에 세부 원문 위치가 없다.',
            '다른 포털의 기관·데이터셋 중복 정리와 코드·단위·시간·공간의 호환성 검증이 남아 있다.',
            '라이선스·갱신일·단위 등 누락 정보와 명세 미확보·403/429·인증·서버/파싱 오류는 미해결로 유지한다.',
            '관측값 품질·결측률·통계적 상관관계는 검사하지 않았다. 데이터 제공·거래 승인을 위한 준비 완료 판정이 아니다.',
            '공유 지식그래프는 별도 고정 스냅샷이다. 수집 DB의 최신 건수와 같지 않다.'
        ],
        'next_phase': [
            '기존 88개 초안 개념과 703개 선별 검토 항목부터 뜻·대상·단위·코드 체계·적용 시점을 검토한다.',
            '의미가 다른 동명이항과 동일 개념의 다른 이름을 구분하고 근거와 검토자를 기록한다.',
            '관계 검토에서 특정 명세·코드표·라이선스가 부족한 경우 해당 출처만 범위를 정해 추가 수집한다.',
            '실제 사용 목적이 데이터 결합·분석·제공으로 확장되면 그 목적에 맞춘 값 QA와 조건 검증을 별도로 수행한다.'
        ]
    }
    dump(HERE / 'collection-sufficiency-assessment.json', report)
    rows = ['# 온톨로지 프로토타입 수집 충분성 판단', '',
            '판정: **초기 개념·관계 설계를 진행할 자료는 충분하다. 대량 자동 수집을 종료하고 필요 자료만 보충한다.**'
            if report['decision'] == 'sufficient_for_prototype' else '판정: 기준 미충족 항목을 검토한다.', '',
            '사용자가 수집 충분성 판단을 Codex에 위임했다. 이에 따라 목적별 충분성과 전국 전수 수집 완료를 구분한다.', '',
            f"판정 기록: {report['generated_at']} · 수집 현황 기준: {coverage['generated_at']}", '',
            f"목록을 확보한 포털 {coverage['portals_with_catalog_acquisition']}곳, 등록정보 {total:,}건, "
            f"원문 명세 항목 {coverage['fields_in_source_definition_documents']:,}회 출현을 확보했다. "
            '개별 원문 데이터 전체나 고유 분석 변수의 수가 아니다.', '',
            '## 충분하다고 판단한 이유', '']
    rows += [f"- {'충족' if c['passed'] else '추가 검토'}: {c['criterion']}" for c in checks]
    rows += ['', '분야·개념 사례가 있으므로 이제 관계 후보를 검토하며 부족한 정보를 구체적으로 식별할 수 있다. '
             '더 많은 목록을 계속 모으는 것만으로 의미 검증·단위 정규화·기관 식별 문제는 해결되지 않는다.', '',
             '## 판단의 한계', ''] + ['- ' + x for x in report['limitations']]
    rows += ['', '## 다음 작업', ''] + [f'{i}. {x}' for i,x in enumerate(report['next_phase'],1)]
    rows += ['', '## 근거', '',
             '- [측정값·분야별 사례·판정 항목](collection-sufficiency-assessment.json)',
             '- [수집 정책](completion-policy.json)',
             '- [실제 수집 범위](coverage-report.json)',
             '- [개념 초안과 원문 대조](concepts/validation-report.json)',
             '- [지식그래프 검증](concepts/graph-validation.json)',
             '- [수집 종료 운영 기록](collection-stop-report.json)', '']
    (HERE / 'COLLECTION-SUFFICIENCY.md').write_text('\n'.join(rows), encoding='utf-8')
    print(report['decision'], report['counts'], flush=True)
    if report['decision'] != 'sufficient_for_prototype':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
