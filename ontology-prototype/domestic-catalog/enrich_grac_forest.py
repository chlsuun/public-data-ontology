"""Attach source navigation observations without rebuilding other portal inventories."""
from common import *
from urllib.parse import urljoin
import re

def main():
    body,r=fetch('forest-public-home-20260914','https://data.forest.go.kr/')
    soup=BeautifulSoup(body,'html.parser');moves=[]
    for sn,s in enumerate(soup.select('script')):
        for ln,line in enumerate(s.get_text().splitlines()):
            if line.strip().startswith('//'):continue
            m=re.search(r'document\.location\.href\s*=\s*"([^"]+)"',line)
            if m:moves.append({'target_url_as_reported':m[1],'source_statement':line.strip(),
                'locator':f'script[{sn}] line[{ln}]','evidence_id':r['id'],'mechanism':'static_javascript_location_assignment'})
    assert len(moves)==1
    target=read(HERE/'evidence/forest-data-redirect-target.json')
    assert target['requested_url']==moves[0]['target_url_as_reported'] and target['status']=='fetched'
    move={'generated_at':now(),'landing_url':r['requested_url'],'moves':moves,
        'public_overview_final_url':target['final_url'],'overview_evidence_id':target['id'],
        'catalog_url':read(HERE/'evidence/forest-public-catalog-page1.json')['requested_url'],
        'catalog_navigation_evidence_id':'forest-data-redirect-target',
        'closed_or_unavailable_inferred':False,'noscript_and_commented_legacy_routes_not_used':True}
    dump(HERE/'inventory/forest-navigation-observations.json',move)
    body,r=fetch('grac-public-data-disclosure','https://www.grac.or.kr/OpenBook/informPublic12.aspx')
    content=BeautifulSoup(body,'html.parser').select_one('.contentBody')
    navigation=[{'label':a.get_text(' ',strip=True),'url':urljoin(r['requested_url'],a['href']),
        'locator':f'.contentBody a[href][{n}]','evidence_id':r['id']}
        for n,a in enumerate(content.select('a[href]')) if not a['href'].startswith('javascript:')]
    assert len(navigation)==3
    dump(HERE/'inventory/grac-disclosure-navigation.json',{'generated_at':now(),'evidence_id':r['id'],'links':navigation,
        'dataset_listing_table_observed':False,'staff_contact_table_not_used_as_dataset_schema':True,
        'source_navigation_not_an_all_agency_dataset_census':True})
    qa=read(HERE/'grac-source-qa.json')
    qa['public_disclosure_navigation']='inventory/grac-disclosure-navigation.json'
    qa['remaining_scope']=['Public data portal agency-specific catalog reconciliation','Runtime schema vs documentation validation','File column definitions and non-API catalogs']
    dump(HERE/'grac-source-qa.json',qa)
    registry=read(HERE/'inventory/domestic-portals.json')
    for p in registry['portals']:
        if p['id']=='forest':
            p.update(observation_status='public_catalog_and_html_guides_observed',catalog_collected=True,
                catalog_entry_url=move['catalog_url'],current_official_overview_url=target['final_url'],
                navigation_observations='inventory/forest-navigation-observations.json',
                operational_status='public_catalog_documents_accessible_data_services_not_tested',
                next_action='외부 참조·지도 파일 속성사전·다른 산림청 목록을 계속 조사')
            p['notes']=list(dict.fromkeys(p['notes']+['기존 짧은 안내 페이지의 실제 이동 문장을 따라 현재 산림청 공개 목록 5개 분류·56개 등록을 확인했다. 전체 제공 건수 표시는 없다.']))
            p['evidence_ids']=list(dict.fromkeys(p['evidence_ids']+['forest-public-home-20260914','forest-data-redirect-target','forest-public-catalog-page1']))
        elif p['id']=='grac':
            p.update(observation_status='two_public_api_guides_observed',catalog_collected=True,
                catalog_scope_note='OPEN API 게임·채용 가이드 2개이며 기관 전체 자료 목록이 아님',
                operational_status='public_definition_documents_accessible_data_services_not_tested',
                next_action='공공데이터포털 기관별 목록과 연결 대조, 파일 명세·문서 간 불일치 검증')
            p['evidence_ids']=list(dict.fromkeys(p['evidence_ids']+['grac-game-guide','grac-recruit-usage','grac-public-data-disclosure']))
    dump(HERE/'inventory/domestic-portals.json',registry)
    model=read(HERE/'model.json')
    model['instance_files'].update(grac_source_qa='grac-source-qa.json',forest_source_qa='forest-source-qa.json',
        forest_navigation_observations='inventory/forest-navigation-observations.json',
        grac_disclosure_navigation='inventory/grac-disclosure-navigation.json')
    dump(HERE/'model.json',model)
    path=HERE/'browser.html';html=path.read_text(encoding='utf-8')
    if "grac:'게임물관리위원회 Open API'" not in html:
        html=html.replace("foodsafety:'식품안전나라 데이터활용서비스'", "foodsafety:'식품안전나라 데이터활용서비스',grac:'게임물관리위원회 Open API',forest:'산림청 공공데이터 개방목록'")
    if "'grac-collection-report.json'" not in html:
        html=html.replace("const labels={", "const labels={'grac-collection-report.json':'게임물관리위원회 · 공개 API 가이드','forest-collection-report.json':'산림청 · 공개 목록과 HTML 명세',")
    path.write_text(html,encoding='utf-8')
    print('Registry, model references and browser labels updated; national completeness remains false.')

if __name__=='__main__':main()
