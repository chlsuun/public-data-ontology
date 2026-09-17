"""Validate the semantic retrieval policy without network access."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
policy = json.loads((ROOT / "semantic-retrieval-policy.json").read_text(encoding="utf-8"))

checks = {
    "metadata_not_raw_warehouse": policy["raw_dataset_warehouse"] is False,
    "three_official_semantic_fields": policy["source_fields"]["semantic"] == [
        "title_raw", "description_raw", "keywords_raw"
    ],
    "exact_conditions_are_separate": {"spatial_extent", "temporal_extent", "provider_id"}.issubset(
        policy["source_fields"]["exact_filters"]
    ),
    "raw_metadata_preserved": policy["normalization"]["preserve_raw"] is True,
    "missing_text_is_not_invented": "invent_missing_description" in policy["normalization"]["forbidden"],
    "field_vectors_are_separate": policy["embedding"]["field_strategy"] == "separate_title_description_keywords_vectors",
    "model_version_is_traceable": {"model_id", "model_revision", "input_hash"}.issubset(
        policy["embedding"]["version_fields"]
    ),
    "multiple_topics_supported": policy["retrieval"]["allow_multiple_concepts"] is True,
    "abstention_supported": policy["retrieval"]["allow_abstention"] is True,
    "semantic_score_cannot_override_filter": policy["retrieval"]["semantic_score_may_override_filter_conflict"] is False,
    "official_access_is_returned": "official_page_or_access_url" in policy["retrieval"]["result_requires"],
    "evaluation_has_lexical_baseline": "title_lexical" in policy["evaluation"]["baselines"],
    "evaluation_has_rank_metric": "ndcg_at_10" in policy["evaluation"]["retrieval_metrics"],
    "statistical_correlation_is_not_gate": policy["evaluation"]["correlation_analysis_required"] is False,
    "retrieval_does_not_create_fact": policy["audit"]["search_result_creates_permanent_ontology_relation"] is False,
}

failed = [name for name, passed in checks.items() if not passed]
report = {
    "policy_version": policy["version"],
    "checks": checks,
    "passed": len(checks) - len(failed),
    "failed": failed,
}
(ROOT / "semantic-retrieval-validation.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
if failed:
    raise SystemExit("Validation failed: " + ", ".join(failed))
print(json.dumps(report, ensure_ascii=False))
