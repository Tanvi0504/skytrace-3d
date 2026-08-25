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


def object_detection_metrics(predictions: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, Any]:
    """Compute class-level precision/recall/F1 from supplied labels.

    Matching is intentionally ID based for Step 8. If a dataset does not provide
    matched IDs, the report should stay NOT_TESTED rather than inventing IoU or
    manual labels.
    """
    predicted = _object_records(predictions)
    truth = _object_records(ground_truth)
    if not predicted or not truth:
        return {"status": "NOT_TESTED", "reason": "Object detection requires non-empty predicted and ground-truth object records."}

    classes = sorted({item["class"] for item in predicted + truth if item.get("class")})
    by_class: dict[str, dict[str, Any]] = {}
    total_tp = total_fp = total_fn = 0
    truth_by_id = {item["id"]: item for item in truth if item.get("id")}
    for class_name in classes:
        predicted_class = [item for item in predicted if item.get("class") == class_name]
        truth_class_ids = {item["id"] for item in truth if item.get("class") == class_name and item.get("id")}
        true_positive = sum(1 for item in predicted_class if item.get("id") in truth_class_ids)
        false_positive = sum(1 for item in predicted_class if item.get("id") not in truth_by_id or item.get("id") not in truth_class_ids)
        false_negative = max(0, len(truth_class_ids) - true_positive)
        total_tp += true_positive
        total_fp += false_positive
        total_fn += false_negative
        by_class[class_name] = _classification_scores(true_positive, false_positive, false_negative)
    overall = _classification_scores(total_tp, total_fp, total_fn)
    return {"status": "TESTED", "by_class": by_class, "overall": overall}


def object_localization_metrics(predictions: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, Any]:
    """Measure 3D object position error where matched object IDs exist."""
    predicted = {item["id"]: item for item in _object_records(predictions) if item.get("id")}
    truth = {item["id"]: item for item in _object_records(ground_truth) if item.get("id")}
    comparisons = []
    for object_id, truth_item in truth.items():
        predicted_item = predicted.get(object_id)
        if not predicted_item:
            continue
        truth_point = _point3d(truth_item)
        predicted_point = _point3d(predicted_item)
        if truth_point is None or predicted_point is None:
            continue
        error = math.sqrt(sum((predicted_point[index] - truth_point[index]) ** 2 for index in range(3)))
        comparisons.append(
            {
                "object_id": object_id,
                "class": truth_item.get("class") or predicted_item.get("class"),
                "ground_truth_position": truth_point,
                "predicted_position": predicted_point,
                "position_error_metres": error,
                "observation_count": predicted_item.get("observation_count") or predicted_item.get("observations"),
                "viewpoint_diversity": predicted_item.get("viewpoint_diversity"),
                "evidence_level": predicted_item.get("evidence_level"),
            }
        )
    if not comparisons:
        return {"status": "NOT_TESTED", "reason": "No matched 3D object positions were available."}
    errors = [item["position_error_metres"] for item in comparisons]
    return {
        "status": "TESTED",
        "object_count": len(comparisons),
        "mae_metres": sum(errors) / len(errors),
        "median_error_metres": median(errors),
        "rmse_metres": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "maximum_error_metres": max(errors),
        "comparisons": comparisons,
    }


def completeness_metrics(document: dict[str, Any]) -> dict[str, Any]:
    """Estimate observed/missing surface coverage from provided reference areas."""
    records = document.get("surfaces", document if isinstance(document, list) else [])
    if not isinstance(records, list):
        return {"status": "NOT_TESTED", "reason": "surface_completeness.json must be an array or contain a surfaces array."}
    comparisons = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        reference_area = _finite_nonnegative(record.get("reference_area_square_metres"))
        observed_area = _finite_nonnegative(record.get("observed_area_square_metres"))
        if reference_area is None or reference_area <= 0 or observed_area is None:
            continue
        coverage = min(observed_area, reference_area) / reference_area
        comparisons.append(
            {
                "surface_id": record.get("surface_id", f"surface_{index}"),
                "class": record.get("class"),
                "reference_area_square_metres": reference_area,
                "observed_area_square_metres": observed_area,
                "observed_surface_percent": coverage * 100.0,
                "missing_surface_percent": (1.0 - coverage) * 100.0,
            }
        )
    if not comparisons:
        return {"status": "NOT_TESTED", "reason": "No valid reference/observed surface area pairs were supplied."}
    observed = [item["observed_surface_percent"] for item in comparisons]
    missing = [item["missing_surface_percent"] for item in comparisons]
    return {
        "status": "TESTED",
        "surface_count": len(comparisons),
        "mean_observed_surface_percent": sum(observed) / len(observed),
        "mean_missing_surface_percent": sum(missing) / len(missing),
        "comparisons": comparisons,
    }


def _finite_nonnegative(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0 or not math.isfinite(numeric):
        return None
    return numeric


def _classification_scores(true_positive: int, false_positive: int, false_negative: int) -> dict[str, Any]:
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else None
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else None
    f1 = 2.0 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _object_records(document: dict[str, Any]) -> list[dict[str, Any]]:
    raw = document.get("objects", document.get("labels", document if isinstance(document, list) else []))
    if not isinstance(raw, list):
        return []
    records = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        identifier = item.get("object_id") or item.get("track_id") or item.get("id") or item.get("label_id")
        class_name = item.get("class") or item.get("label") or item.get("category")
        clone = dict(item)
        clone["id"] = str(identifier or index)
        clone["class"] = str(class_name).lower() if class_name else None
        records.append(clone)
    return records


def _point3d(record: dict[str, Any]) -> list[float] | None:
    raw = record.get("position") or record.get("position_3d") or record.get("centroid") or record.get("world_position")
    if isinstance(raw, dict):
        raw = [raw.get("x"), raw.get("y"), raw.get("z")]
    if not isinstance(raw, (list, tuple)) or len(raw) < 3:
        return None
    point = []
    for value in raw[:3]:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric):
            return None
        point.append(numeric)
    return point
