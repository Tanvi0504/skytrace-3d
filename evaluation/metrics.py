"""Metrics and aggregation helpers for Step 8 evaluation."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Any, Iterable


def measurement_error_metrics(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Compute metric-accuracy statistics from matched ground-truth records."""
    comparisons = []
    for record in records:
        truth = _finite_nonnegative(record.get("ground_truth_distance_metres"))
        predicted = _finite_nonnegative(record.get("predicted_distance_metres"))
        if truth is None or predicted is None:
            continue
        absolute = abs(predicted - truth)
        comparisons.append(
            {
                "measurement_id": record.get("measurement_id"),
                "ground_truth_distance_metres": truth,
                "predicted_distance_metres": predicted,
                "absolute_error_metres": absolute,
                "relative_error_percent": 100.0 * absolute / truth if truth > 0 else None,
                "evidence_level": record.get("evidence_level"),
            }
        )
    if not comparisons:
        return {"status": "NOT_TESTED", "reason": "No matched ground-truth measurements were available."}
    errors = [item["absolute_error_metres"] for item in comparisons]
    percentage = [item["relative_error_percent"] for item in comparisons if item["relative_error_percent"] is not None]
    return {
        "status": "TESTED",
        "measurement_count": len(comparisons),
        "mae_metres": sum(errors) / len(errors),
        "median_absolute_error_metres": median(errors),
        "rmse_metres": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "maximum_absolute_error_metres": max(errors),
        "mean_relative_error_percent": sum(percentage) / len(percentage) if percentage else None,
        "comparisons": comparisons,
    }


def evidence_score_validation(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Group actual measurement error by Step 6 evidence level."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for record in records:
        level = str(record.get("evidence_level") or "").upper()
        error = _finite_nonnegative(record.get("absolute_error_metres"))
        if level in {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT"} and error is not None:
            grouped[level].append(error)
    if not grouped:
        return {"status": "NOT_TESTED", "reason": "Evidence validation needs both evidence levels and ground truth errors."}
    by_level = {
        level: {
            "count": len(values),
            "mean_absolute_error_metres": sum(values) / len(values),
            "median_absolute_error_metres": median(values),
        }
        for level, values in sorted(grouped.items())
    }
    means = [by_level[level]["mean_absolute_error_metres"] for level in ("HIGH", "MEDIUM", "LOW") if level in by_level]
    needs_recalibration = any(left > right for left, right in zip(means, means[1:]))
    return {
        "status": "TESTED",
        "by_evidence_level": by_level,
        "conclusion": "Evidence score requires recalibration." if needs_recalibration else "Higher evidence generally had lower measured error in this dataset.",
    }


def aggregate_numeric(values: Iterable[float | int | None]) -> dict[str, float | int] | None:
    usable = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not usable:
        return None
    return {
        "count": len(usable),
        "mean": sum(usable) / len(usable),
        "min": min(usable),
        "max": max(usable),
        "median": median(usable),
    }


def compare_against_baseline(baseline: dict[str, Any], degraded: dict[str, Any]) -> dict[str, Any]:
    """Return raw baseline/degraded values and percent change where meaningful."""
    comparison = {}
    for key, baseline_value in baseline.items():
        degraded_value = degraded.get(key)
        if isinstance(baseline_value, (int, float)) and isinstance(degraded_value, (int, float)):
            comparison[key] = {
                "baseline": baseline_value,
                "degraded": degraded_value,
                "absolute_change": degraded_value - baseline_value,
                "percent_change": (100.0 * (degraded_value - baseline_value) / baseline_value if baseline_value else None),
            }
    return comparison


def _finite_nonnegative(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0 or not math.isfinite(numeric):
        return None
    return numeric
