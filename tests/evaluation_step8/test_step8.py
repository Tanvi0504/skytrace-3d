from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from evaluation.failure import classify_failure
from evaluation.gps import perturb_gps_metadata
from evaluation.metrics import evidence_score_validation, measurement_error_metrics
from evaluation.metrics import completeness_metrics, object_detection_metrics, object_localization_metrics
from evaluation.perturbations import add_sensor_noise, add_synthetic_shadow, adjust_illumination, apply_motion_blur
from evaluation.reports import PS_CHALLENGES, build_report, write_reports
from evaluation.run_suite import DEFAULT_SCENARIO_MANIFESTS, run_suite


def test_degradation_generation_changes_expected_pixels() -> None:
    frame = np.zeros((9, 9, 3), dtype=np.uint8)
    frame[:, 4] = 255

    blurred = apply_motion_blur(frame, 2)
    dark = adjust_illumination(frame, exposure_scale=0.5)
    noisy = add_sensor_noise(frame, sigma=5.0, seed=1)
    shadowed = add_synthetic_shadow(np.full((20, 20, 3), 200, dtype=np.uint8), level=2)

    assert blurred.shape == frame.shape
    assert blurred[4, 4, 0] < frame[4, 4, 0]
    assert dark.max() < frame.max()
    assert not np.array_equal(noisy, frame)
    assert shadowed.min() < 200


