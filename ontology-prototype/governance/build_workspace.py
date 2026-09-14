"""Create review tasks from the legacy model; never invent approvals or source QA."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from score_qa import score

ROOT = Path(__file__).resolve().parent


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def main():
    model = json.loads((ROOT.parent / "discovery-platform/model.json").read_text(encoding="utf-8"))
    templates = json.loads((ROOT / "record-templates.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "workflow-policy.json").read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in model["nodes"]}
    evidence = {e["id"]: e for e in model["source_evidence"]}
    tasks = []
    for r in model["relations"]:
        snapshot = {"relation": r, "endpoints": [nodes[r["source"]], nodes[r["target"]]], "evidence": [evidence[k] for k in r["evidence_ids"]]}
        tasks.append({
            "relation_id": r["id"], "source": r["source"], "target": r["target"],
            "predicate": r["predicate"], "role": r["role"],
            "legacy_evidence_status": r["status"], "evidence_ids": r["evidence_ids"],
            "import_origin": "legacy_editorial_model_not_live_llm", "workflow_state": "proposed",
            "proposal_fingerprint": digest(snapshot),
            "fingerprint_scope": "Legacy relation, endpoint metadata and evidence records; not an original dataset checksum",
            "review_method": rules["review_methods"][r["role"]],
            "reviewer_id": None, "reviewed_at": None, "decision": None,
            "original_dataset_versions_verified": False,
        })
    assessments = []
    for d in model["datasets"]:
        a = deepcopy(templates["qa_assessment"])
        a.update(assessment_id="qa-pending-" + d["id"], dataset_id=d["id"],
                 site_profile="kosis" if d["id"].startswith("d-kosis-") else "oecd" if d["id"].startswith("d-oecd-") else "world_bank",
                 metadata_snapshot_sha256=digest(d),
                 assessment_reason="Metadata observations exist; original observation values have not been inspected")
        a["calculated"] = score(a["metrics"])
        assessments.append(a)
    output = {
        "version": "0.4.0-draft", "source_model_version": model["version"],
        "generated_file": True, "note": "Preparation only. Do not edit this generated queue as a review ledger; use separate versioned review records.",
        "legacy_relation_status_counts": dict(Counter(r["status"] for r in model["relations"])),
        "relation_review_tasks": tasks, "qa_assessments": assessments,
        "confirmed_relation_ids": [], "human_reviews_recorded": 0,
        "data_rows_inspected": 0, "live_llm_calls": 0,
        "community_and_delivery_services_running": False,
    }
    (ROOT / "review-workspace.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"relation_review_tasks": len(tasks), "qa_pending": len(assessments), "approved": 0, "rows_inspected": 0}))


if __name__ == "__main__":
    main()
