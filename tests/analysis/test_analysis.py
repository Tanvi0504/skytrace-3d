from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from pipeline.analysis import (
    EvidenceConfig,
    MeasurementRequest,
    analyze_georeferenced_scene,
    calculate_evidence,
    convert_distance,
    measure_distance,
    measure_scene_distance,
)
from pipeline.analysis.errors import MeasurementInputError
from pipeline.analysis.evidence import evidence_level
from pipeline.analysis.inputs import load_scene_context


def _write_ascii_ply(path: Path, points: np.ndarray) -> None:
    rows = "\n".join(" ".join(str(value) for value in point) for point in points)
    path.write_text(
        "\n".join(
            [
                "ply",
                "format ascii 1.0",
                f"element vertex {len(points)}",
                "property float x",
                "property float y",
                "property float z",
                "end_header",
                rows,
            ]
        )
        + "\n"
    )


def _write_scene(
    tmp_path: Path,
    *,
    points: np.ndarray | None = None,
    cameras: np.ndarray | None = None,
    with_transform: bool = True,
    dynamic_marker: np.ndarray | None = None,
) -> tuple[Path, Path | None]:
    scene = tmp_path / "georeferenced"
    scene.mkdir()
    source_points = (
        points
        if points is not None
        else np.repeat(np.array([[0.0, 0.0, 0.0]]), 24, axis=0)
    )
    _write_ascii_ply(scene / "point_cloud_georef.ply", source_points)
    if with_transform:
        (scene / "transform.json").write_text(
            json.dumps(
                {
                    "target_coordinate_system": "Local East-North-Up (ENU), metres",
                    "transform": {"matrix_4x4": np.eye(4).tolist()},
                }
            )
        )
    source_cameras = (
        cameras
        if cameras is not None
        else np.array(
            [[-10.0, 0.0, 2.0], [10.0, 0.0, 2.0], [0.0, -10.0, 2.0], [0.0, 10.0, 2.0]]
        )
    )
    with (scene / "camera_trajectory_georef.csv").open("w", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=["image_id", "enu_east_m", "enu_north_m", "enu_up_m"],
        )
        writer.writeheader()
        for index, camera in enumerate(source_cameras, start=1):
            writer.writerow(
                {
                    "image_id": index,
                    "enu_east_m": camera[0],
                    "enu_north_m": camera[1],
                    "enu_up_m": camera[2],
                }
            )
    objects: Path | None = None
    if dynamic_marker is not None:
        objects = tmp_path / "scene_objects"
        objects.mkdir()
        (objects / "objects_3d.json").write_text(
            json.dumps(
                {
                    "objects": [
                        {
                            "is_dynamic_candidate": True,
                            "coordinate_system": "Local East-North-Up (ENU), metres",
                            "world_position": dynamic_marker.tolist(),
                        }
                    ]
                }
            )
        )
    return scene, objects


def test_distance_horizontal_and_vertical_are_distinct() -> None:
    measurement = measure_distance([0, 0, 10], [3, 4, 25])

    assert measurement.distance_3d_metres == pytest.approx(np.sqrt(250))
    assert measurement.horizontal_distance_metres == pytest.approx(5.0)
    assert measurement.vertical_difference_metres == pytest.approx(15.0)


def test_unit_conversion_keeps_internal_metres_precise() -> None:
    measurement = measure_distance([0, 0, 0], [3, 4, 0], unit="cm")

    assert measurement.distance_3d_metres == pytest.approx(5.0)
    assert measurement.to_dict()["distance_3d"] == pytest.approx(500.0)
    assert convert_distance(1.25, "km") == pytest.approx(0.00125)


def test_invalid_coordinates_and_units_are_rejected() -> None:
    with pytest.raises(MeasurementInputError, match="three finite"):
        measure_distance([0, 0], [1, 1, 1])
    with pytest.raises(MeasurementInputError, match="unit must be"):
        measure_distance([0, 0, 0], [1, 1, 1], unit="feet")


def test_evidence_normalization_reaches_high_for_dense_diverse_support(tmp_path: Path) -> None:
    scene_dir, _ = _write_scene(tmp_path)
    config = EvidenceConfig()
    scene = load_scene_context(scene_dir, None, config)

    evidence = calculate_evidence(np.array([0.0, 0.0, 0.0]), scene, config)

    assert evidence.evidence_score == pytest.approx(1.0)
    assert evidence.evidence_level == "HIGH"
    assert evidence.direct_observation_status == "UNKNOWN"
    assert evidence.signals["nearby_camera_support"]["visibility_verified"] is False


def test_evidence_level_thresholds_are_configurable() -> None:
    config = EvidenceConfig(high_threshold=0.8, medium_threshold=0.6, low_threshold=0.3)

    assert evidence_level(0.81, config) == "HIGH"
    assert evidence_level(0.60, config) == "MEDIUM"
    assert evidence_level(0.30, config) == "LOW"
    assert evidence_level(0.29, config) == "INSUFFICIENT"


