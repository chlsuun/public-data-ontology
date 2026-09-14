"""Editable project vocabulary. Definitions and alias mappings require human review."""
FACETS = {
    'Topic':('분야','자료를 탐색하는 주제 분류. 지표의 상위 클래스와 구분한다.'),
    'Measure':('지표','무엇을 세거나 측정하는지. 관측값 자체와 구분한다.'),
    'EntityType':('대상','사람·학교·시설 등 측정하거나 설명하는 대상의 종류.'),
    'Dimension':('분류 기준','성별·연령 등으로 관측 대상을 나누는 기준.'),
    'SpatialReference':('공간 기준','행정구역·집계구·주소·좌표 등 공간을 지정하는 방식.'),
    'TemporalReference':('시간 기준','관측의 기준 시점과 집계 기간. 자료 갱신일과 구분한다.'),
    'IdentifierScheme':('식별 기준','대상을 구별하는 코드. 기관·코드 체계·버전이 같아야 연결을 검토할 수 있다.'),
    'Unit':('단위','값의 크기를 해석하는 단위. 필드에 실제로 적힌 단위만 관측 사실로 저장한다.')}

# slugs are project IDs, never a claim that the source uses these identifiers.
TOPICS = [
 ('population','인구·가구','인구|가구|인구/가구'),('employment','고용·노동','고용|노동|고용·노동|임금'),
 ('economy','경제·금융','경제|금융|경제일반|금융·보험|물가'),('industry','산업·기업','산업|기업|사업체|산업/경제'),
 ('transport','교통·물류','교통|물류|교통·물류'),('land','국토·주택·주소','국토|주택|건설|도시관리|주택/건설'),
 ('environment','환경·기상·수문','환경|기상|수문'),('agriculture','농림·수산·식품','농림|농업|수산|식품|농림어업'),
 ('health','보건·의료','보건|의료|보건의료'),('welfare','복지·사회','복지|사회|사회복지'),
 ('education','교육','교육'),('culture','문화·관광·체육','문화|관광|체육|문화/관광'),
 ('administration','행정·재정','행정|재정|일반행정'),('law','정치·법률','정치|법률|법무|입법'),
 ('science','과학·기술·정보통신','과학|기술|정보통신|과학기술'),('safety','안전·재난','안전|재난|공공질서및안전')]

