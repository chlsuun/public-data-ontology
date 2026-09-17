"""Check the review migration and QA arithmetic using synthetic test inputs only."""
from copy import deepcopy
import json
from pathlib import Path
from score_qa import score

ROOT = Path(__file__).resolve().parent


def main():
    workspace = json.loads((ROOT / "review-workspace.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "qa-policy.json").read_text(encoding="utf-8"))
    workflow = json.loads((ROOT / "workflow-policy.json").read_text(encoding="utf-8"))
    legacy = json.loads((ROOT.parent / "discovery-platform/model.json").read_text(encoding="utf-8"))
    checks = []

    def check(name, ok):
        checks.append({"name": name, "passed": bool(ok)})

    def rejects(name, metrics):
        try:
            score(metrics)
        except ValueError:
            check(name, True)
        else:
            check(name, False)

    tasks = workspace["relation_review_tasks"]
    old = {r["id"]: r for r in legacy["relations"]}
    check("기존 관계와 근거 상태 보존", len(tasks) == len(old) and {t["relation_id"] for t in tasks} == set(old) and all(t["legacy_evidence_status"] == old[t["relation_id"]]["status"] for t in tasks))
    check("기존 공식 근거를 사람의 승인으로 자동 승격하지 않음", all(t["workflow_state"] == "proposed" and t["reviewer_id"] is None and t["decision"] is None for t in tasks) and workspace["confirmed_relation_ids"] == [] and workspace["human_reviews_recorded"] == 0)
    check("관계별 검토 방법과 변경 감지 해시", all(t["review_method"] and len(t["proposal_fingerprint"]) == 64 for t in tasks))
    qa = workspace["qa_assessments"]
    check("기존 6개 자료 QA 준비 및 원본 버전 미확인 표시", {a["dataset_id"] for a in qa} == {d["id"] for d in legacy["datasets"]} and all(a["dataset_version"] is None and a["source_sha256"] is None for a in qa))
    check("미검사 자료에 품질 점수 생성 금지", all(a["calculated"]["overall_score"] is None and all(v is None for v in a["calculated"]["scores"].values()) for a in qa) and workspace["data_rows_inspected"] == 0)
    check("네 사이트별 QA 프로파일과 공통 가중치", set(policy["site_profiles"]) == {"kosis", "data_go_kr", "oecd", "world_bank"} and abs(sum(policy["weights"].values()) - 1) < 1e-9)
    check("AI·인기도는 승인 권한이 아님", workflow["approval_requirements"]["ai_may_approve"] is False and workflow["approval_requirements"]["community_votes_may_approve"] is False)
    check("500GB 작업은 작은 웹 요청에 활성화하지 않음", workflow["delivery"]["unbounded_500gb_ingestion_enabled"] is False)
    blank = score({})
    check("빈 측정은 0점 대신 미평가", blank["status"] == "not_assessed" and blank["overall_score"] is None and blank["assessment_completion_ratio"] == 0)
    # These numbers are deliberately synthetic, never provider assessments.
    fixture = {
        "reliability_checks": dict(zip(policy["rules"]["reliability"]["checks"], [True, True, True, False])),
        "coverage": {"covered_unique_units": 70, "expected_unique_units": 100},
        "freshness": {"applicability": "applicable", "overdue_release_cycles": 0.3},
        "completeness": {"valid_required_values": 80, "expected_required_values_in_observed_units": 100},
    }
    calculated = score(fixture)
    check("합성 예시의 네 축과 종합 계산", calculated["scores"] == {"reliability": 7.5, "coverage": 7.0, "freshness": 9.0, "completeness": 8.0} and calculated["overall_score"] == 7.8)
    partial = deepcopy(fixture);partial["coverage"]["expected_unique_units"] = None
    check("미평가 축을 빼고 종합 점수를 높이지 않음", score(partial)["overall_score"] is None and score(partial)["assessment_completion_ratio"] == 0.75)
    zeros = {"coverage": {"covered_unique_units": 0, "expected_unique_units": 100}}
    check("실측 0은 0점이며 미평가와 다름", score(zeros)["scores"]["coverage"] == 0 and score(zeros)["status"] == "partial")
    check("분모가 0이면 미평가", score({"coverage": {"covered_unique_units": 0, "expected_unique_units": 0}})["scores"]["coverage"] is None)
    rejects("분자 부풀리기 거부", {"coverage": {"covered_unique_units": 101, "expected_unique_units": 100}})
    rejects("음수 측정 거부", {"completeness": {"valid_required_values": -1, "expected_required_values_in_observed_units": 100}})
    rejects("비정수 관측 수 거부", {"coverage": {"covered_unique_units": 0.5, "expected_unique_units": 10}})
    rejects("숫자 필드에 불리언 거부", {"freshness": {"applicability": "applicable", "overdue_release_cycles": True}})
    rejects("무한대·NaN 측정 거부", {"freshness": {"applicability": "applicable", "overdue_release_cycles": float("nan")}})
    historical = deepcopy(fixture);historical["freshness"] = {"applicability": "not_applicable", "reason": "Synthetic final historical dataset"}
    check("역사 자료 최신성은 미적용·종합 미산출", score(historical)["scores"]["freshness"] is None and score(historical)["overall_score"] is None)
    rejects("미적용 사유 누락 거부", {"freshness": {"applicability": "not_applicable"}})
    delayed = deepcopy(fixture);delayed["freshness"]["overdue_release_cycles"] = 10
    check("장기 지연 점수의 하한", score(delayed)["scores"]["freshness"] == 0)
    check("점수는 제공 권한을 승인하지 않음", not any(k in calculated for k in ("join_allowed", "delivery_allowed", "license_approved")))
    result = {"passed": all(c["passed"] for c in checks), "checks": checks, "scope": "검토 대기열·QA 산식의 로컬 검사. 실제 사람 승인·원본 데이터 품질·전송 성능은 검증하지 않음"}
    (ROOT / "validation-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failures": [c for c in checks if not c["passed"]]}, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
