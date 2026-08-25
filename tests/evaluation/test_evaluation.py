from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.evaluation import evaluate_measurements


def test_evaluation_reports_known_absolute_and_percentage_errors(tmp_path: Path) -> None:
    predictions = tmp_path / "measurements.json"
    predictions.write_text(
        json.dumps(
            {
                "measurements": [
                    {"measurement_id": "one", "distance_3d_metres": 20.7},
                    {"measurement_id": "two", "distance_3d": 500.0, "unit": "cm"},
                ]
            }
        )
    )
    ground_truth = tmp_path / "ground_truth.json"
    ground_truth.write_text(
        json.dumps(
            {
                "measurements": [
                    {"measurement_id": "one", "distance_m": 20.0},
                    {"measurement_id": "two", "point_a": [0, 0, 0], "point_b": [3, 4, 0]},
                ]
            }
        )
    )

    result = evaluate_measurements(predictions, ground_truth, tmp_path / "evaluation")

    assert result.success
    assert result.measurement_count == 2
    assert result.mean_absolute_error_metres == pytest.approx(0.35)
    assert result.median_absolute_error_metres == pytest.approx(0.35)
    assert result.rmse_metres == pytest.approx((0.7**2 / 2) ** 0.5)
    assert result.mean_percentage_error == pytest.approx(1.75)
    report = json.loads((tmp_path / "evaluation" / "evaluation.json").read_text())
    assert report["comparisons"][0]["absolute_error_metres"] == pytest.approx(0.7)


def test_evaluation_handles_malformed_prediction_safely(tmp_path: Path) -> None:
    predictions = tmp_path / "measurements.json"
    predictions.write_text(json.dumps({"measurements": [{"measurement_id": "one"}]}))
    ground_truth = tmp_path / "ground_truth.json"
    ground_truth.write_text(json.dumps({"one": {"distance_m": 5.0}}))

    result = evaluate_measurements(predictions, ground_truth, tmp_path / "evaluation")

    assert not result.success
    assert "prediction needs" in (result.error or "")
