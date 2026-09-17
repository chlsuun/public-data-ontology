"""Publish a readable collection decision alongside the fixed graph. No network."""
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / 'ontology-prototype/domestic-catalog'
OUT = ROOT / 'docs'
BRANCH = 'codex/ontology-collection-share-20260915'
REPO = 'https://github.com/chlsuun/public-data-ontology/tree/' + BRANCH


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    a = read(CAT / 'collection-sufficiency-assessment.json')
    c = read(CAT / 'coverage-report.json')
    g = read(OUT / 'graph-data/overview.json')
    p = read(CAT / 'completion-policy.json')
    assert a['decision'] == 'sufficient_for_prototype' and p['bulk_collection_enabled'] is False
    assert g['counts']['catalog_records'] == c['total_catalog_records']
    assert g['counts']['documented_fields'] == c['documented_column_occurrences']
    names = {x['id']: x['research_name'] for x in read(CAT / 'inventory/domestic-portals.json')['portals']}
    public = {k:a[k] for k in ['decision','purpose','decision_basis','criteria','counts','topics',
                              'concept_facets','limitations','next_phase']}
    public.update(catalog_snapshot_at=c['generated_at'], graph_snapshot_at=g['generated_at'],
                  published_branch=BRANCH, graph_counts=g['counts'],
                  collection_state=p['collection_state'], national_complete=False,
                  ontology_complete=False, automatic_bulk_collection=False,
                  portal_counts=c['portal_counts'])
    public['limitations'] = [x for x in public['limitations'] if not x.startswith('공유 지식그래프는')]
    public['limitations'].append('공유 그래프는 수집 종료 후 검색 DB의 등록정보와 명세 항목을 반영한 고정 스냅샷이다. 개념 사전의 선별 사례는 이전 검토용 스냅샷을 유지한다.')
    (OUT/'collection-data.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    stamp = datetime.fromisoformat(c['generated_at']).astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST')
    cards = ''.join(f'<div class="card"><small>{escape(label)}</small><strong>{value:,}</strong><span>{escape(note)}</span></div>'
        for label,value,note in [
            ('목록을 확보한 포털', c['portals_with_catalog_acquisition'], '국내 제공처 후보 125곳 중 부분 수집'),
            ('데이터셋 등록정보', c['total_catalog_records'], '분류 경로·제공기관·포털 간 중복 포함'),
            ('원문 명세 항목', c['fields_in_source_definition_documents'], '반복 출현 포함 · 고유 분석 변수 수가 아님'),
            ('공통 개념 초안', g['counts']['project_concepts'], '8가지 역할 · 사람의 의미 검토 전')])
    criteria = ''.join('<li>'+escape(x['criterion'])+'</li>' for x in a['criteria'])
    topics = ''.join('<span class="tag">'+escape(x['label'])+'</span>' for x in a['topics'])
    rows = ''.join(f'<tr><th scope="row"><a href="./?view=registrations&amp;portal={escape(x["portal_id"])}">{escape(names.get(x["portal_id"],x["portal_id"]))}</a></th>'
        + ''.join(f'<td>{x[k]:,}</td>' for k in ['catalog_records','fields_in_source_definition_documents','records_with_documented_columns'])+'</tr>'
        for x in c['portal_counts'])
    limitations = ''.join('<li>'+escape(x)+'</li>' for x in public['limitations'])
    next_steps = ''.join('<li>'+escape(x)+'</li>' for x in a['next_phase'])
    html = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>수집 현황과 다음 단계 · 국내 공공데이터 온톨로지</title>