def test_invalid_degradation_inputs_are_rejected() -> None:
    frame = np.zeros((3, 3, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        apply_motion_blur(frame, 9)
    with pytest.raises(ValueError):
        adjust_illumination(frame, exposure_scale=0)
    with pytest.raises(ValueError):
        add_sensor_noise(frame, sigma=-1)
    with pytest.raises(ValueError):
        add_synthetic_shadow(frame, level=9)


def test_gps_perturbation_records_controlled_noise(tmp_path: Path) -> None:
    source = tmp_path / "gps.json"
    source.write_text(
        json.dumps({"observations": [{"latitude": 12.0, "longitude": 77.0, "altitude": 10.0}]}),
        encoding="utf-8",
    )

    payload = perturb_gps_metadata(source, tmp_path / "gps_noisy.json", horizontal_noise_metres=5.0, seed=42)

    observation = payload["observations"][0]
    assert observation["latitude"] != 12.0 or observation["longitude"] != 77.0
    assert observation["controlled_perturbation"]["horizontal_noise_metres"] == 5.0
    assert payload["controlled_experiment"]["type"] == "gps_noise"


def test_metric_calculations_do_not_fabricate_missing_ground_truth() -> None:
    assert measurement_error_metrics([])["status"] == "NOT_TESTED"
    metrics = measurement_error_metrics(
        [
            {"measurement_id": "a", "ground_truth_distance_metres": 10, "predicted_distance_metres": 12, "evidence_level": "HIGH"},
            {"measurement_id": "b", "ground_truth_distance_metres": 20, "predicted_distance_metres": 17, "evidence_level": "LOW"},
        ]
    )
    assert metrics["mae_metres"] == pytest.approx(2.5)
    assert metrics["maximum_absolute_error_metres"] == pytest.approx(3.0)


def test_evidence_validation_flags_bad_ordering() -> None:
    result = evidence_score_validation(
        [
            {"evidence_level": "HIGH", "absolute_error_metres": 5.0},
            {"evidence_level": "LOW", "absolute_error_metres": 1.0},
        ]
    )

    assert result["status"] == "TESTED"
    assert result["conclusion"] == "Evidence score requires recalibration."


def test_failure_classification_uses_standard_taxonomy() -> None:
    failure = classify_failure(
        {
            "steps": [
                {"step": 1, "status": "COMPLETED"},
                {"step": 3, "status": "FAILED", "error": "not enough GPS matches"},
            ]
        }
    )

    assert failure is not None
    assert failure["failure_type"] == "GEOREFERENCE_FAILURE"
    assert failure["stage"] == "STEP_3"


def test_report_generation_includes_all_ps_challenges(tmp_path: Path) -> None:
    report = build_report(
        dataset_dir=tmp_path / "dataset",
        scenarios=[{"scenario": "baseline", "label": "BASELINE", "status": "TESTED", "metrics": {}, "notes": []}],
        baseline={"status": "TESTED", "metrics": {}},
        metric_accuracy={"status": "NOT_TESTED"},
        evidence_validation={"status": "NOT_TESTED"},
    )
    paths = write_reports(report, tmp_path / "out")

    assert len(report["ps_requirement_scorecard"]) == len(PS_CHALLENGES)
    assert Path(paths["json"]).is_file()
    assert "Limited viewing angles" in Path(paths["markdown"]).read_text(encoding="utf-8")
    assert "Metric accuracy" in Path(paths["markdown"]).read_text(encoding="utf-8")
    assert "Failure Analysis" in Path(paths["markdown"]).read_text(encoding="utf-8")


def test_run_suite_creates_reproducible_not_tested_report(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    (dataset / "baseline").mkdir(parents=True)
    (dataset / "baseline" / "manifest.json").write_text(json.dumps({"single_pass": True}), encoding="utf-8")

    report = run_suite(dataset, tmp_path / "results", ["baseline", "motion_blur", "metric_accuracy"], tmp_path / "missing-run")

    assert report["baseline"]["status"] == "NOT_TESTED"
    assert any(row["ps_requirement"] == "Metric accuracy" and row["status"] == "NOT_TESTED" for row in report["ps_requirement_scorecard"])
    assert report["scenarios"][0]["single_pass"] is True
    assert set(report["dataset_structure"]["scenario_directories"]) == set(DEFAULT_SCENARIO_MANIFESTS)
    assert (dataset / "gps_noise" / "manifest.json").is_file()


def test_run_suite_collects_processed_demo_baseline() -> None:
    report = run_suite(
        Path("data/evaluation"),
        Path("evaluation/test-results"),
        ["baseline", "processing_time"],
        Path("outputs/processed-demo"),
    )

    assert report["baseline"]["status"] == "TESTED"
    assert report["baseline"]["metrics"]["point_count"] == 9
    assert report["scenarios"][1]["metrics"]["real_time_claim_supported"] is False


def test_object_detection_metrics_use_labels_without_fabrication() -> None:
    predictions = {"objects": [{"object_id": "p1", "class": "person"}, {"object_id": "c1", "class": "car"}]}
    labels = {"objects": [{"object_id": "p1", "class": "person"}, {"object_id": "t1", "class": "truck"}]}

    result = object_detection_metrics(predictions, labels)

    assert result["status"] == "TESTED"
    assert result["overall"]["precision"] == pytest.approx(0.5)
    assert result["overall"]["recall"] == pytest.approx(0.5)
    assert object_detection_metrics({"objects": []}, labels)["status"] == "NOT_TESTED"


def test_object_localization_metrics_require_matched_3d_positions() -> None:
    predictions = {"objects": [{"object_id": "car-1", "class": "car", "position": [1, 2, 2], "evidence_level": "HIGH"}]}
    labels = {"objects": [{"object_id": "car-1", "class": "car", "position": [1, 2, 0]}]}

    result = object_localization_metrics(predictions, labels)

    assert result["status"] == "TESTED"
    assert result["maximum_error_metres"] == pytest.approx(2.0)
    assert object_localization_metrics({"objects": []}, labels)["status"] == "NOT_TESTED"


def test_completeness_metrics_distinguish_surface_coverage() -> None:
    result = completeness_metrics(
        {
            "surfaces": [
                {"surface_id": "front", "class": "building", "reference_area_square_metres": 100, "observed_area_square_metres": 80},
                {"surface_id": "rear", "class": "building", "reference_area_square_metres": 100, "observed_area_square_metres": 0},
            ]
        }
    )

    assert result["status"] == "TESTED"
    assert result["mean_observed_surface_percent"] == pytest.approx(40.0)
