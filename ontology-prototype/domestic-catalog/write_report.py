from common import *

NAMES={'data-go':'공공데이터포털','kosis':'KOSIS 주제별통계','seoul':'서울 열린데이터광장','gyeonggi':'경기데이터드림','neis':'나이스 교육정보 개방 포털','assembly':'열린국회정보','culture':'문화공공데이터광장','ecos':'한국은행 ECOS','yeongdeungpo':'영등포구 열린 데이터 광장','incheon':'인천데이터포털','daegu':'D-데이터허브','library':'도서관 정보나루'}
NAMES.update(opendart='금융감독원 OpenDART',address='주소기반산업지원서비스')
NAMES.update({'kma-api':'기상청 API허브','mafra':'농림축산식품 공공데이터포털'})
NAMES.update(busan='부산 Big-데이터웨이브',ulsan='울산광역시 데이터포털')
NAMES.update(chungnam='충남 올담',jeonbuk='전북 빅데이터 허브',sgis='SGIS 통계지리정보서비스',jeju='제주데이터허브')
NAMES.update({'hrdk-api':'한국산업인력공단 오픈 API'})
NAMES.update(foodsafety='식품안전나라 데이터활용서비스')
NAMES.update(grac='게임물관리위원회 Open API',forest='산림청 공공데이터 개방목록')
NAMES.update(expressway='고속도로 공공데이터 포털',hrfco='한강홍수통제소 Open API')
NAMES.update({'kdi-api':'KDI Open API','kocca-api':'한국콘텐츠진흥원 Open API','kspo':'국민체육진흥공단 공개 데이터 안내','bigdata-culture':'문화 빅데이터 플랫폼'})
def esc(v):return str(v or '미확인').replace('|',' / ').replace('\n',' ')
def main():
    c=read(HERE/'coverage-report.json');ps=read(HERE/'inventory/domestic-portals.json')['portals']
    rows=['# 국내 공공데이터 포털·기관·칼럼 수집 결과','',
        '현재 수집 범위는 **국내 포털 전 분야**다. OECD와 World Bank는 이번 수집 대상에서 제외했다.',
        '국내는 포털 제공처의 범위다. 국내 포털이 제공하는 국제 통계를 주제만으로 제외하지 않는다. KOSIS의 다른 목록 뷰는 추가 조사 대상이다.',
        '**국내 모든 포털과 모든 칼럼을 수집 완료한 상태는 아니다.** 아래는 실제 내려받은 공식 목록과 공개 명세의 수량이다.','',
        f"조회·생성 시점(UTC): {c['generated_at']}",'',
        '## 확보한 목록과 칼럼','',
        '| 출처 | 등록정보 행 | 출처 안의 고유 목록 키 | 선언된 출력항목명 후보 | 명세에서 확인한 칼럼 | 명세를 확보한 등록정보 |',
        '|---|---:|---:|---:|---:|---:|']
    for x in c['portal_counts']:
        rows.append('| '+' | '.join([NAMES.get(x['portal_id'],x['portal_id'])]+[f'{x[k]:,}' for k in ['catalog_records','distinct_catalog_keys','declared_output_tokens','documented_columns','records_with_documented_columns']])+' |')
    rows += ['',
        f"총 등록정보 **{c['total_catalog_records']:,}행**, 선언된 출력항목명 후보 **{c['declared_output_tokens']:,}개**를 저장했다. 명세 문서별 항목 합계는 **{c.get('fields_in_source_definition_documents',c['documented_column_occurrences']):,}개**, 기관별 등록정보에 연결한 반복까지 포함한 항목 수는 **{c['documented_column_occurrences']:,}개**다.",
        '등록정보 행에는 동일 자료의 분류 경로·제공기관별 반복이 포함된다. 고유 목록 키도 포털 사이의 중복을 제거한 실제 데이터셋 수는 아니다. 두 칼럼 수는 서로 겹치므로 합산하지 않는다.',
        '명세 수에는 통계 분류·측정 항목·기간과 API 응답 코드·메시지도 포함된다. 모두 물리적 CSV 칼럼이나 통계분석 변수인 것은 아니다.','',
        '## 계속 수집하는 방식','',
        '공식 목록의 모든 식별자를 큐에 넣어 재개 가능한 워커로 조회한다. 수집기는 원문을 재사용하고 호스트별 요청 간격 및 요청 제한 시 대기를 적용한다. 검색 DB는 5분마다 증분 반영하고 휴대용 칼럼 파일은 약 1시간마다 갱신한다.',
        '수집 큐가 끝나도 미공개·접근 제한·파싱 실패·미확인 코드 목록은 미해결로 남긴다. [완료 판정 조건](completion-policy.json)과 [이어가기 문서](CONTINUATION.md)를 따른다. 로컬 컴퓨터가 켜져 있고 네트워크가 연결되어 있어야 워커가 진행된다.',
        '현재 작업에는 30분 간격 후속 실행도 설정되어 있어 워커 상태를 확인하고 미수집 제공처의 경로 조사를 이어간다. 예약 설정 자체는 수집 완료 근거가 아니다.','',
        '## 먼저 보는 방법','',
        '- 검색 화면: `python ontology-prototype/domestic-catalog/browse.py` 실행 후 http://127.0.0.1:8766 에서 기관명·자료명·칼럼명으로 검색한다.',
        '- 현재 국내 온톨로지 구조: [model.json](model.json). 대규모 실제 목록은 연결된 파일과 검색 DB에 분리되어 있다.',
        '- 공통 개념 체계 초안: [개념·근거 탐색](http://127.0.0.1:8766/concepts) / [설명](concepts/README.md) / [개념 JSON](concepts/concept-model.json). 원문 용어 후보와 사람 검토 전 매핑을 따로 관리한다.',
        '- 전체 출처 지식 그래프: [포털·자료·항목·개념 연결](http://127.0.0.1:8766/concepts/graph) / [사용법과 집계 범위](concepts/GRAPH-README.md). 전체 연결 집계와 등록 자료 탐색을 제공하며 의미 관계는 검토 전이다.',
        '- 국내 제공처: [포털 수집 상태표](portal-coverage.md) / [JSON](inventory/domestic-portals.json).',
        '- 기관별 등록부: [providers.json](inventory/providers.json). 기관 코드는 포털별 이름공간으로 분리했다.',
        '- 전체 등록정보 파일은 [model.json](model.json)의 `instance_files.catalogs` 목록을 따른다. 새 제공처는 별도 압축 파일로 추가한다.',
        '- 실제 외부 참조 관계: [external-references.jsonl.gz](inventory/external-references.jsonl.gz). [신규 제공처 조사 큐](inventory/provider-discovery-frontier.json)로 연결한다. 링크 관측만으로 동일 데이터라고 단정하지 않는다.',
        '- 모든 추출 항목명 후보: [declared-field-tokens.jsonl.gz](inventory/declared-field-tokens.jsonl.gz).',
        '- 실제 공개 명세의 칼럼: [documented-columns.jsonl.gz](inventory/documented-columns.jsonl.gz).',
        '- 파일 첫 레코드·공개 미리보기의 머리글 후보: [csv-header-candidates.jsonl.gz](inventory/csv-header-candidates.jsonl.gz). 공식 명세나 실제 값의 품질 검증과 구분한다.',
        '- 수집 실패·형식 이상: [격리 행](inventory/quarantine.jsonl.gz), [수집 QA 보고서](import-report.json), [검사 결과](validation-report.json).','',
        '- 금융·주소 제공처의 원문 QA: [목록·설명·파일 형식·변수 표기 차이](finance-address-source-qa.json). 실제 데이터 값의 품질 점수와 구분한다.','',
        'JSONL 파일은 한 줄에 한 레코드이며 gzip으로 압축했다. 기관·목록·칼럼의 ID, 원문 위치와 evidence_id로 출처를 추적한다. 원문은 evidence 폴더의 gzip 파일에 보존하고 각 JSON 영수증에 URL·조회일·SHA256을 기록했다.',
        '## 출처별 수집 범위와 남은 일','',
        '1. **공공데이터포털:** 행정안전부의 목록 메타정보 CSV 전체를 확보했다. 파일 표기는 20260703이고 현재 포털 전체 목록과의 일치는 미확인이다. 원본의 108,234행 중 형식이 잘못된 50행과 영향을 받을 수 있는 앞선 12행은 격리했다. 페이지의 전체 행 표시 68,943과 파일의 실제 행 수가 달라 QA 이슈로 기록했다.',
        '   FILE 83,691개, API 12,053개, STD 179개 키 전체의 공개 명세 수집 큐를 실행한다. API는 연산별 출력과 요청 인자를 분리한다. 정의서가 없거나 주소가 폐기된 항목은 완료 처리하지 않으며 공개 파일 헤더와 원기관 명세를 추가 조사한다.',
        '   화면에 내장된 Swagger/OpenAPI 명세도 해석한다. 응답의 중첩 구조·배열·연산·상태 코드·매체별 변형과 원문 JSON 포인터를 보존하고 요청 인자를 분리한다. 순환 참조·외부 명세 참조·동적 속성은 미해결로 기록한다. 항목 수는 명세의 출현 수이며 API 변형 사이에서도 반복될 수 있다. [최초 복구](data-go-api-swagger-first-recovery-report.json), [원문 위치 검사](new-adapter-check.json).',
        '2. **KOSIS:** 2026.09.13 국내 주제별통계 목록의 XLS 5개 시트를 모두 읽었다. 식별 가능한 통계표 266,688개의 공개 분류·측정 항목·단위·기간 명세를 순회한다. 기본 화면에 나온 분류 코드는 전체 코드 목록과 다를 수 있어 코드 수를 대조한다. 식별자를 확인하지 못한 1,581개 목록 행과 다른 국내 목록 뷰는 별도 미해결 범위다.',
        '3. **서울:** 26년 8월 목록 XLSX의 서비스 8,272개 첫 순회를 마쳤으며 5,665개에서 API·일반 시트 명세를 확보했다. 통계형 S/2 자료 1,777개를 공개 statSheetView → stat.eseoul.go.kr iframe 경로로 순회해 1,776개·8,736항목을 확보했다. OA-882는 원문 HTTP 500과 후속 재조회 실패로 남겨 두었다. 분류·측정항목·기간을 구분하고 OA 등록 ID와 DT 통계표 ID를 함께 보존한다. 기본 화면에 일부만 나타난 분류 코드나 측정 단위를 임의 완성하지 않는다. 링크 전용 자료·서비스 선언 없는 자료 등은 미해결이며 제공부서를 제공기관으로 추측하지 않는다. [통계형 수집](seoul-statistics-collection-report.json), [원문 대조](address-db-seoul-adapter-check.json).',
        '4. **경기:** 공개 목록의 총수와 고유 ID 수를 대조했다. 기본 정렬의 페이지 반복을 발견해 데이터명 정렬로 재조회했으며 결과는 [수집 보고서](gyeonggi-collection-report.json)에 남겼다. API 경로가 있는 자료의 출력 명세를 수집했고, API 없는 파일·링크의 칼럼은 별도 확인해야 한다.',
        '5. **나이스:** 공개 목록 12개와 해당 12개 API의 출력 명세를 모두 확보했다. 공개 문서 확인 범위이며 기관 내부 DB나 실제 관측값을 수집한 것은 아니다.',
        '6. **열린국회·문화데이터:** 열린국회 API 278개, 문화데이터 API 468개의 목록과 출력 명세를 확보했다. 문화 파일 목록 470개의 CSV 첫 레코드도 별도로 수집한다. 첫 레코드는 헤더 후보이며 전체 파일을 내려받지 않는다. 일반 정보공개·소속기관 별도 API·다른 유형 목록은 추가 조사한다.',
        '7. **한국은행 ECOS·영등포구:** ECOS 공개 통계코드검색의 분류 노드 259개와 통계표 681개를 구분하고 681개 표의 분류 명세를 확보했다. 679개 표의 코드 응답은 개수가 대조되었고, 903Y003·903Y203의 구분코드 조회는 HTTP 400으로 미해결이다. [ECOS 코드 대조](ecos-schema-coverage-report.json)를 참고한다. 영등포구 자체 목록 153개도 확보했다. 분류 코드를 칼럼 수에 합산하지 않으며, 서울 포털과 OA 코드가 같다는 이유만으로 같은 자료라고 확정하지 않는다.',
        '8. **인천·대구:** 인천은 공개 등급 5 목록의 439페이지·4,382개 고유 ID를 대조했다. srcSe와 dataId를 함께 식별자로 사용한다. 펼친 응답변수 문자열은 후보로 보존하고, 자체 API의 구조화된 responseInfo는 원문 항목별로 대조해 명세에 반영한다. 대구 데이터셋 상세 목록은 2026.09.13 스냅샷의 2,218페이지·19,954개 고유 ID가 공식 총계와 일치했다. 월별 파일이 공유하는 dataSetId 대신 dataSetDetailId로 구분했다. 별도 외부 LINK 목록과 칼럼 명세는 아직 남아 있다. 두 포털의 원기관 링크를 같은 데이터라는 승인으로 바꾸지 않는다. [인천 목록 대조](incheon-catalog-report.json), [대구 목록 대조](daegu-catalog-report.json).',
        '9. **도서관 정보나루:** 공식 공개 API 매뉴얼 v20260210의 70페이지에서 번호가 붙은 19개 서비스와 응답 요소 436개를 수집했다. 추천 유형에 따라 같은 주소를 쓰는 두 서비스를 보존하여 고유 호출 주소는 18개다. 표의 칼럼 위치와 페이지·행을 저장하고 중첩 경로는 추측하지 않았다. 요청 인자·분류 코드표는 응답 요소 수에 합산하지 않는다. 웹 안내의 18개 서비스와 매뉴얼의 19개 서비스에는 차이가 있고, 도서관별 다운로드 자료·테마자료는 남은 조사 범위다. [매뉴얼 목록 대조](library-catalog-report.json), [추출 검사](new-adapter-check.json).',
        '10. **OpenDART:** 공개 개발가이드 6개 분류의 85개 API와 응답 항목 2,175개를 확보했다. 소개 게시판은 9페이지·83건으로 수량과 일부 표기가 다르므로 두 원본을 보존하고 불일치를 표시했다. API 2개는 오류 응답 항목만 확인되고 ZIP/XBRL 파일 내부 명세는 미해결이다. result·list 같은 구조 노드와 요청 인증키는 응답 항목 수에 합산하지 않는다. 공시 개별 보고서와 재무정보 일괄 다운로드 목록은 별도 범위다. [목록 대조·차이](opendart-catalog-report.json), [원문 대조](finance-address-adapter-check.json).',
        '11. **주소기반산업지원서비스:** 공개 UI의 API 목록 11개와 그중 9개 서비스의 응답 항목 199개를 확보했다. 주소 DB 공개 분류 31개를 별도 db/ 식별자로 추가하고 공개 스키마의 칼럼 출현 1,117개를 원문과 대조했다. 한 분류의 여러 파일 형식과 공간정보 그룹을 구분하며 자료형·크기·PK 표기는 원문대로 보존한다. 배포 JavaScript의 정적 자료만 실행 없이 읽고 원문 문자 위치·배열 행을 기록한다. RLS_YN 표시는 파일 다운로드 권한이나 품질 점수로 해석하지 않는다. 지도 검색 PDF의 입력 14개는 응답 칼럼에 포함하지 않는다. 개별 날짜별 배포 파일 목록, 상세주소 팝업과 지도 검색의 독립 출력 명세는 남아 있다. [API 목록](address-catalog-report.json), [DB 분류 목록](address-db-catalog-report.json), [DB 명세 수집](address-db-collection-report.json), [원문 검사](address-db-seoul-adapter-check.json).',
        '12. **기상청 API허브:** 홈페이지의 13개 분야에서 하위 분류 55개와 산업특화 가이드 1개를 모두 읽었다. 가이드의 호출 형식 626개를 구분하여 출력 표 304개·응답 변수 출현 4,709개를 확보했다. 나머지 322개는 별도 매뉴얼·공유 표 적용 범위·이미지·격자·파일 내부 명세를 확인해야 한다. 식별자는 가이드 경로와 제목 위치로 만든 프로젝트 ID이며 공식 API ID나 고유 호출 URL 수가 아니다. 의미(단위)에 코드 체계·시간대가 함께 적혀 있어 단위를 임의 분리하지 않는다. 요청 인증키와 출력 변수를 구분하고 관측 API를 호출하지 않았다. [가이드 범위](kma-api-catalog-report.json), [명세 진행](kma-api-collection-report.json).',
        '13. **농림축산식품:** 공개 통합검색의 파일 619개·API 183개·링크 1,340개를 수집했다. 링크의 수정일 정렬에서 중복 1개를 발견했고 조회수 정렬 전체를 추가 순회해 고유 ID 1,340개를 대조했다. 두 순회의 원문과 중복을 보존한다. 전체 2,142개 중 원문 PUBLIC 분류는 1,359개, PRIVATE 분류는 외부 거래소 연계 목록 783개다. 포털에 등록되어 있다는 이유로 모두 공공기관 생산 데이터·무료 재사용 자료라고 분류하지 않는다. PUBLIC과 PRIVATE의 공식 상세 경로를 구분한다. API 183개의 기본 출력 표에서 2,387항목을 확보한 뒤, 여러 기능이 있는 API 6개의 기능별 명세를 추가로 확인해 2,725항목으로 확장했다. 기능 선택 목록 전체는 197개이며, 추가 조회한 20개 중 19개의 문서를 읽었고 기능 1개는 두 번 시간 초과되어 미해결이다. 기능별 중복 출현을 포함하며 고유 분석 변수 수가 아니다. 파일·링크까지 기본 공개 상세 메타데이터 2,142개 큐를 마쳤으며, 파일 헤더와 원기관 명세는 미해결이다. [기능별 진행](mafra-operations-collection-report.json). 표준용어 검색의 10,000 표시는 별도 사전 범위이며 데이터셋 수에 더하지 않았다. [목록 대조](mafra-catalog-report.json), [수집 진행](mafra-collection-report.json).',
        '14. **부산 Big-데이터웨이브:** 공공데이터 목록 내보내기의 12,551개 PUBLICDATAPK가 모두 고유하며 검색 총계와 일치한다. 영상·보고서·링크도 포함된 등록정보이고 모든 항목이 표 형식인 것은 아니다. 연결 오류 9건을 이전 실패 근거를 보존한 채 한 번씩 재확인하여 전체 12,551개 공개 JSON 메타데이터를 확보했다. 원문 영수증·SHA256 25,022개를 대조했으며, API 350개 등록의 연산 442개와 파일 목록 12,119개 등록의 버전 메타데이터 17,375행을 보존했다. 응답 이름 후보 7,071개와 설명 후보 7,071개는 같은 문자열 목록의 별도 표현이며 합산하거나 정식 칼럼으로 승격하지 않는다. fileCnt=0과 비어 있지 않은 fileList의 의미가 같은지는 미확인이므로 누락 파일이나 품질 불량으로 단정하지 않는다. 상세 HTML의 HTTP 200 오류 화면, 다른 카탈로그 탭·실제 파일 헤더·원기관 명세는 남아 있다. [재조회 후 상태](busan-final-metadata-collection-report.json), [원문 전수 대조](busan-final-metadata-source-check.json), [사이트별 QA](busan-source-qa.json).',
        '15. **울산광역시 데이터포털:** 통합 목록은 HTML이 중간에 끊기므로 파일·API·표준데이터의 개별 탭 174페이지를 순회했다. 15개 보기와 각 탭의 마지막 페이지를 대조해 파일 2,284행·API 116행·표준 182행을 보존했다. 목록 자체의 독립 ID가 없어 스냅샷·유형·페이지·행 위치로 프로젝트 ID를 만들고 원문 링크·제공기관·기능명을 보존한다. 같은 data.go.kr 주소를 가리키는 여러 등록 행을 합치지 않는다. 목록 2,582행은 중복 제거한 데이터셋 수가 아니며 링크만으로 원본 칼럼을 복제하지 않는다. [페이지 범위](ulsan-catalog-report.json), [수집 진행](ulsan-collection-report.json).',
        '16. **충남 올담:** 공개 공공데이터 목록 413페이지의 4,124개 고유 등록 키가 총계와 일치했다. 자체 자료 apiIdx 1,451개와 연계·인허가 자료 publicdatapk 2,673개를 분리하며, PUB로 시작하는 문자 ID도 그대로 보존한다. 화면 표에 명시된 header/name 칼럼 정의는 정적 코드의 원문 위치와 함께 보존한다. 표본 관측값의 키에서 칼럼을 추측하지 않으며, 화면 표의 명세를 모든 파일 버전의 명세로 확대하지 않는다. Vue의 비어 있는 API 안내 템플릿을 실제 API 명세로 세지 않는다. 연계 API 211개의 기능별 공개 파라미터 명세도 순회했다. 같은 자료 버전·기능의 반복 탭을 대조해 명세를 중복 합산하지 않고 입력과 출력을 분리한다. header/items 같은 일반 요소명은 구조 여부가 불명확해 별도 보존한다. [기능별 진행](chungnam-operations-collection-report.json), [원문 대조](chungnam-operations-source-check.json). 별도 통계·맞춤형 데이터와 파일 내부 전체 명세는 남은 범위다. [목록 대조](chungnam-catalog-report.json), [수집 진행](chungnam-collection-report.json).',
        '17. **전북 빅데이터 허브:** 데이터셋 목록 224페이지의 pId 2,233개가 화면 총계와 일치하고 각 페이지의 행 번호도 대조했다. 상세의 자료명과 명시적인 공공데이터포털 링크를 확인하고, 파일·API의 uddi 버전 ID와 각 버전의 메타데이터 표 및 링크를 따로 보존한다. 설명문에 나열된 변수명을 검증 명세로 승격하지 않으며, 외부 참조만으로 다른 포털과 동일 자료라고 확정하지 않는다. [목록 대조](jeonbuk-catalog-report.json), [수집 진행](jeonbuk-collection-report.json).',
        '18. **SGIS 통계지리정보서비스:** 공개 개발지원센터의 DATA API 문서 본문 68개 구획과 68쌍의 요청·응답 표를 읽었다. 응답 행 620개 중 항목 618개, JavaScript 산출물 설명 1개, 셀이 모자란 미해결 행 1개를 구분했다. 입력 244개는 응답 수에 합산하지 않는다. 메뉴 표적 8개는 대응 본문이 없고, #106은 메뉴의 도시권 목록과 본문의 소지역 코드찾기가 달라 미해결이다. 본문에 적힌 구형 API 주소·연도·값 설명을 그대로 보존하며 실제 API 운영이나 최신성을 확인했다고 주장하지 않는다. 인증키 발급과 관측 API는 호출하지 않았다. 문서에서 참조하는 코드표 14개의 461행을 확보하고 입력/출력 인자와 연결된 참조 35개를 보존했다. 코드 선행 0·연도·병합 셀의 원문 위치를 유지하며 코드 행은 칼럼 수에 더하지 않는다. [코드표](inventory/sgis-code-lists.json), [인자별 참조](inventory/sgis-code-list-references.json). 지도 API·SDK·파일 사전과 다른 코드 목록은 다음 범위다. [본문 목록과 메뉴 차이](sgis-catalog-report.json), [원문 대조](sgis-source-check.json).',
        '19. **제주데이터허브:** 공개 데이터 목록 126페이지의 고유 등록 ID 1,259개가 별도 총계 조회와 일치했다. 목록 JSON에 포함된 API 93개에서 응답 명세 686항목, 요청 331항목을 구분했다. 파일/미리보기 메타데이터 출현 2,240개는 역할·파일 ID·원문 위치를 보존하며 실제 파일 수나 파일 헤더 수로 해석하지 않는다. 소유자와 업로더를 생산기관으로 단정하지 않고, API 주소에 내부 IP가 기재되어 있어도 해당 주소로 요청하지 않는다. 실제 API 사용의 인증/허가 표시는 재사용 승인으로 바꾸지 않는다. 개인·민간 등록 및 해외 주제 자료도 국내 포털의 공개 목록에 포함된다. 파일 헤더와 별도 인포그래픽·보고서·센터 목록은 남은 범위다. [목록 대조](jeju-catalog-report.json), [원문 검사](sgis-codes-jeju-source-check.json).',
        '20. **한국산업인력공단:** 공식 API 목록 본문의 카드 69개와 공공데이터포털 참조 69개를 저장했다. 59개는 기존 API 등록 키와 일치하며 57개는 저장한 명세가 있다. 나머지 10개 링크는 실제 조회에서 HTTP 404였고 [실패 근거](hrdk-unresolved-target-check.json)를 보존했다. 안내문의 개방 API 229개 전체와 같다고 단정하지 않는다. MCP 통합 경로는 안내 41개와 실제 공개 도구 45개가 다르고, NCS 경로도 안내 5개와 실제 6개가 다르다. 통합·분야별 7개 경로의 명세 출현 87개와 입력 속성 223개는 별도 [도구 메타데이터](inventory/hrdk-mcp-tool-contracts.json)에 보존했다. 응답 스키마는 없으며 도구 실행·데이터 관측 요청은 하지 않았다. 입력 속성을 데이터셋 칼럼으로 합산하거나 도구와 API 사이의 매핑을 추측하지 않는다. [목록 대조](hrdk-api-catalog-report.json), [MCP 수량 대조](hrdk-mcp-collection-report.json).',
        '21. **농식품 파일 미리보기:** 기존 FILE 등록 619개 화면을 대조해 459개 자료에서 파일 버전별 미리보기 요청 1,510개를 발견해 해당 큐를 소진했다. 머리글 후보 16,990셀을 보존했으며 버전별로 후보 관측 1,471개·빈 결과 30개·HTTP 실패 3개·HTML 오류 응답 6개다. 큐 소진은 칼럼 완성을 의미하지 않는다. 공식 화면에서 listHead를 표 머리글로 표시하는 셀만 후보로 저장하고 파일 ID·원문 위치를 보존한다. 제목행·병합행·빈칸이 있을 수 있어 정식 칼럼 명세로 승격하지 않는다. 공개 미리보기 응답은 2 MB로 제한하며 원본 파일 전체는 다운로드하지 않는다. [진행 상태](mafra-previews-collection-report.json), [버전별 대상](inventory/mafra-preview-targets.json).',
        '22. **식품안전나라:** 현재 전체 목록 178개(4페이지), API 169개·FILE 8개·LINK 1개를 수집했다. API별 출력 1,861항목을 확인했고 동일한 명세 표가 두 번 표시되는 169개 사례는 원문 전체 행이 일치할 때만 중복 수량을 제외했다. 입력 인자·오류 코드·샘플 관측값은 출력 칼럼에 합산하지 않는다. FILE 8개 화면의 파일 버전 정보 316행은 파일 자체를 내려받지 않고 수집했다. 별도 API 필터의 169개 ID가 전체 목록의 API ID와 일치하지만, 이전 홈의 172개 표시 및 9월 공지의 171종과는 범위/기준일 차이가 미해결이다. 개인정보 관련 항목을 Null로 제공한다는 공식 공지가 있으므로 칼럼 존재를 실제 값의 가용성으로 해석하지 않는다. [수집 요약](foodsafety-definition-summary.json), [목록 대조](foodsafety-catalog-crosscheck.json), [공식 공지 근거](inventory/foodsafety-source-notices.json), [사이트별 메타데이터 QA](foodsafety-source-qa.json). 최종수정일이 기재된 등록은 144/178개지만 실제 데이터 최신성이나 정확도 점수를 매긴 것은 아니다.',
        '23. **게임물관리위원회:** OPEN API 메뉴의 게임·채용 가이드 2개에서 응답·제어 항목 24개와 입력 10개를 수집했다. 구조 요소 4개와 오류 코드·XML 예시는 별도로 보존한다. 게임 가이드의 `canceledddate`와 예시의 `canceleddate`, 잘못 닫힌 XML 선언/태그, 채용 가이드의 `result`/`results`·`resultItem` 차이를 자동으로 고치거나 병합하지 않는다. [원문 QA](grac-source-qa.json). 이 두 안내를 기관 전체 데이터의 전수 목록으로 간주하지 않는다.',
        '24. **산림청:** data.forest.go.kr의 안내 페이지에 있는 실제 이동 주소를 따라 공공데이터 개방목록의 명시된 분류 5개·56개 등록정보를 수집했다. 자체 HTML 안내 21개 중 10개에서 응답 156항목·입력 50항목을 확보했다. 별도 활용정보 탭 19개를 따라 지도 자료 5개·속성 표 7개에서 파일/레이어 속성 61개를 추가했다. 등산로의 지점·선·안전지점 표는 서로 다른 그룹이며 같은 이름을 합치지 않는다. 단위·좌표계·파일 형식·문서의 최종수정일은 원문 문맥으로 보존하고 EPSG 코드나 최신 파일 적용 여부를 추측하지 않는다. 길이가 물음표인 3개 항목은 미확인이다. 전체 56개 중 명세가 있는 등록은 15개이며 나머지 자체 안내 6개·외부 참조 35개는 칼럼 미확인이다. [목록 범위](forest-catalog-report.json), [파일 속성 요약](forest-attribute-summary.json), [사이트별 QA](forest-source-qa.json). 전체 건수 표시는 없어 명시된 분류 문서 수집과 기관 전체 완료를 구분한다.',
        '25. **고속도로 공공데이터 포털:** 빈 필터 검색의 527개 등록(FILE 238·API 93·원본 문서 194·LOD 2)을 별도 유형/분류 집계 및 API 목록 93개와 대조했다. API 응답 1,553항목과 원본 문서 56개의 정식 칼럼 설명 306항목을 확보했다. 입력 384행·공통 입력 2개/API·입출력 구분이 공백인 15행은 별도 보존하며, 공식 화면이 이 15행을 출력 표에 표시한다는 근거도 남겼다. 샘플 237개 머리글 2,728셀과 LOD 목록 2개 머리글 9셀은 정식 명세로 세지 않는다. 원본 문서 194개의 파일 버전 목록 806행과 외부 링크 15개를 수집했으며 파일 다운로드나 활용목적 양식 제출은 하지 않았다. 자료의 추천 ID는 원문 추천 정보이며 통계적 관계로 승인하지 않는다. [목록 대조](expressway-catalog-report.json), [사이트별 QA](expressway-source-qa.json), [원문 검사](expressway-hrfco-source-check.json). 파일 전체 버전에 이 칼럼이 적용되는지는 미검증이다.',
        '26. **한강홍수통제소:** WAMIS의 공식 안내 링크를 따라 공개 API 레퍼런스의 수위·강수량·댐·보·홍수예보 9개 연산에서 응답 73항목을 수집했다. 입력 표 74행과 오류 코드 18행은 별도 보존한다. 단위가 명시된 24항목은 원문 표기를 유지하며 자료형·좌표계 EPSG를 추정하지 않는다. 댐/보 관측소 설명에 강수량이라고 적힌 2개 항목과 보정 전 T/M 자료라는 공식 주의사항을 [사이트별 QA](hrfco-source-qa.json)에 기록했다. 실제 값의 신뢰도 점수나 실측 결측률을 산출한 것은 아니다.',
        '27. **WAMIS:** 공개 API 홈과 활용가이드는 읽었지만 API 목록 이동은 로그인 분기로 안내하므로 보호된 목록을 요청하지 않았다. 강우레이더 서비스 중단·기상청 자료 연계 문제 공지를 원문과 함께 보존했다. 강우레이더 대체 안내가 한강홍수통제소 레퍼런스를 연결하지만 해당 9개 연산과 레이더 서비스의 범위 동일성은 미해결이다. WAMIS 전체 사이트가 비공개라는 의미는 아니며 다른 공개 목록·명세는 계속 조사 대상이다. [접근 조건 및 공지 QA](water-source-access-qa.json).',
        '28. **KDI:** 공개 Open API 안내의 A–F 분류 6개에서 응답·제어 항목 113개와 입력 30개를 확보했다. ARCHIVES 구조 행 6개는 응답 칼럼과 분리한다. 문서의 cd 기본값이 6개 분류 모두 A인 차이를 보존하며 실제 API를 호출하거나 B–F 기본값을 임의로 수정하지 않는다. 이 6개는 API 분류이며 KDI 개별 연구자료의 전수 목록이 아니다. [수집 상태](kdi-api-collection-report.json), [사이트별 QA](kdi-api-source-qa.json).',
        '29. **한국콘텐츠진흥원:** 공개 활용가이드 6개에서 응답 101개·입력 33개를 수집했다. 응답 상단의 title과 List.title은 별도 경로이며 cata 같은 원문 표기를 유지한다. 입력 표 6개에 tr 없이 놓인 numOfRows 셀을 실제 위치로 복구하고, 정기간행물 표의 rowspan 범위 초과는 존재하는 행까지만 읽었다. resultMgs/resultMsg 등 안내·예시 차이를 기록하고 예시 키로 정식 항목을 추가하지 않는다. 소개 메뉴의 분류명 차이·전체 기관 목록과 실제 API 값 검증은 남아 있다. [사이트별 QA](kocca-api-source-qa.json).',
        '30. **국민체육진흥공단:** 공식 안내가 연결한 외부 공개 데이터 지도의 활성 등록 183개를 수집했다. 외부 호스트 소유권은 확인되지 않았고 복사된 명세·공개 미리보기 머리글 3,035셀은 후보로 구분한다. 지도에 선언된 관계 시나리오·품질 등급을 승인된 관계나 점수로 가져오지 않는다. 공식 개방 안내의 표 20행·6행은 자료 묶음이며 개별 등록과 합산하지 않는다. data.go.kr 참조 86개는 기존 목록 키와 모두 일치하지만 원본 칼럼을 복제하지 않는다. [사이트별 QA](kspo-source-qa.json), [원기관 참조 대조](inventory/kspo-data-go-reference-resolution.json).',
        '31. **문화 빅데이터 플랫폼:** 위 지도에서 실제로 연결된 원본 자료 92개의 공개 상세 화면과 컬럼정의서 시트를 대조해 정식 칼럼 1,577항목을 확보했다. 컬럼명·한글명·자료형·길이·PK·NOT NULL·상품명과 비연속 순번을 그대로 보존한다. 지도에 복사된 명세와 원문 셀이 정확히 일치한 자료는 87개, 자료형 등 정보 생략이나 설명 차이가 있는 자료는 5개다. 비교는 문서 내용 대조이며 사람이 승인한 의미 동일성·통계 관계 검증이 아니다. 관측값 다운로드·구매·API 호출은 하지 않았다. 플랫폼 전체 목록은 아직 남아 있다. [진행](culture-market-references-collection-report.json), [사이트별 QA](culture-market-reference-source-qa.json), [출처 간 셀 비교](inventory/kspo-culture-primary-definition-comparison.json).',
        '   별도로 미리보기 머리글과 원본 정의서의 칼럼명·순서를 비교하면 92쌍 중 90쌍 일치, 2쌍 차이다. 경륜 등록 선수 자료는 미리보기 31개에 비해 원본 정의서는 28개이며, 차이만으로 칼럼을 추가하거나 파일 누락으로 단정하지 않는다. [미리보기와 정의서 비교](inventory/kspo-culture-preview-dictionary-comparison.json). 위의 87/5는 복사된 정의서의 전체 셀 비교이고 이 90/2는 미리보기와 정의서의 이름·순서 비교로 검사 대상이 다르다.',
        f"32. **나머지 제공처:** 국내 조사 등록부 {c['registered_portal_candidates']}개 중 목록을 일부라도 확보한 {c['portals_with_catalog_acquisition']}곳 외의 제공처는 수집 경로·명세 형식을 계속 조사한다. 원문 외부 참조에서 발견한 신규 제공처도 검토한다. 전국 제공처 자체의 완전한 명부도 아직 없다.",
        '', '## 관계 정의에 사용하는 방법','',
        '관계의 출발점은 `포털 → 등록정보 → 보고된 제공기관`, `등록정보 → 공식 명세 칼럼`, `칼럼 → 원문 근거`다. 이 연결은 수집 근거이며 사람이 승인한 의미 관계 DB와 구분된다.',
        '예를 들어 나이스의 학교기본정보에 있는 `SD_SCHUL_CODE`는 원문에서 “행정표준코드”라고 설명된다. 다른 자료에 같은 코드가 있으면 코드 체계·대상·기준일을 대조해 결합 후보를 만들 수 있다. 이름 일치만으로 `sameAs`나 `joinableWith`를 확정하지 않는다.',
        '실제 분석값, 결측률, 기관별 품질 점수, 통계적 상관관계, 개인정보·라이선스 승인은 생성하지 않았다. 목록 메타정보 자체의 이용허락 범위를 개별 원본 자료의 재사용 허가로 상속하지 않는다.',
        '', '## 원문과 재현','',
        '- [행정안전부 공공데이터포털 목록 메타정보](https://www.data.go.kr/data/15121937/fileData.do)',
        '- [KOSIS 국내 통계목록](https://kosis.kr/statisticsList/statisticsListIndex.do?menuId=M_01_01&vwcd=MT_ZTITLE)',
        '- [서울 전체 공공데이터 목록 및 이용현황](https://data.seoul.go.kr/together/notice/datasetNoticeView.do?seq=934c376ea6dbbff6082b7a4a1c2ce7f8&bbsCd=10008)',
        '- [경기데이터드림 목록](https://data.gg.go.kr/portal/data/dataset/searchDatasetPage.do)',
        '- [나이스 데이터셋 목록](https://open.neis.go.kr/portal/data/dataset/searchDatasetPage.do)',
        '', 'Python에 requirements.txt의 라이브러리를 준비한 다음 프로젝트 루트에서 실행한다. XLS/XLSX 입력은 읽기 전용으로 처리한다.',
        '```powershell',
        'python -X utf8 ontology-prototype/domestic-catalog/index_progress.py',
        'python -X utf8 ontology-prototype/domestic-catalog/build_frontier.py',
        'python -X utf8 ontology-prototype/domestic-catalog/validate.py',
        'python -X utf8 ontology-prototype/domestic-catalog/write_report.py',
        'python -X utf8 ontology-prototype/domestic-catalog/browse.py',
        '```',
        '이 명령은 새 관찰 자료를 기존 검색 DB에 추가한다. SQLite는 `.local/domestic-catalog/catalog.sqlite3`의 검색 인덱스이며 한 번에 전부 RAM에 올리지 않는다. 초기 3개 벌크 목록만 처리하는 build_inventory.py를 현재 DB 위에서 재실행하지 않는다.',
        '새 외부 수집은 collect_portal_catalogs.py와 collect_definitions.py로 실행한다. 후자의 기본값은 기관별 명세 어댑터 점검이고 `--all`은 수집 목록의 FILE 상세 명세 전부를 대상으로 하므로 많은 외부 요청이 발생한다. 이미 받은 원문은 재사용한다. 최신 시점으로 다시 조사할 때는 기존 evidence를 보존하고 새 버전의 source ID를 사용한다.',
        '', '기존 discovery-platform/model.json과 지식그래프는 v0.3의 과거 탐색 데모다. 현재 국내 수집 범위는 이 디렉터리의 v0.5 model.json과 coverage-report.json을 따른다.','']
    (HERE/'README.md').write_text('\n'.join(rows),encoding='utf-8')
    table=['# 국내 제공처별 수집 상태','',
        f"기존 조사 등록부와 새로 발견한 제공처를 합쳐 {len(ps)}개 후보를 관리한다. 미검증 서비스 후보와 기관 대표 누리집 입구를 포함한다. 기관 내부 비공개 DB는 수집 범위가 아니다.",'',
        '| 제공처 | 조사 분류 | 현재 목록 수집 | 칼럼 수집 | 원문 / 다음 작업 |','|---|---|---|---|---|']
    for p in ps:
        v=p.get('current_collection')
        table.append('| '+esc(p['research_name'])+' | '+esc(p['group'])+' | '+(f"{v['catalog_records']:,}행" if v else '대기')+' | '+(f"명세 {v['documented_columns']:,}개 · 후보 {v['declared_output_tokens']:,}개" if v else '미수집')+' | [공식 입구]('+p['requested_url']+') · '+('누락 칼럼·차원 명세 확인' if v else esc(p.get('next_action')))+' |')
    (HERE/'portal-coverage.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
    print('Reports written')

if __name__=='__main__':main()
