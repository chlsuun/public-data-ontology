"""Render Pages entry points from the locally tested graph UI."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'ontology-prototype/domestic-catalog/concepts'
html=(src/'graph.html').read_text(encoding='utf8')
html=html.replace('<script>', '<script src="graph-static.js"></script>\n<script>', 1)
html=html.replace("await fetch('/api/concepts/graph/", "await shareFetch('/api/concepts/graph/")
html=html.replace('href="/api/concepts/graph/overview?download=1"', 'href="graph-data/overview.json" download')
html=html.replace('href="/concepts#', 'href="concepts.html#')
html=html.replace('href="/concepts"', 'href="concepts.html"')
html=html.replace('href="/"', 'href="?view=registrations"')
html=html.replace('href="/?record=', 'href="?view=paths&mode=all&record=')
html=html.replace('수집된 칼럼 전체 보기', '이 자료의 원문 항목 보기')
html=html.replace('수집된 자료 상세', '이 자료의 원문 항목')
html=html.replace('수집 자료 상세', '이 자료의 원문 항목')
html=html.replace('자료 상세 ↗', '원문 항목 ↗')
html=html.replace('<a href="?view=paths&mode=all&record=${encodeURIComponent(r.id)}" target="_blank" rel="noopener noreferrer">이 자료의 원문 항목 ↗</a>', '<a href="${esc(safe(r.url))}" target="_blank" rel="noopener noreferrer">공식 자료 페이지 ↗</a>')
html=html.replace('공공데이터 전체 지식 그래프</h1>', '공공데이터 전체 지식 그래프</h1><p class="sub">팀 공유용 스냅샷 · 로그인 없이 탐색할 수 있습니다.</p>')
html=html.replace('<main class="wrap">', '<main class="wrap"><p class="notice">프로토타입 설계에 필요한 자료 확보를 마쳐 대량 수집을 종료했습니다. <a href="collection.html">최종 수집 범위·종료 판단·다음 작업 보기 ↗</a></p>', 1)
if 'href="collection.html"' not in html:
    html=html.replace('</header>', '</header><div class="wrap"><p class="notice">프로토타입 설계에 필요한 자료 확보를 마쳐 대량 수집을 종료했습니다. <a href="collection.html">최종 수집 범위·종료 판단·다음 작업 보기 ↗</a></p></div>', 1)
old="history.replaceState(null,'','/concepts/graph?'+new URLSearchParams(Object.entries(f).filter(([k,v])=>v&&!(k==='mode'&&v==='mapped'))))"
assert old in html
html=html.replace(old,'syncState()')
sync="""function syncState(){if(!DATA)return;const f=filter();history.replaceState(null,'',location.pathname+'?'+new URLSearchParams(Object.entries({...f,view:mode,page:String(page),pending:$('pending').checked?'1':''}).filter(([k,v])=>v&&!(k==='mode'&&v==='mapped')&&!(k==='page'&&v==='1'))))}
"""
html=html.replace('function setMode(next){mode=next;',sync+'function setMode(next){mode=next;syncState();')
html=html.replace('async function loadPaths(){const req=', 'async function loadPaths(){syncState();const req=')
html=html.replace("$('pending').onchange=makeOverview", "$('pending').onchange=()=>{syncState();makeOverview()}")
assert 'resize();applyFilters(false)' in html
html=html.replace('resize();applyFilters(false)',"recordFilter=params.get('record')||'';page=Math.max(1,Number(params.get('page'))||1);$('pending').checked=params.get('pending')==='1';setMode(['overview','paths','registrations'].includes(params.get('view'))?params.get('view'):'overview');resize();overviewInspector();loadPaths()")
assert 'href="/' not in html
(ROOT/'docs/index.html').write_text(html,encoding='utf8')
(ROOT/'docs/.nojekyll').write_text('',encoding='utf8')
print('Rendered docs/index.html')
