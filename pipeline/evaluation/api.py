"""Ground-truth error evaluation for Step 6 measurement artifacts."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.analysis.measurements import measure_distance, normalize_unit
from pipeline.evaluation.errors import EvaluationError
from pipeline.evaluation.models import EvaluationResult


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluationError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"{label} is invalid JSON: {exc}") from exc


def _records(document: Any, label: str) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(document, dict) and isinstance(document.get("measurements"), list):
        source = document["measurements"]
        pairs = [(None, item) for item in source]
    elif isinstance(document, list):
        pairs = [(None, item) for item in document]
    elif isinstance(document, dict):
        pairs = list(document.items())
    else:
        raise EvaluationError(f"{label} must be a measurement array or object mapping IDs to records")
    output: list[tuple[str, dict[str, Any]]] = []
    for index, (mapping_id, record) in enumerate(pairs, start=1):
        if not isinstance(record, dict):
            raise EvaluationError(f"{label} record {index} is not an object")
        identifier = str(record.get("measurement_id", mapping_id or "")).strip()
        if not identifier:
            raise EvaluationError(f"{label} record {index} has no measurement_id")
        output.append((identifier, record))
    return output


def _ground_truth_distance(record: dict[str, Any]) -> float:
    for name in ("distance_m", "distance_metres", "distance_meters"):
        if name in record:
            value = float(record[name])
            if value < 0 or not np.isfinite(value):
                raise ValueError("ground-truth distance must be finite and non-negative")
            return value
    if "point_a" in record and "point_b" in record:
        return measure_distance(record["point_a"], record["point_b"]).distance_3d_metres
    raise ValueError("ground truth needs distance_m or point_a and point_b")


def _prediction_distance(record: dict[str, Any]) -> float:
    if "distance_3d_metres" in record:
        value = float(record["distance_3d_metres"])
    elif "distance_3d" in record:
        unit = normalize_unit(record.get("unit", "m"))
        factors = {"m": 1.0, "cm": 0.01, "km": 1000.0}
        value = float(record["distance_3d"]) * factors[unit]
    else:
        raise ValueError("prediction needs distance_3d_metres or distance_3d with unit")
    if value < 0 or not np.isfinite(value):
        raise ValueError("predicted distance must be finite and non-negative")
    return value


def _prepare_output_directory(output_dir: Path, predictions_path: Path, ground_truth_path: Path, overwrite: bool) -> None:
    resolved_output = output_dir.resolve()
    for source in (predictions_path.resolve(), ground_truth_path.resolve()):
        if resolved_output == source or resolved_output in source.parents:
            raise EvaluationError("Evaluation output must not overwrite an input file or its parent")
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise EvaluationError(
                f"Evaluation output directory is not empty: {output_dir}. Use overwrite=True to replace it."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def evaluate_measurements(
    predictions_path: str | Path,
    ground_truth_path: str | Path,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> EvaluationResult:
    """Compare predicted metric distances with known distances, without using evidence as error."""
    started_at = time.monotonic()
    predictions = Path(predictions_path)
    ground_truth = Path(ground_truth_path)
    output = Path(output_dir)
    prepared = False
    result: EvaluationResult | None = None
    comparisons: list[dict[str, Any]] = []
    try:
        prediction_map = dict(_records(_read_json(predictions, "Predictions"), "Predictions"))
        truth_records = _records(_read_json(ground_truth, "Ground truth"), "Ground truth")
        _prepare_output_directory(output, predictions, ground_truth, overwrite)
        prepared = True
        warnings: list[str] = []
        for identifier, truth in truth_records:
            if identifier not in prediction_map:
                warnings.append(f"No prediction matched ground-truth measurement_id {identifier!r}.")
                continue
            expected = _ground_truth_distance(truth)
            predicted = _prediction_distance(prediction_map[identifier])
            absolute_error = abs(predicted - expected)
            comparisons.append(
                {
                    "measurement_id": identifier,
                    "ground_truth_distance_metres": expected,
                    "predicted_distance_metres": predicted,
                    "absolute_error_metres": absolute_error,
                    "percentage_error": (100.0 * absolute_error / expected if expected > 0 else None),
                }
            )
        if not comparisons:
            raise EvaluationError("No ground-truth records could be matched to valid predictions")
        errors = np.asarray([item["absolute_error_metres"] for item in comparisons], dtype=float)
        percentage_errors = [
            item["percentage_error"] for item in comparisons if item["percentage_error"] is not None
        ]
        result = EvaluationResult(
            success=True,
            predictions_path=predictions,
            ground_truth_path=ground_truth,
            output_dir=output,
            measurement_count=len(comparisons),
            mean_absolute_error_metres=float(np.mean(errors)),
            median_absolute_error_metres=float(np.median(errors)),
            rmse_metres=float(np.sqrt(np.mean(errors**2))),
            mean_percentage_error=(
                float(np.mean(percentage_errors)) if percentage_errors else None
            ),
            worst_case_absolute_error_metres=float(np.max(errors)),
            report_path=output / "evaluation.json",
            warnings=warnings,
        )
    except (EvaluationError, OSError, TypeError, ValueError) as exc:
        result = EvaluationResult(
            success=False,
            predictions_path=predictions,
            ground_truth_path=ground_truth,
            output_dir=output,
            error=str(exc),
        )
    result.processing_time_seconds = time.monotonic() - started_at
    if prepared:
        result.report_path = output / "evaluation.json"
        payload = result.to_dict()
        if result.success:
            payload.update(
                {
                    "schema_version": 1,
                    "description": (
                        "Measured distance error against provided ground truth. These metrics are "
                        "separate from Step 6 reconstruction evidence and Step 3 GPS alignment residuals."
                    ),
                    "comparisons": comparisons,
                }
            )
        result.report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return result
