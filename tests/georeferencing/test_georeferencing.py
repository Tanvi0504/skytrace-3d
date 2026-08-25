from __future__ import annotations

import csv
import json
import struct
from pathlib import Path

import numpy as np
import pytest

from pipeline.georeferencing import georeference_reconstruction
from pipeline.georeferencing.alignment import (
    estimate_robust_similarity_transform,
    estimate_similarity_transform,
)
from pipeline.georeferencing.coordinates import (
    choose_enu_reference,
    enu_to_geodetic,
    geodetic_to_enu,
)
from pipeline.georeferencing.correspondence import match_camera_poses_to_gps
from pipeline.georeferencing.errors import GPSMetadataError
from pipeline.georeferencing.gps import load_gps_metadata
from pipeline.georeferencing.models import CameraPose, GPSObservation, LocalENUReference
from pipeline.georeferencing.models import SimilarityTransform
from pipeline.georeferencing.ply import transform_ply


def _rotation_z(degrees: float) -> np.ndarray:
    radians = np.deg2rad(degrees)
    return np.array(
        [
            [np.cos(radians), -np.sin(radians), 0.0],
            [np.sin(radians), np.cos(radians), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )


def _source_trajectory() -> np.ndarray:
    return np.array(
        [
            [0.0, 0.0, 0.0],
            [2.0, 0.5, 0.2],
            [0.2, 3.0, 0.7],
            [2.4, 3.2, 1.1],
            [1.0, 1.2, 2.0],
            [3.5, 1.1, 1.6],
        ]
    )


def _known_transform() -> tuple[float, np.ndarray, np.ndarray]:
    return 2.5, _rotation_z(32.0), np.array([12.0, -8.0, 4.0])


def _write_ascii_ply(path: Path, points: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "ply",
        "format ascii 1.0",
        f"element vertex {len(points)}",
        "property float x",
        "property float y",
        "property float z",
        "property uchar red",
        "end_header",
    ]
    lines.extend(f"{x} {y} {z} 200" for x, y, z in points)
    path.write_text("\n".join(lines) + "\n")


def _write_reconstruction(
    root: Path,
    source_points: np.ndarray,
    *,
    metric_scale: bool = False,
    timestamps: bool = False,
) -> Path:
    reconstruction_dir = root / "reconstruction"
    poses = []
    manifest_frames = []
    for index, point in enumerate(source_points):
        name = f"frame_{index * 6:06d}.jpg"
        pose = {
            "image_id": index + 1,
            "image_name": name,
            "camera_center_world": point.tolist(),
        }
        if timestamps:
            manifest_frames.append(
                {
                    "filename": name,
                    "selected": True,
                    "timestamp_seconds": float(index),
                }
            )
        poses.append(pose)
    reconstruction_dir.mkdir(parents=True)
    (reconstruction_dir / "camera_poses.json").write_text(
        json.dumps(
            {
                "scale": "metric metres" if metric_scale else "arbitrary; not metric or georeferenced",
                "poses": poses,
            }
        )
    )
    _write_ascii_ply(reconstruction_dir / "sparse" / "sparse.ply", source_points)
    if timestamps:
        (root / "frame_manifest.json").write_text(json.dumps({"frames": manifest_frames}))
    return reconstruction_dir


def _write_gps_json(
    path: Path,
    target_enu: np.ndarray,
    *,
    image_names: list[str] | None = None,
    timestamps: bool = False,
) -> None:
    reference = LocalENUReference(latitude=17.385, longitude=78.4867, altitude=500.0)
    observations = []
    for index, position in enumerate(target_enu):
        latitude, longitude, altitude = enu_to_geodetic(position, reference)
        record = {
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
        }
        if image_names is not None:
            record["image_name"] = image_names[index]
        if timestamps:
            record["timestamp_seconds"] = float(index)
        observations.append(record)
    path.write_text(
        json.dumps(
            {
                "coordinate_system": "WGS 84 geographic latitude/longitude",
                "altitude_reference": "ellipsoidal height",
                "observations": observations,
            }
        )
    )


def test_wgs84_local_enu_conversion_round_trip() -> None:
    reference = LocalENUReference(latitude=17.385, longitude=78.4867, altitude=500.0)
    expected_enu = np.array([25.0, -12.0, 4.0])
    latitude, longitude, altitude = enu_to_geodetic(expected_enu, reference)
    recovered_enu = geodetic_to_enu(latitude, longitude, altitude, reference)

    assert np.allclose(geodetic_to_enu(17.385, 78.4867, 500.0, reference), 0.0)
    assert np.allclose(recovered_enu, expected_enu, atol=1e-5)


def test_binary_little_endian_ply_coordinates_are_transformed(tmp_path: Path) -> None:
    input_path = tmp_path / "input.ply"
    output_path = tmp_path / "output.ply"
    header = (
        b"ply\n"
        b"format binary_little_endian 1.0\n"
        b"element vertex 1\n"
        b"property float x\n"
        b"property float y\n"
        b"property float z\n"
        b"property uchar red\n"
        b"end_header\n"
    )
    input_path.write_bytes(header + struct.pack("<fffB", 1.0, 2.0, 3.0, 255))
    transform = SimilarityTransform(
        scale=2.0,
        rotation=np.eye(3),
        translation=np.array([10.0, -1.0, 0.5]),
    )

    transform_ply(input_path, output_path, transform)

    output = output_path.read_bytes()
    values = struct.unpack("<fffB", output[len(header) :])
    assert values == pytest.approx((12.0, 3.0, 6.5, 255))


def test_known_similarity_alignment_recovers_rotation_scale_and_translation() -> None:
    source = _source_trajectory()
    scale, rotation, translation = _known_transform()
    target = scale * (source @ rotation.T) + translation

    estimate = estimate_similarity_transform(source, target)

    assert estimate.scale == pytest.approx(scale, rel=1e-10)
    assert np.allclose(estimate.rotation, rotation, atol=1e-10)
    assert np.allclose(estimate.translation, translation, atol=1e-10)
    assert np.allclose(estimate.apply(source), target, atol=1e-10)


def test_ransac_rejects_a_large_gps_outlier_and_recovers_scale() -> None:
    source = _source_trajectory()
    scale, rotation, translation = _known_transform()
    target = scale * (source @ rotation.T) + translation
    target += np.array(
        [
            [0.02, -0.01, 0.01],
            [-0.01, 0.01, -0.02],
            [0.0, 0.01, 0.02],
            [-0.02, 0.0, -0.01],
            [0.01, -0.02, 0.0],
            [0.0, 0.02, -0.01],
        ]
    )
    target[-1] += np.array([100.0, -80.0, 50.0])

    estimate = estimate_robust_similarity_transform(
        source,
        target,
        estimate_scale=True,
        threshold_metres=0.25,
        max_iterations=100,
    )

    assert estimate.inlier_count == len(source) - 1
    assert not estimate.inlier_mask[-1]
    assert estimate.transform.scale == pytest.approx(scale, abs=0.03)
    assert np.max(estimate.residuals_metres[:-1]) < 0.08


def test_gps_csv_aliases_are_supported(tmp_path: Path) -> None:
    gps_path = tmp_path / "gps.csv"
    with gps_path.open("w", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=["lat", "lon", "altitude_m", "frame_index"],
        )
        writer.writeheader()
        writer.writerow({"lat": 17.385, "lon": 78.4867, "altitude_m": 500, "frame_index": 6})

    dataset = load_gps_metadata(gps_path)

    assert len(dataset.observations) == 1
    assert dataset.observations[0].frame_index == 6


def test_invalid_gps_data_is_not_accepted(tmp_path: Path) -> None:
    gps_path = tmp_path / "bad.json"
    gps_path.write_text(json.dumps([{"latitude": 120, "longitude": 78.4, "altitude": 10}]))

    with pytest.raises(GPSMetadataError, match="No valid 3D GPS"):
        load_gps_metadata(gps_path)


def test_timestamp_matching_interpolates_only_within_tolerance() -> None:
    pose = CameraPose(
        image_id=1,
        image_name="frame_000000.jpg",
        camera_center=np.zeros(3),
        timestamp_seconds=0.5,
    )
    observations = [
        GPSObservation("row_1", 0, 0, 0, timestamp_seconds=0.0),
        GPSObservation("row_2", 0, 0, 0, timestamp_seconds=1.0),
    ]
    positions = {"row_1": np.array([0.0, 0.0, 0.0]), "row_2": np.array([10.0, 0.0, 0.0])}

    matches, warnings = match_camera_poses_to_gps(
        [pose], observations, positions, timestamp_tolerance_seconds=0.6
    )

    assert any("interpolated GPS positions" in warning for warning in warnings)
    assert matches[0].method == "timestamp_interpolated"
    assert np.allclose(matches[0].target_enu, [5.0, 0.0, 0.0])


def test_georeferencing_generates_outputs_and_metadata(tmp_path: Path) -> None:
    source = _source_trajectory()
    scale, rotation, translation = _known_transform()
    target = scale * (source @ rotation.T) + translation
    reconstruction_dir = _write_reconstruction(tmp_path, source)
    image_names = [f"frame_{index * 6:06d}.jpg" for index in range(len(source))]
    gps_path = tmp_path / "gps.json"
    _write_gps_json(gps_path, target, image_names=image_names)

    output_dir = tmp_path / "georeferenced"
    result = georeference_reconstruction(
        reconstruction_dir,
        gps_path,
        output_dir,
        ransac_threshold_metres=0.5,
    )

    assert result.success
    assert result.estimated_scale == pytest.approx(scale, abs=1e-4)
    assert result.matched_pose_count == len(source)
    assert result.inlier_count == len(source)
    assert (output_dir / "point_cloud_georef.ply").is_file()
    assert (output_dir / "camera_trajectory_georef.csv").is_file()
    transform = json.loads((output_dir / "transform.json").read_text())
    validation = json.loads((output_dir / "validation.json").read_text())
    metadata = json.loads((output_dir / "georef_metadata.json").read_text())
    assert transform["target_coordinate_system"] == "Local East-North-Up (ENU), metres"
    assert validation["metric_scope"].startswith("These are camera-trajectory")
    assert metadata["success"] is True


def test_declared_metric_source_keeps_unit_scale(tmp_path: Path) -> None:
    source = _source_trajectory()
    rotation = _rotation_z(-15.0)
    target = source @ rotation.T + np.array([4.0, 7.0, -2.0])
    reconstruction_dir = _write_reconstruction(tmp_path, source, metric_scale=True)
    gps_path = tmp_path / "gps.json"
    _write_gps_json(
        gps_path,
        target,
        image_names=[f"frame_{index * 6:06d}.jpg" for index in range(len(source))],
    )

    result = georeference_reconstruction(
        reconstruction_dir,
        gps_path,
        tmp_path / "georeferenced",
        ransac_threshold_metres=0.5,
    )

    assert result.success
    assert result.estimated_scale == 1.0
    assert any("fixed scale to 1.0" in warning for warning in result.warnings)
    transform = json.loads((tmp_path / "georeferenced" / "transform.json").read_text())
    assert transform["source_declared_metric"] is True
    assert transform["source_scale_treated_as_metric"] is True
    assert transform["scale_estimated"] is False


def test_structured_metric_scale_declaration_is_detected(tmp_path: Path) -> None:
    source = _source_trajectory()
    rotation = _rotation_z(-15.0)
    target = source @ rotation.T + np.array([4.0, 7.0, -2.0])
    reconstruction_dir = _write_reconstruction(tmp_path, source)
    poses_path = reconstruction_dir / "camera_poses.json"
    document = json.loads(poses_path.read_text())
    document["scale"] = {"is_metric": True, "units": "metres"}
    poses_path.write_text(json.dumps(document))
    gps_path = tmp_path / "gps.json"
    _write_gps_json(
        gps_path,
        target,
        image_names=[f"frame_{index * 6:06d}.jpg" for index in range(len(source))],
    )

    result = georeference_reconstruction(
        reconstruction_dir,
        gps_path,
        tmp_path / "georeferenced",
        ransac_threshold_metres=0.5,
    )

    assert result.success
    assert result.estimated_scale == 1.0


def test_missing_gps_file_returns_structured_failure(tmp_path: Path) -> None:
    reconstruction_dir = _write_reconstruction(tmp_path, _source_trajectory())

    result = georeference_reconstruction(
        reconstruction_dir,
        tmp_path / "missing-gps.json",
        tmp_path / "georeferenced",
    )

    assert not result.success
    assert "GPS metadata file not found" in (result.error or "")


def test_insufficient_matches_writes_failure_metadata(tmp_path: Path) -> None:
    source = _source_trajectory()
    reconstruction_dir = _write_reconstruction(tmp_path, source)
    gps_path = tmp_path / "gps.json"
    target = source[:2]
    _write_gps_json(
        gps_path,
        target,
        image_names=["frame_000000.jpg", "frame_000006.jpg"],
    )
    output_dir = tmp_path / "georeferenced"

    result = georeference_reconstruction(reconstruction_dir, gps_path, output_dir)

    assert not result.success
    assert "At least three matched" in (result.error or "")
    metadata = json.loads((output_dir / "georef_metadata.json").read_text())
    assert metadata["success"] is False


def test_non_empty_output_without_overwrite_is_left_untouched(tmp_path: Path) -> None:
    source = _source_trajectory()
    reconstruction_dir = _write_reconstruction(tmp_path, source)
    gps_path = tmp_path / "gps.json"
    _write_gps_json(
        gps_path,
        source,
        image_names=[f"frame_{index * 6:06d}.jpg" for index in range(len(source))],
    )
    output_dir = tmp_path / "georeferenced"
    output_dir.mkdir()
    sentinel = output_dir / "existing-result.txt"
    sentinel.write_text("preserve this output")

    result = georeference_reconstruction(reconstruction_dir, gps_path, output_dir)

    assert not result.success
    assert "not empty" in (result.error or "")
    assert sentinel.read_text() == "preserve this output"
    assert not (output_dir / "georef_metadata.json").exists()
