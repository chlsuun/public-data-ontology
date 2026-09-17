"""Record this completed verification step, leaving ongoing collections active."""
from common import *


def main():
    source=read(HERE/'institutional-source-check.json')
    imported=read(HERE/'institutional-import-check.json')
    busan=read(HERE/'busan-final-metadata-source-check.json')
    health_path=max(HERE.glob('workers-*-check.json'),key=lambda p:p.stat().st_mtime_ns)
    health=read(health_path);coverage=read(HERE/'coverage-report.json')
    assert all(x['passed'] for x in (source,imported,busan,health))
    assert not coverage['all_columns_complete'] and not coverage['all_domestic_portals_complete']
    progress={name:read(HERE/name) for name in ('definition-collection-report.json','kosis-collection-report.json',
        'busan-final-metadata-collection-report.json','kdi-api-collection-report.json','kocca-api-collection-report.json',
        'kspo-collection-report.json','culture-market-references-collection-report.json')}
    name='continuation-20260914T0920-report.json'
    report={'generated_at':now(),'coverage_snapshot':coverage,'progress_snapshots':progress,
        'added_catalog_records':287,'added_portals_with_catalogs':['kdi-api','kocca-api','kspo','bigdata-culture'],
        'new_formal_field_occurrences':1791,'new_secondary_preview_header_candidates':3035,
        'institutional_source_check':{'ref':'institutional-source-check.json','checks_passed':source['checks_passed'],
            'source_hashes_verified':source['source_hashes_verified']},
        'institutional_import_check':{'ref':'institutional-import-check.json','checks_passed':imported['checks_passed'],
            'expansion_exports':imported['expansion_exports']},
        'busan_final_source_check':{'ref':'busan-final-metadata-source-check.json','catalog_records':12551,
            'source_receipts_and_hashes_verified':busan['source_receipts_and_hashes_verified'],
            'connection_failures_recovered':9,'formal_column_definitions_from_this_queue':0},
        'dictionary_copy_comparison_ref':'inventory/kspo-culture-primary-definition-comparison.json',
        'preview_dictionary_comparison_ref':'inventory/kspo-culture-preview-dictionary-comparison.json',
        'kosis_source_error_ref':'kosis-source-error-20260914.json',
        'runtime_check_ref':health_path.name,'runtime_check_passed':True,
        'runtime_restarted_in_this_step':False,'completed_finite_collectors_not_reregistered':True,
        'prior_global_validation_remains_20260913T1244_snapshot':True,
        'national_census_complete':False,'all_columns_complete':False,
        'quality_scores_assigned':False,'statistical_relationships_approved':False,
        'git_operations_performed':False,'other_projects_modified':False,'messages_to_others_sent':False,
        'next_actions':['Continue the existing FILE and KOSIS queues without duplicates',
            'Expand remaining domestic portals and full culture market catalog beyond 92 referred pages',
            'Follow primary schema links and version-specific definitions for metadata-only records',
            'Keep inaccessible sources and missing definitions unresolved with their original evidence']}
    dump(HERE/name,report)
    model=read(HERE/'model.json');model['instance_files']['institutional_import_check']='institutional-import-check.json'
    dump(HERE/'model.json',model)
    continuation=HERE/'CONTINUATION.md';text=continuation.read_text(encoding='utf-8')
    marker='127. 2026.09.14 08:48 UTC 후속 수집'
    if marker not in text:
        text+='''

127. 2026.09.14 08:48 UTC 후속 수집에서 기존 FILE·KOSIS·인덱서·검색 서버·감시기가 정상임을 확인했다. 이번 단계에서는 복구나 재시작을 하지 않았다. 부산 기본 메타데이터 큐는 08:40:23 UTC에 12,551개를 마치고 자연 종료했으므로 재실행하지 않았다. 과거 큐 보고서는 최초 상세 실패 4개와 부분 파일 조회 실패를 보존하는 시점별 기록이다.
128. `retry_busan_connections.py`가 실제 연결 끊김 9개만 이전 원문/정의 문서를 보존한 채 한 번씩 재조회했다. selectDataSet 4건·selectFileData 5건 모두 성공했고 새 evidence ID에 connection-retry-20260914를 붙였다. 기존 HTTP 오류·인증·호출제한을 재시도하거나 보호된 경로로 우회하지 않았다. [재조회 기록](busan-connection-retry-report.json), [이전 정의 문서](inventory/busan-retry-original-documents.json)를 보존한다. collect_busan.collect_one의 선택적 evidence_replacements/force는 이 9건 재해석용이며 기본 큐 동작은 그대로다.
129. [부산 전체 원문 대조](busan-final-metadata-source-check.json)가 12,551개 등록 및 영수증·SHA256 25,022개를 확인했다. 공개 API 메타데이터가 있는 등록 350개·연산 442개, 파일 목록이 있는 등록 12,119개·파일 메타데이터 17,375행이다. 응답 이름 후보 7,071개와 설명 후보 7,071개는 별도 표현이므로 합산하지 않는다. 원문 링크 출현 24,295개 중 호스트 없는 http:// 자리표시자 6개는 보존하되 frontier에서 제외한다. fileCnt가 모두 문자열 0인 데 비해 fileList가 비어 있지 않은 12,119개 사례는 필드 의미가 미확인이다. 실제 파일 누락·품질 불량으로 판정하지 않는다. [부산 QA](busan-source-qa.json)와 [재조회 후 진행](busan-final-metadata-collection-report.json)을 추가했고 검색 화면에는 후자의 현재 상태를 표시한다. 원래 busan-collection-report.json은 삭제하지 않았으며 정식 칼럼은 여전히 0개다. HTML 상세 오류·다른 부산 카탈로그·원기관 명세는 남아 있다.
130. `collect_kdi_kocca.py`가 KDI 공개 Open API 안내의 A–F 분류 6개·정식 응답 및 제어 항목 113개·입력 30개를 확보했다. ARCHIVES 구조 행 6개는 칼럼에서 분리했다. cd 기본값 A가 모든 분류에 반복되는 5개 차이를 그대로 남겼으며 실제 API를 호출하거나 기본값을 수정하지 않았다. 연구자료 개별 목록 6개라는 뜻이 아니다. 공공데이터 개방 안내는 keyword 검색 링크이며 별도 자료 목록으로 세지 않았다. [KDI QA](kdi-api-source-qa.json)를 참고한다.
131. 같은 수집기가 한국콘텐츠진흥원 활용가이드 6개·응답 101개·입력 33개를 확보했다. 응답 상단 title과 List.title을 경로별로 구분하고 List.cata를 원문 그대로 유지한다. 입력 표 6개에서 tr 없는 numOfRows 셀을 실제 tbody.direct_cells 위치와 함께 보존했다. 정기간행물 출력 표의 rowspan=9는 실제 남은 7행에만 적용하고 원래 범위를 감사 정보에 남겼다. resultMgs/resultMsg, List/list, startDt/viewStartDt 등 문서·예시 불일치를 자동 보정하지 않는다. 구조 6개·오류 코드 36행은 응답 수량과 분리한다. 소개 메뉴와 실제 가이드의 명칭 차이도 [KOCCA QA](kocca-api-source-qa.json)에 있다. API·인증 신청은 실행하지 않았다.
132. `collect_kspo_referred.py`는 국민체육진흥공단 공식 공개 안내가 실제 연결한 외부 GitHub Pages 데이터 지도에서 활성 등록 183개를 확보했다. 공개 안내 표 20행·6행은 묶음이며 개별 자료로 합산하지 않는다. 외부 호스트 소유권은 미확인이다. HTML→명시된 app.js→명시된 explorer-data.json을 읽었고 코드는 실행하지 않았다. 배포 자산에 들어 있는 표본 관측 행은 raw 영수증에 부수적으로 포함되지만 관측값을 추출·검색·분석하거나 원본 CSV를 요청하지 않았다. 활성 목록에 없는 분리 payload 키 33·40·103은 등록으로 추가하지 않았다. 복사된 명세 그룹 178개와 미리보기 머리글 3,035셀은 후보이며 정식 칼럼 0개다. 앱의 예정된 관계 시나리오·basis 등급은 승인 관계·품질 점수로 가져오지 않았다. [KSPO QA](kspo-source-qa.json), [data.go.kr 참조 86개 대조](inventory/kspo-data-go-reference-resolution.json)를 확인한다.
133. `collect_culture_market_references.py`는 활성 지도에 실제로 연결된 문화 빅데이터 플랫폼 원문 92개를 별도 제공처 등록으로 수집했다. hidden id·제목·기관 링크 및 화면의 컬럼정의서 시트/호출 코드를 대조하고 공개 읽기용 columninfo.do의 type=preview/id 요청으로 칼럼 1,577개를 확보했다. 원문 여덟 셀의 순번·영문명·한글명·자료형·길이·PK·NOT NULL·상품명을 보존한다. 비연속 순번이나 단위를 임의 완성하지 않는다. 관측 미리보기·파일 다운로드·구매는 실행하지 않았다. 전체 문화 플랫폼 목록이 아니라 92개 참조 부분집합이다. [수집 상태](culture-market-references-collection-report.json), [원문 QA](culture-market-reference-source-qa.json)를 확인한다.
134. [복사된 정의서와 원문 셀 비교](inventory/kspo-culture-primary-definition-comparison.json)는 87개 완전 일치·5개 차이를 확인했다. 4개는 복사본의 자료형 등 속성 생략, 1개는 설명 표기 차이다. 이와 별개로 [미리보기 머리글과 원문 정의서 이름·순서 비교](inventory/kspo-culture-preview-dictionary-comparison.json)는 90개 일치·2개 차이다. 경륜 등록 선수 미리보기 31개/정의서 28개, 다른 자료의 WRHSN_DE 차이를 보존한다. 문서 비교와 파일 버전 동등성·사람이 승인한 의미 관계·통계 관계 검증은 구분한다. KSPO 자료에 원본 칼럼을 복제하지 않았고 외부 참조 178개에는 same_dataset_asserted/joinability_asserted=false를 유지했다.
135. [기관 원문 대조](institutional-source-check.json) 11개가 원문 SHA256 193개 및 신규 287개 등록·정식 항목 1,791개·머리글 후보 3,035개를 대조했다. [DB·실제 HTTP·내보내기 검사](institutional-import-check.json) 최종 18개가 문서/필드 전체 일치, 정식 명세 필터, 구조/오탈자/깨진 표 위치, 부산 재조회 근거, 외부 참조 178개와 현재 진행 표시를 확인했다. 새 명세 1,791행과 후보를 담은 180개 문서 행을 별도 gzip 스냅샷으로 저장하고 다시 읽어 대조했다. 후보 항목 수 3,035와 후보 문서 행 수 180을 혼동하지 않는다. 전역 압축 export는 기존 인덱서의 시간별 실행이 관리하므로 현재 SQLite보다 늦을 수 있다. 이전 전체 58개 검사는 여전히 2026.09.13 12:44 UTC 고정 범위다.
136. KOSIS의 새로운 parse_unresolved 1건(134/DT_13403)은 HTTP 200 원문에 통계표 정보가 없다는 alert가 있고 g_jsonStatInfo가 없는 사례다. [출처 오류 관측](kosis-source-error-20260914.json)에 원문 문자 위치·SHA256을 보존했다. 영구 삭제나 파서 결함으로 단정하지 않았고 자동 재조회/정식 칼럼 생성 없이 기존 실패 문서를 유지한다. 파일 텍스트의 parse_unresolved 검색은 previous_parser_attempt에도 걸리므로 현재 상태 확인에는 schema_documents.status 또는 최상위 status를 사용한다.
137. [이번 확장 기록](continuation-20260914T0920-report.json)의 09:18:37 UTC 스냅샷은 목록을 일부 확보한 제공처 32곳·등록정보 440,356개·명세 문서별 항목 1,143,674개다. 표준 명세의 제공기관별 연결 반복을 포함한 SQL 행은 1,392,536개로 별도 수량이다. 고유 분석 변수 수나 통계 관계 수가 아니다. [09:20 워커 검사](workers-20260914T0920-check.json)에서 FILE 8120·KOSIS 11416·인덱서 18188이 각각 한 프로세스이며 활성 오류 로그 0바이트, 감시기 3744·검색 서버 3236 정상, stop 표시가 없다. 이번 새 유한 수집기·검사기는 모두 자연 종료했으며 반복 워커로 등록하지 않았다. 다음 실행에는 실제 명령행과 새 진행을 다시 확인한다. 국내 후보 125개는 전수 명부가 아니며 나머지 포털·칼럼·파일 버전·재사용 조건·관계 검증을 계속한다. Git 작업·다른 프로젝트 수정·타인 메시지 발송은 하지 않았다.
'''
        continuation.write_text(text,encoding='utf-8')
    print(json.dumps({'report':name,'coverage_generated_at':coverage['generated_at'],
        'portals':coverage['portals_with_catalog_acquisition'],'catalog_records':coverage['total_catalog_records'],
        'source_document_field_occurrences':coverage['fields_in_source_definition_documents'],
        'health_ref':health_path.name,'all_columns_complete':False},ensure_ascii=False))


if __name__=='__main__':main()