# kind, slug, label, topic, exact lexical candidates, working definition, scope checks.
ROWS = [
 ('Measure','population-count','인구수','population','인구수|총인구|총인구수','특정 대상·공간·시점에 속하는 인구의 규모.','상주·주민등록·생활인구를 별도 확인'),
 ('Measure','registered-population','주민등록인구','population','주민등록인구|주민등록인구수','주민등록 기준으로 집계한 인구를 가리키는 초안 개념.','등록 기준·외국인 포함 여부·기준일 확인'),
 ('Measure','living-population','생활인구','population','생활인구|생활인구수|총생활인구수','출처가 생활인구로 정의한 추계 지표.','출처의 추계 방법·내외국인 범위·시간 단위 확인'),
 ('Measure','household-count','가구 수','population','가구수|총가구수|가구','자료에서 정의한 가구의 수.','가구와 세대, 일반가구와 전체가구 구분'),
 ('Measure','labor-force','경제활동인구','employment','경제활동인구','출처의 경제활동 상태 기준에 따른 경제활동인구 규모.','연령·조사기간·구직 기준 확인'),
 ('Measure','employed-count','취업자 수','employment','취업자|취업자수','취업자로 분류된 사람의 수.','취업 판정 기준·조사 대상 확인'),
 ('Measure','unemployed-count','실업자 수','employment','실업자|실업자수','실업자로 분류된 사람의 수.','구직기간·취업 가능성·연령 기준 확인'),
 ('Measure','unemployment-rate','실업률','employment','실업률','실업자의 비중을 나타내는 지표. 정확한 분모·배율은 통계 설명에서 검토한다.','경제활동인구 분모·연령·계절조정 여부 확인'),
 ('Measure','employment-rate','고용률','employment','고용률','대상 인구 중 취업자의 비중을 나타내는 지표.','분모의 연령 범위와 배율 확인'),
 ('Measure','participation-rate','경제활동참가율','employment','경제활동참가율','대상 인구의 경제활동 참여 비중.','분모·연령·계절조정 여부 확인'),
 ('Measure','inactive-count','비경제활동인구','employment','비경제활동인구','경제활동인구에 포함되지 않는 대상 인구.','실업자와 혼동 금지·활동상태 기준 확인'),
 ('Measure','boarding-count','승차 인원','transport','승차총승객수|승차인원|승차인원수|승차승객수','교통수단에 승차한 인원 또는 이용 건수로 보고된 지표.','중복 이용·환승·실인원 여부 확인'),
 ('Measure','alighting-count','하차 인원','transport','하차총승객수|하차인원|하차인원수|하차승객수','교통수단에서 하차한 인원 또는 이용 건수로 보고된 지표.','중복 이용·환승·실인원 여부 확인'),
 ('Measure','traffic-volume','교통량','transport','교통량|총교통량','정해진 구간·지점·기간의 교통 통행 규모.','차종·방향·집계 간격 확인'),
 ('Measure','speed','통행 속도','transport','통행속도|평균속도','도로 구간이나 차량의 통행 속도로 보고된 지표.','단위·구간 평균과 지점 속도 구분'),
 ('Measure','precipitation','강수량','environment','강수량|강수량자료','정해진 관측 시간과 지점에서 보고된 강수량.','누적 기간·보정 여부·결측 코드 확인'),
 ('Measure','water-level','수위','environment','수위|수위자료','관측 지점의 수면 높이로 보고된 지표.','높이 기준면·단위·보정 여부 확인'),
 ('Measure','temperature','기온','environment','기온|평균기온|최고기온|최저기온','대기의 온도를 나타내는 지표군.','평균·최고·최저는 세부 지표로 분리 검토'),
 ('Measure','fine-dust','미세먼지 농도','environment','미세먼지농도|미세먼지 농도|PM10','입자 크기 기준에 따른 대기 중 입자 농도.','PM10과 PM2.5·평균 시간·단위 구분'),
 ('Measure','financial-amount','재무 계정 금액','economy','당기금액|전기금액|thstrm_amount|frmtrm_amount','특정 회사·기간·계정의 재무 보고 금액.','계정·연결/별도·기간·통화 구분'),
 ('Measure','price','가격','economy','가격|판매가격|거래가격','재화나 서비스의 가격으로 보고된 값.','품목·규격·통화·부가세·실거래/호가 구분'),
 ('Measure','loan-count','도서 대출 건수','culture','대출건수|대출 건수|대출횟수','도서관에서 집계한 도서 대출 규모.','대출 기간·연장 포함 여부·자료 범위 확인'),
 ('Measure','facility-count','시설 수','land','시설수|시설 수','정의된 종류의 시설 개수.','시설 유형·운영 상태·중복 등록 확인'),
 ('Measure','production','생산량','agriculture','생산량','정해진 품목·지역·기간의 생산 규모.','품목·규격·중량 단위 확인'),
 ('Measure','area','면적','land','면적|총면적','공간 또는 대상의 넓이.','대상 범위·제곱미터/헥타르 등 단위 확인'),
 ('EntityType','person','사람','population','사람','사람을 가리키는 대상 종류.','개인 레코드 수집·식별 승인을 뜻하지 않음'),
 ('EntityType','household','가구','population','가구','함께 생활하는 단위 등 출처가 정의한 가구.','세대와 동일 개념으로 자동 병합 금지'),
 ('EntityType','school','학교','education','학교|학교명','교육기관으로서의 학교.','학교 종류·분교·학교 코드 체계 확인'),
 ('EntityType','company','기업','industry','기업|회사|회사명|기업명','기업 또는 공시 대상 회사.','사업체·법인·사업자 단위 구분'),
 ('EntityType','establishment','사업체','industry','사업체|사업체명','사업 활동을 하는 장소 또는 통계상의 사업체.','기업·법인과 별개로 관리'),
 ('EntityType','bus-stop','버스정류장','transport','버스정류장|정류장명','버스가 정차하는 지점 또는 정류장 시설.','상하행·표준 ID·ARS 번호 구분'),
 ('EntityType','road','도로','transport','도로|도로명|노선명','도로 또는 노선으로 기술된 대상.','버스 노선과 도로 노선을 문맥으로 구분'),
 ('EntityType','observation-station','관측소','environment','관측소|관측소명','기상·수문 등의 관측 지점.','기관별 코드 체계·관측 종류 확인'),
 ('EntityType','library','도서관','culture','도서관|도서관명','도서관 시설 또는 운영기관.','시설과 운영기관 구분'),
 ('EntityType','book','도서','culture','도서|도서명','도서 자료 또는 출판물.','판본·권차·복본과 ISBN 범위 확인'),
 ('EntityType','hospital','의료기관','health','병원|의료기관|병원명|요양기관명','의료 서비스를 제공하는 기관 또는 시설.','기관 종류·사업장·코드 체계 확인'),
 ('EntityType','park','공원','land','공원|공원명','공원으로 등록되거나 분류된 공간.','법적 종류·경계·시설 단위 확인'),
 ('EntityType','youth','청년','employment','청년','청년이라는 대상 범주.','연령 경계를 고정하지 않음·사업과 통계마다 확인'),
 ('Dimension','sex','성별','population','성별|성별구분','출처의 성별 분류 체계.','코드값·미상·전체 포함 여부 확인'),
 ('Dimension','age-group','연령 구간','population','연령별|연령계층별|연령대|연령','나이 또는 연령 구간으로 대상을 나누는 기준.','만 나이·구간 경계·개별 나이와 구간 구분'),
 ('Dimension','nationality','국적','population','국적|국적별','국적에 따른 구분.','국적과 체류자격·출신지 구분'),
 ('Dimension','industry-class','산업 분류','industry','산업별|산업분류|산업분류코드','사업 활동의 산업 분류.','분류 차수·코드 자릿수 확인'),
 ('Dimension','occupation','직업 분류','employment','직업별|직업분류|전직업별','직업에 따른 구분.','현재·이전 직업 및 분류 차수 확인'),
 ('Dimension','education-level','교육 정도','education','교육정도별|교육정도|학력','학력 또는 교육 정도의 분류.','재학·졸업·중퇴와 단계 구분'),
 ('Dimension','vehicle-type','차종','transport','차종|차종구분코드','차량 종류의 분류.','톨게이트 요금 분류와 차종 통계 분류 구분'),
 ('SpatialReference','administrative-area','행정구역','land','행정구역|행정구역 이름|행정구역명|시도별|시군구별','행정상 구획으로 공간을 나누는 기준.','계층·행정동/법정동·경계 기준일 확인'),
 ('SpatialReference','administrative-dong','행정동','land','행정동|행정동명','행정동 기준의 공간 구분.','법정동과 자동 동일시하지 않음'),
 ('SpatialReference','legal-dong','법정동','land','법정동|법정동명','법정동 기준의 공간 구분.','행정동 대응표·기준일 필요'),
 ('SpatialReference','census-area','집계구','population','집계구|집계구코드','통계 작성에 쓰이는 집계구 공간 단위.','경계와 코드 버전·행정구역 대응표 확인'),
 ('SpatialReference','address','주소','land','주소|도로명주소|소재지도로명주소','대상 위치를 표현한 주소 정보.','지번/도로명·정규화·건물/사업장 단위 확인'),
 ('SpatialReference','latitude','위도','land','위도|LAT','위치를 나타내는 위도 성분.','좌표계·도분초/십진도 확인'),
 ('SpatialReference','longitude','경도','land','경도|LON','위치를 나타내는 경도 성분.','좌표계·도분초/십진도 확인'),
 ('TemporalReference','reference-date','기준일','administration','기준일|기준일자|사용일자|기준일ID','관측·이용 집계의 기준 날짜.','서비스 사용일·추출일·수정일 구분'),
 ('TemporalReference','reference-month','기준월','administration','기준월|사용년월|기준년월','관측·이용 집계의 기준 월.','월 합계·월평균·월말 값 구분'),
 ('TemporalReference','reference-year','기준연도','administration','기준연도|기준년도|사업 연도|연도','관측이나 보고의 기준 연도.','달력연도·회계연도·조사연도 구분'),
 ('TemporalReference','reference-time','관측 시각·시간대','administration','관측시각|시간대구분|집계시간|YMDHM','관측 시점 또는 시간 구간.','시점/구간·시간대·누적 간격 확인'),
 ('TemporalReference','period','통계 기간','administration','기간|수록기간','자료가 제공하는 기간과 주기.','월/분기/연도와 자료 실제 가용 범위 확인'),
 ('IdentifierScheme','area-code','행정구역 코드','land','행정구역 코드|행정구역코드|adm_cd','행정구역 식별을 위한 코드 계열.','기관·자릿수·계층·개정 버전 확인'),
 ('IdentifierScheme','dong-code','행정동 코드','land','행정동코드|ADSTRD_CODE_SE','행정동 식별용 코드 계열.','법정동 코드와 자동 결합 금지'),
 ('IdentifierScheme','school-code','학교 식별 코드','education','행정표준코드|학교코드|SD_SCHUL_CODE','학교를 식별하는 코드로 쓰이는 항목 후보.','행정표준코드라는 이름만으로 학교 코드 단정 금지'),
 ('IdentifierScheme','corp-code','공시 회사 코드','economy','corp_code','공시 대상 회사의 코드로 쓰이는 항목 후보.','사업자등록번호·법인번호와 구분'),
 ('IdentifierScheme','business-code','사업자등록번호','industry','사업자등록번호','사업자등록 단위 식별번호.','법인·사업장·공시회사 코드와 구분'),
 ('IdentifierScheme','stop-code','버스정류장 식별 코드','transport','표준버스정류장ID|STOPS_ID','버스정류장을 식별하는 표준 ID 항목 후보.','ARS 번호·노선별 순번과 구분'),
 ('IdentifierScheme','route-code','노선 식별 코드','transport','노선ID|RTE_ID','교통 노선을 식별하는 코드 항목 후보.','노선번호·도로노선 ID와 범위 확인'),
 ('IdentifierScheme','isbn','ISBN','culture','13자리 ISBN|isbn13|ISBN','출판물 식별 체계 ISBN.','10/13자리·판본·세트·복본 구분'),
 ('IdentifierScheme','rain-station-code','강수 관측소 코드','environment','RFOBSCD','강수 관측소의 식별 코드 항목 후보.','기관별 코드·개폐소·지점 이력 확인'),
 ('Unit','person','명','population','명','인원 계수 단위 후보.','자료에서 보고한 배율·실인원/건수 확인'),
 ('Unit','thousand-person','천 명','population','천명|천 명','인원 천 단위 후보.','명을 천명과 그대로 비교하지 않음'),
 ('Unit','percent','퍼센트','economy','%|퍼센트','백분율 단위 후보.','분모와 퍼센트포인트 차이 구분'),
 ('Unit','millimeter','밀리미터','environment','mm','길이 단위 후보.','강수량의 누적 기간은 별도 기준'),
 ('Unit','won','원','economy','원','원화 금액 단위 후보.','천원·백만원·물가 기준 구분'),
 ('Unit','square-meter','제곱미터','land','㎡|m²|m2','면적 단위 후보.','문서의 단위와 환산 가능성 확인')]

