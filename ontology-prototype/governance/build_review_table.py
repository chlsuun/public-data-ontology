"""Render every current model relation as a human-readable review checklist."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "ontology-prototype/discovery-platform/model.json"


def cell(value):
    return str(value).replace("|", "&#124;").replace("\n", " ")


def main():
    source = MODEL.read_text(encoding="utf-8")
    model = json.loads(source)
    nodes = {n["id"]: n for n in model["nodes"]}
    evidence = {e["id"]: e for e in model["source_evidence"]}
    positions = {r["id"]: next(i for i, line in enumerate(source.splitlines(), 1) if f'"id": "{r["id"]}"' in line) for r in model["relations"]}
    groups = [
        ("context_hypothesis", "함께 탐색할 맥락 가설", "함께 찾아볼 관련성이 있다는 제안", "해당 맥락을 연결할 문헌·공식 설명 또는 적용 사례를 확인한다. 통계적 연관성을 주장하려면 변수·지역·기간·연령을 정한 별도 분석이 필요하다."),
        ("metadata_mapping", "지표와 실제 자료의 대응", "이 자료에서 해당 지표를 찾을 수 있다는 연결", "실제 표/API에서 항목 코드·연령·지역·기간·단위를 확인한다. 원문 설명만 확인한 상태와 필요한 계열을 조회한 상태를 구분한다."),
        ("indicator_definition", "개념과 측정 지표", "이 개념을 살펴볼 지표라는 편집 정의", "공식 지표 정의·산식·분모·단위·대상 범위를 확인한다. 이 관계만으로 해당 자료가 확보됐다고 판단하지 않는다."),
        ("source_provenance", "자료와 제공기관", "해당 기관을 통해 자료가 제공된다는 연결", "원문 자료 ID와 제공기관을 대조한다. 제공 경로와 원생산기관은 별도로 확인한다."),
        ("query_interpretation", "질문과 개념", "질문을 해당 개념으로 해석한 예시", "질문의 의도와 개념이 맞는지 확인하고, 정해지지 않은 지역·기간·연령 조건을 기록한다. 통계분석 대상이 아니다."),
    ]
    states = {"candidate": "후보", "curated": "편집 정의", "documented": "공식 설명 근거 있음"}
    counts = Counter(r["status"] for r in model["relations"])
    lines = [
        "# model.json 관계 검토표", "",
        f"기준: v{model['version']} / 총 {len(model['relations'])}개 관계. [원본 모델](../ontology-prototype/discovery-platform/model.json#L557)의 ID를 사람이 읽을 이름으로 풀어 쓴 목록이다.", "",
        f"상태: 후보 {counts['candidate']}개 · 편집 정의 {counts['curated']}개 · 공식 설명 근거 {counts['documented']}개. 이 상태는 새 사람 승인 절차의 완료 표시가 아니다.", "",
        "이 표는 검토 대상을 정하는 읽기용 생성 파일이다. 검토 결론은 [검토 기록 양식](../ontology-prototype/governance/record-templates.json)에 별도로 남긴다. 다시 생성하면 이 표의 직접 수정 내용은 보존되지 않는다.", "",
        "## 읽는 방법", "",
        "1. 연결된 두 개체와 관계 종류를 확인한다.",
        "2. ‘함께 탐색’, ‘해당 지표 제공’, ‘같은 자료로 결합’, ‘통계적 연관’ 중 무엇을 주장하는지 구분한다.",
        "3. 관계 ID로 원본 위치를 열고 근거·자료 조건을 확인한다.",
        "4. 출처 확인, 실제 계열 검사 또는 별도 분석 중 필요한 작업을 정한다.",
        "5. 검토자·날짜·근거·적용 범위와 승인/수정 요청/기각 결정을 별도 기록한다.", "",
        "현재 모델에는 실측 상관계수나 확정 인과관계가 없다. 아래 가설을 상관분석 대상으로 쓰려면 먼저 분석 질문과 입력 자료를 구체화해야 한다.", "",
    ]
    emitted = []
    for role, title, meaning, method in groups:
        relations = [r for r in model["relations"] if r["role"] == role]
        lines += [f"## {title} — {len(relations)}개", "", meaning + ".", "", "검토: " + method, "", "| 관계 ID · 원본 위치 | 연결 | 기존 근거 상태 | 현재 주의점 | 근거 |", "|---|---|---|---|---|"]
        for r in relations:
            a, b = nodes[r["source"]], nodes[r["target"]]
            name_a, name_b = a.get("short", a["label"]), b.get("short", b["label"])
            note = r.get("note") or "관계 유형에 맞게 위 검토 항목을 확인"
            if role == "metadata_mapping":
                note += " " + " / ".join(b.get("limitations", []))
            if b.get("data_gap"):
                note += " 적절한 자료 대응이 아직 확보되지 않음."
            refs = " · ".join(f"[{eid}](#evidence-{eid})" for eid in r["evidence_ids"])
            relation_link = f"[{r['id']}](../ontology-prototype/discovery-platform/model.json#L{positions[r['id']]})"
            lines.append(f"| {relation_link} | {cell(name_a)} → {cell(name_b)} | {states[r['status']]} | {cell(note)} | {refs} |")
            emitted.append(r["id"])
        lines += [""]
    lines += ["## 근거 기록", "", "공식 페이지 링크와 과거 관찰 상태를 함께 표시한다. 이번 표 생성은 원문 재조사나 새 검증이 아니다.", ""]
    for eid in dict.fromkeys(eid for r in model["relations"] for eid in r["evidence_ids"]):
        e = evidence[eid]
        lines += [f'<a id="evidence-{eid}"></a>', f"### {eid}", ""]
        if e.get("url"):
            lines += [f"[원문 출처]({e['url']})", ""]
        else:
            lines += ["[프로젝트 요구사항](../ontology-prototype/discovery-platform/requirements-v0.3.md)에서 가져온 편집 근거. 외부 실증 연구 결과가 아니다.", ""]
        lines += [f"기존 확인 상태: `{e['status']}` · 확인일: {e.get('checked_at') or '기록 없음'}.", ""]
        if e.get("summary"):
            lines += [e["summary"], ""]
    assert len(emitted) == len(set(emitted)) == len(model["relations"])
    assert set(emitted) == {r["id"] for r in model["relations"]}
    lines += ["## 다시 생성", "", "```bash", "python ontology-prototype/governance/build_review_table.py", "```", "", f"모델 내용 해시(UTF-8, LF): `{sha256(source.encode('utf-8')).hexdigest()}`", ""]
    output = ROOT / "docs/relations-review.md"
    output.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(json.dumps({"file": str(output.relative_to(ROOT)), "relations": len(emitted), "source_model_version": model["version"]}))


if __name__ == "__main__":
    main()