def test_sparse_region_is_insufficient_and_measurement_is_not_recommended(tmp_path: Path) -> None:
    scene_dir, _ = _write_scene(tmp_path)
    scene = load_scene_context(scene_dir, None, EvidenceConfig())

    result = measure_scene_distance(scene, [0, 0, 0], [200, 0, 0])

    assert result.measurement.distance_3d_metres == pytest.approx(200.0)
    assert result.measurement_status == "MEASUREMENT_NOT_RELIABLE"
    assert result.evidence_level == "INSUFFICIENT"
    assert any("Point B lies" in warning for warning in result.warnings)


def test_dynamic_marker_proximity_reduces_but_does_not_erase_evidence(tmp_path: Path) -> None:
    scene_dir, object_dir = _write_scene(tmp_path, dynamic_marker=np.array([0.0, 0.0, 0.0]))
    config = EvidenceConfig()
    baseline = calculate_evidence(
        np.array([0.0, 0.0, 0.0]), load_scene_context(scene_dir, None, config), config
    )
    contaminated = calculate_evidence(
        np.array([0.0, 0.0, 0.0]), load_scene_context(scene_dir, object_dir, config), config
    )

    assert contaminated.evidence_score < baseline.evidence_score
    assert contaminated.signals["dynamic_contamination"]["nearby_dynamic_marker_count"] == 1
    assert contaminated.evidence_score == pytest.approx(0.75)


def test_analysis_writes_measurements_and_compact_quality_grid(tmp_path: Path) -> None:
    points = np.vstack(
        [
            np.repeat(np.array([[0.0, 0.0, 0.0]]), 24, axis=0),
            np.repeat(np.array([[3.0, 4.0, 0.0]]), 24, axis=0),
            np.repeat(np.array([[1.0, 4.0 / 3.0, 0.0]]), 24, axis=0),
            np.repeat(np.array([[2.0, 8.0 / 3.0, 0.0]]), 24, axis=0),
        ]
    )
    scene_dir, _ = _write_scene(tmp_path, points=points)
    output = tmp_path / "analysis"
    result = analyze_georeferenced_scene(
        scene_dir,
        output,
        measurements=[
            MeasurementRequest(
                "known_five_metres", np.array([0.0, 0.0, 0.0]), np.array([3.0, 4.0, 0.0])
            )
        ],
    )

    assert result.success
    assert result.point_count == len(points)
    assert result.measurement_count == 1
    assert result.recommended_measurement_count == 1
    measurements = json.loads((output / "measurements.json").read_text())["measurements"]
    assert measurements[0]["measurement_status"] == "MEASUREMENT_AVAILABLE"
    assert measurements[0]["distance_3d"] == pytest.approx(5.0)
    assert measurements[0]["horizontal_distance"] == pytest.approx(5.0)
    assert measurements[0]["vertical_difference"] == pytest.approx(0.0)
    quality_map = json.loads((output / "evidence_map" / "quality_grid.json").read_text())
    assert quality_map["source_point_cloud"].endswith("point_cloud_georef.ply")
    assert len(quality_map["regions"]) < len(points)
    metadata = json.loads((output / "quality_metadata.json").read_text())
    assert "per-point source-frame visibility" in metadata["evidence_methodology"]["signals_not_available"]
    assert metadata["vertical_measurement"]["source"] == "Step 3 Local ENU Up coordinate"


def test_missing_point_cloud_returns_structured_failure(tmp_path: Path) -> None:
    scene = tmp_path / "georeferenced"
    scene.mkdir()
    (scene / "transform.json").write_text(
        json.dumps(
            {
                "target_coordinate_system": "Local East-North-Up (ENU), metres",
                "transform": {"matrix_4x4": np.eye(4).tolist()},
            }
        )
    )

    result = analyze_georeferenced_scene(scene, tmp_path / "analysis")

    assert not result.success
    assert "point cloud" in (result.error or "").lower()


def test_missing_georeferencing_transform_returns_structured_failure(tmp_path: Path) -> None:
    scene_dir, _ = _write_scene(tmp_path, with_transform=False)

    result = analyze_georeferenced_scene(scene_dir, tmp_path / "analysis")

    assert not result.success
    assert "transform.json" in (result.error or "")


def test_missing_camera_evidence_is_reported_without_fabrication(tmp_path: Path) -> None:
    scene_dir, _ = _write_scene(tmp_path)
    (scene_dir / "camera_trajectory_georef.csv").unlink()

    result = analyze_georeferenced_scene(scene_dir, tmp_path / "analysis")

    assert result.success
    assert result.camera_count == 0
    assert any("nearby-camera evidence is zero" in warning for warning in result.warnings)