DISTINCTIONS=[('living-population','registered-population','측정 대상과 산출 방법이 다르므로 자동 동의어 처리하지 않는다.'),
 ('unemployment-rate','unemployed-count','비율과 인원수는 다른 지표다.'),
 ('unemployed-count','inactive-count','경제활동 상태의 정의를 대조해야 한다.'),
 ('administrative-dong','legal-dong','서로 다른 공간 구분이며 대응표가 필요하다.'),
 ('company','establishment','기업과 개별 사업체의 집계 단위가 다를 수 있다.'),
 ('corp-code','business-code','식별 체계와 식별 대상이 다르다.'),
 ('person','thousand-person','단위 배율을 확인해야 한다.')]

def seed_model():
    concepts=[]
    for slug,label,aliases in TOPICS:
        concepts.append({'id':'topic:'+slug,'kind':'Topic','label':label,'aliases':aliases.split('|'),
            'working_definition':label+' 관련 자료를 탐색하기 위한 프로젝트 주제 묶음.',
            'scope_checks':['공식 단일 분류체계가 아님','다중 주제 허용·포털 원분류를 보존'],
            'topics':[],'status':'project_draft','human_approved':False})
    for kind,slug,label,topic,aliases,definition,checks in ROWS:
        concepts.append({'id':kind.lower()+':'+slug,'kind':kind,'label':label,'aliases':aliases.split('|'),
            'working_definition':definition,'scope_checks':checks.split('·'),'topics':['topic:'+topic],
            'status':'project_draft','human_approved':False})
    by_slug={c['id'].split(':',1)[1]:c['id'] for c in concepts}
    edges=[]
    for c in concepts:
        for topic in c['topics']:edges.append({'id':'topic-membership:'+c['id'],'source':c['id'],'predicate':'inTopic','target':topic,
            'status':'project_proposal','human_approved':False,'rationale':'탐색 분야 배치이며 하위 클래스나 상관관계를 뜻하지 않는다.'})
    for a,b,why in DISTINCTIONS:
        # person and household slugs occur in more than one facet; references here resolve intentionally.
        a_id='unit:person' if a=='person' else by_slug[a]
        edges.append({'id':'distinction:'+a+':'+b,'source':a_id,'predicate':'distinguishFrom','target':by_slug[b],
            'status':'project_proposal','human_approved':False,'rationale':why})
    return {'version':'0.1.0','scope':'국내 전 분야 메타데이터에 연결하는 공통 개념 초안',
        'facets':{k:{'label':v[0],'description':v[1]} for k,v in FACETS.items()},'concepts':concepts,'relationships':edges,
        'rules':{'all_definitions_are_project_drafts':True,'aliases_are_matching_candidates_not_approved_synonyms':True,
            'source_occurrence_does_not_validate_semantics':True,'region_is_not_parent_class_of_unemployment_rate':True,
            'unknown_unit_or_code_version_stays_unknown':True,'no_statistical_association_generated':True},
        'not_yet_implemented':['전국의 모든 개념을 포괄하는 공식 사전','Formal OWL reasoning','Automatic sameAs/joinability approval']}