<style>
:root{{color-scheme:dark;font:16px/1.7 system-ui,'Malgun Gothic',sans-serif;background:#0b1424;color:#dce9f9}}*{{box-sizing:border-box}}body{{margin:0}}main{{max-width:1120px;margin:auto;padding:32px 22px 70px}}a{{color:#87caff}}a:focus-visible{{outline:3px solid #63dcff;outline-offset:4px}}nav{{display:flex;gap:18px;flex-wrap:wrap;font-size:14px}}h1{{font-size:clamp(26px,4vw,38px);line-height:1.4;margin:22px 0 14px}}h2{{font-size:23px;margin-top:34px}}p{{margin:12px 0}}.muted,small{{color:#a3b7cf}}.status{{display:inline-block;color:#72e3cd;background:#13332f;border:1px solid #287061;padding:4px 12px;border-radius:20px;font-size:13px;margin-top:25px}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:25px 0}}.card{{padding:18px;border:1px solid #2b405c;border-radius:10px;background:#122137}}.card strong{{display:block;font-size:28px;color:#f0f7ff}}.card span{{display:block;color:#a3b7cf;font-size:12px;margin-top:8px}}.panel{{background:#101f34;border:1px solid #2b405c;border-radius:12px;padding:18px 24px;margin:20px 0}}.notice{{border-left:3px solid #e0b162;background:#302a20;color:#ebd6ac;padding:14px 18px}}.tags{{display:flex;flex-wrap:wrap;gap:8px}}.tag{{font-size:13px;border:1px solid #335072;border-radius:6px;padding:4px 10px;color:#bce0ff}}li{{margin:9px 0}}.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:11px 13px;border-bottom:1px solid #283d57;text-align:right;white-space:nowrap}}th:first-child{{text-align:left}}thead{{background:#17283f}}tbody th{{font-weight:500}}footer{{border-top:1px solid #2b405c;margin-top:35px;padding-top:20px;font-size:13px;color:#a3b7cf}}@media(max-width:800px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:450px){{.cards{{grid-template-columns:1fr}}main{{padding:24px 16px}}.panel{{padding:14px}}}}
</style></head><body><main>
<nav><a href="./">← 전체 지식 그래프</a><a href="concepts.html">개념 사전</a><a href="{REPO}">GitHub 코드·설계서</a></nav>
<span class="status">자료 확보 단계 종료 · 개념·관계 검토 준비</span>
<h1>무엇을 모았고,<br>이제 무엇을 검토할까?</h1>
<p>국내 공공데이터를 의미로 탐색하고 연결하기 위한 메타데이터를 모았습니다. 현재 자료는 <strong>온톨로지 프로토타입의 개념·관계 설계를 시작하기에 충분하다</strong>고 판단해 대량 자동 수집을 종료했습니다.</p>
<p class="muted">최종 수집 DB 기준: {stamp} · 로그인이나 설치 없이 볼 수 있는 팀 공유본</p>
<div class="cards">{cards}</div>
<div class="notice">전국 모든 공공데이터를 수집했다는 뜻은 아닙니다. 실제 관측값 전체·기관 내부 DB·통계적 상관관계 분석 결과는 포함하지 않습니다. 의미 관계는 사람이 검토할 후보입니다.</div>
<h2>수집한 자료를 보는 순서</h2><div class="panel"><p><strong>포털 → 등록 자료 → 원문 명세 항목 → 공통 개념 후보 → 출처 근거</strong></p><p>그래프에서 포털을 고르고, ‘출처 경로 펼치기’에서 자료와 항목을 확인하세요. 개념과 연결되지 않은 항목도 ‘등록 자료’와 전체 항목 검색에서 찾을 수 있습니다.</p><p><a href="./">지식 그래프 열기 ↗</a> · <a href="./?view=registrations">등록 자료 전체 보기 ↗</a></p></div>
<h2>충분하다고 판단한 근거</h2><ul>{criteria}</ul>
<p>아래 16개 분야는 프로젝트의 탐색 분류입니다. 각 분야의 모든 기관·개념·자료를 빠짐없이 확보했다는 의미는 아닙니다.</p><div class="tags">{topics}</div>
<h2>포털별 확보 범위</h2><p class="muted">포털 이름을 누르면 해당 포털의 등록 자료로 이동합니다. ‘명세 항목’은 문서별 출현 수이며, 명세를 확보한 등록정보 수와 단위가 다릅니다.</p>
<div class="table-wrap"><table><thead><tr><th scope="col">포털</th><th scope="col">등록정보</th><th scope="col">원문 명세 항목</th><th scope="col">명세 확보 등록정보</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>다음 단계</h2><ol>{next_steps}</ol>
<p>추가 수집은 특정 관계를 검토하다 필요한 근거가 부족할 때, 해당 출처와 명세를 정해서 진행합니다. 기존 자료·미처리 큐·오류 기록은 보존했습니다.</p>
<details class="panel"><summary>해석할 때 확인할 한계</summary><ul>{limitations}</ul></details>
<footer><a href="collection-data.json" download>수집 현황·판단 근거 JSON 내려받기</a> · <a href="graph-data/overview.json" download>지식 그래프 개요 JSON 내려받기</a><p>포털 이름이나 칼럼명이 같다는 이유만으로 의미 동일성·자료 결합 가능성·품질 점수를 확정하지 않습니다.</p></footer>
</main></body></html>'''
    (OUT/'collection.html').write_text(html,encoding='utf8')
    concepts = OUT/'concepts.html'
    text = concepts.read_text(encoding='utf8').replace('codex/knowledge-graph-sharing-20260914', BRANCH)
    if 'href="collection.html"' not in text:
        text = text.replace('<h1>공통 개념 사전</h1>', '<p><a href="collection.html">최종 수집 현황과 다음 단계 ↗</a></p><h1>공통 개념 사전</h1>')
    concepts.write_text(text,encoding='utf8')
    print('Rendered collection.html and collection-data.json; graph and collection counts agree.')


if __name__ == '__main__':
    main()
