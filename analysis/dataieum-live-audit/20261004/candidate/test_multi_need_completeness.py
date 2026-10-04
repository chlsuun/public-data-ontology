import copy

from discovery_harness.similarity_results import compose_similarity_result
from discovery_harness.site_search import node_plan, validate_plan


SOURCES = [{"id": "kosis", "name": "KOSIS 국가통계포털", "url": "https://kosis.kr"}]


def plan():
    value = node_plan("population")
    value["needs"].append(node_plan("employment")["needs"][0])
    value["semantic_query"] = "청년 인구와 청년 실업률 / youth population and youth unemployment rate"
    value["related_mode"] = "exclude"
    return validate_plan(value)


def candidate(identifier, title, need, cosine):
    return {
        "dataset_id": identifier,
        "source_id": "kosis",
        "cosine": cosine,
        "checked_at": "2026-10-04",
        "input_hash": "a" * 64,
        "metadata": {"title": title, "url": f"https://kosis.kr/{identifier}"},
        "relevance_tier": "direct",
        "relevance_need": need,
        "relevance_exclusions": [],
        "relevance_evidence": [
            {"condition": "relevance_context", "field": "title", "quote": title}
        ],
    }


def retrieval(count):
    return {
        "selection": {"candidate_sites": 1 if count else 0},
        "relevance": {
            "version": "metadata-relevance-v3",
            "eligible_candidates": count,
            "judged_candidates": count,
            "omitted_for_budget": 0,
            "accepted_candidates": count,
        },
    }


def test_partial_when_one_requested_need_is_missing():
    result = compose_similarity_result(
        plan(),
        [candidate("population", "서울 청년 인구", 1, 0.91)],
        SOURCES,
        retrieval(1),
    )

    assert result["state"] == "partial"
    assert [group["indicator"] for group in result["groups"]] == ["population", "employment"]
    assert len(result["groups"][0]["sites"]) == 1
    assert result["groups"][1]["sites"] == []
    assert result["retrieval"]["selection"]["missing_needs"] == ["employment"]


def test_results_only_when_every_requested_need_is_verified():
    candidates = [
        candidate("population", "서울 청년 인구", 1, 0.91),
        candidate("employment", "서울 청년 실업률", 2, 0.89),
    ]
    result = compose_similarity_result(plan(), candidates, SOURCES, retrieval(2))

    assert result["state"] == "results"
    assert all(group["sites"] for group in result["groups"])
    assert result["retrieval"]["selection"]["missing_needs"] == []


if __name__ == "__main__":
    test_partial_when_one_requested_need_is_missing()
    test_results_only_when_every_requested_need_is_verified()
    print("multi-need completeness tests passed")
