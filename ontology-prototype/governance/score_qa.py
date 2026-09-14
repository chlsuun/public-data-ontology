"""Calculate a draft score from explicitly supplied measurements, not source reputation."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def number(value, name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number or null")
    return value


def ratio(values, numerator, denominator):
    a = number(values.get(numerator), numerator)
    b = number(values.get(denominator), denominator)
    if (a is not None and int(a) != a) or (b is not None and int(b) != b):
        raise ValueError("Observation and value counts must be integers")
    if a is not None and b is not None and a > b:
        raise ValueError("The numerator cannot exceed its declared denominator")
    return None if a is None or b in (None, 0) else 10 * a / b


def score(metrics):
    policy = json.loads((ROOT / "qa-policy.json").read_text(encoding="utf-8"))
    checks = metrics.get("reliability_checks", {})
    flags = [checks.get(k) for k in policy["rules"]["reliability"]["checks"]]
    if any(v is not None and not isinstance(v, bool) for v in flags):
        raise ValueError("Reliability checks must be true, false or null")
    reliability = None if any(v is None for v in flags) else 10 * sum(flags) / len(flags)
    freshness = metrics.get("freshness", {})
    applicable = freshness.get("applicability", "unknown")
    if applicable not in ("applicable", "not_applicable", "unknown"):
        raise ValueError("Unknown freshness applicability")
    if applicable == "not_applicable" and not freshness.get("reason"):
        raise ValueError("Not-applicable freshness requires a reason")
    late = number(freshness.get("overdue_release_cycles"), "overdue_release_cycles")
    fresh = None if applicable != "applicable" or late is None else 10 * max(0, 1 - late / policy["rules"]["freshness"]["maximum_delay_cycles"])
    values = {
        "reliability": reliability,
        "coverage": ratio(metrics.get("coverage", {}), "covered_unique_units", "expected_unique_units"),
        "freshness": fresh,
        "completeness": ratio(metrics.get("completeness", {}), "valid_required_values", "expected_required_values_in_observed_units"),
    }
    count = sum(v is not None for v in values.values())
    total = sum(values[k] * w for k, w in policy["weights"].items()) if count == 4 else None
    return {
        "policy_version": policy["version"],
        "scores": {k: round(v, 2) if v is not None else None for k, v in values.items()},
        "overall_score": round(total, 2) if total is not None else None,
        "assessment_completion_ratio": count / 4,
        "status": "assessed" if count == 4 else "partial" if count else "not_assessed",
        "note": "Arithmetic only; evidence, dataset scope and sampling validity need separate review. This score never authorizes data delivery.",
    }
