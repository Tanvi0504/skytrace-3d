"""Readers for the existing Step 2, Step 3, and Step 4 artifact formats."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.scene_objects.errors import (
    CameraCalibrationError,
    GeometryError,
    ObjectInputError,
    ReconstructionInputError,
)
from pipeline.scene_objects.geometry import quaternion_to_rotation_matrix
from pipeline.scene_objects.models import (
    CameraIntrinsics,
    GeoreferenceTransform,
    ObjectObservation,
    ReconstructionCameraPose,
)


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ObjectInputError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ObjectInputError(f"{label} is invalid JSON: {path}: {exc}") from exc


def load_object_observations(object_dir: Path) -> tuple[dict[int, list[ObjectObservation]], list[str]]:
    """Read Step 4 detections and group only valid tracker-ID observations."""
    if not object_dir.is_dir():
        raise ObjectInputError(f"Step 4 object directory not found: {object_dir}")
    document = _read_json(object_dir / "detections.json", "Step 4 detections.json")
    if not isinstance(document, dict) or not isinstance(document.get("detections"), list):
        raise ObjectInputError("Step 4 detections.json must contain a 'detections' array")
    grouped: dict[int, list[ObjectObservation]] = defaultdict(list)
    warnings: list[str] = []
    for row_number, record in enumerate(document["detections"], start=1):
        if not isinstance(record, dict):
            warnings.append(f"Ignored non-object detection record {row_number}.")
            continue
        try:
            track_id = record.get("track_id")
            if isinstance(track_id, bool) or not isinstance(track_id, int):
                if track_id is not None:
                    warnings.append(
                        f"Ignored detection {row_number}: track_id must be an integer."
                    )
                continue
            class_name = str(record["class"]).strip().lower()
            confidence = float(record["confidence"])
            bbox = tuple(float(value) for value in record["bbox_xyxy_pixels"])
            if not class_name or not 0.0 <= confidence <= 1.0 or len(bbox) != 4:
                raise ValueError("class, confidence, or bbox is invalid")
            if not all(math.isfinite(value) for value in bbox) or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                raise ValueError("bbox must be finite with positive area")
            frame_index_value = record.get("frame_index")
            frame_index = (
                frame_index_value
                if isinstance(frame_index_value, int) and not isinstance(frame_index_value, bool)
                else None
            )
            timestamp_value = record.get("timestamp_seconds")
            timestamp = (
                float(timestamp_value)
                if isinstance(timestamp_value, (int, float))
                and math.isfinite(float(timestamp_value))
                else None
            )
            grouped[track_id].append(
                ObjectObservation(
                    detection_id=str(record.get("detection_id", f"row_{row_number}")),
                    track_id=track_id,
                    class_name=class_name,
                    confidence=confidence,
                    frame_filename=Path(str(record["frame_filename"])).name,
                    frame_index=frame_index,
                    timestamp_seconds=timestamp,
                    bbox_xyxy=bbox,
                    is_dynamic_candidate=bool(record.get("is_dynamic_candidate", False)),
                )
            )
        except (GeometryError, KeyError, TypeError, ValueError) as exc:
            warnings.append(f"Ignored malformed detection {row_number}: {exc}.")
    if not grouped:
        warnings.append(
            "No valid detections with tracker IDs were found. Step 5 only associates "
            "tracked observations; untracked 2D detections remain in Step 4 output."
        )
    for observations in grouped.values():
        observations.sort(
            key=lambda item: (
                item.timestamp_seconds is None,
                item.timestamp_seconds if item.timestamp_seconds is not None else float("inf"),
                item.frame_filename,
                item.detection_id,
            )
        )
    return dict(grouped), warnings


def load_reconstruction_poses(
    reconstruction_dir: Path,
) -> tuple[dict[str, ReconstructionCameraPose], list[str]]:
    """Load Step 2's exported COLMAP poses including real camera orientations."""
    if not reconstruction_dir.is_dir():
        raise ReconstructionInputError(
            f"Step 2 reconstruction directory not found: {reconstruction_dir}"
        )
    path = reconstruction_dir / "camera_poses.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReconstructionInputError(f"Step 2 camera poses file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReconstructionInputError(f"Step 2 camera poses JSON is invalid: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("poses"), list):
        raise ReconstructionInputError("Step 2 camera_poses.json must contain a 'poses' array")
    poses: dict[str, ReconstructionCameraPose] = {}
    warnings: list[str] = []
    for row_number, record in enumerate(document["poses"], start=1):
        try:
            if not isinstance(record, dict):
                raise ValueError("pose is not an object")
            image_name = Path(str(record["image_name"])).name
            image_id = int(record["image_id"])
            camera_id = int(record["camera_id"])
            rotation = quaternion_to_rotation_matrix(
                np.asarray(record["qvec_world_to_camera"], dtype=float)
            )
            translation = np.asarray(record["tvec_world_to_camera"], dtype=float)
            if translation.shape != (3,) or not np.all(np.isfinite(translation)):
                raise ValueError("tvec_world_to_camera must contain three finite numbers")
            centre = -rotation.T @ translation
            poses[image_name] = ReconstructionCameraPose(
                image_id=image_id,
                image_name=image_name,
                camera_id=camera_id,
                rotation_world_to_camera=rotation,
                translation_world_to_camera=translation,
                camera_center_world=centre,
            )
        except (KeyError, TypeError, ValueError) as exc:
            warnings.append(f"Ignored malformed Step 2 camera pose {row_number}: {exc}.")
    if not poses:
        raise ReconstructionInputError(
            "Step 2 camera_poses.json contains no usable oriented camera poses"
        )
    return poses, warnings


def _camera_text_path(reconstruction_dir: Path) -> tuple[Path | None, list[str]]:
    """Locate the Step 2 selected-model camera export without assuming model '0'."""
    warnings: list[str] = []
    metadata_path = reconstruction_dir / "reconstruction_metadata.json"
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            configured = metadata.get("output_locations", {}).get("sparse_text")
            if configured:
                candidate = Path(str(configured)) / "cameras.txt"
                if candidate.is_file():
                    return candidate, warnings
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            warnings.append("Could not use reconstruction_metadata.json to locate cameras.txt.")
    candidates = sorted((reconstruction_dir / "sparse" / "text").glob("*/cameras.txt"))
    direct = reconstruction_dir / "sparse" / "text" / "cameras.txt"
    if direct.is_file():
        candidates.insert(0, direct)
    if not candidates:
        warnings.append(
            "No Step 2 COLMAP cameras.txt export was found. Camera intrinsics are "
            "unavailable, so no calibrated 3D rays can be created."
        )
        return None, warnings
    if len(candidates) > 1:
        warnings.append(
            "Multiple COLMAP cameras.txt exports were found; using the first sorted "
            f"candidate: {candidates[0]}."
        )
    return candidates[0], warnings


def load_camera_intrinsics(
    reconstruction_dir: Path,
) -> tuple[dict[int, CameraIntrinsics], list[str]]:
    """Parse COLMAP's actual ``cameras.txt`` calibration records when available."""
    path, warnings = _camera_text_path(reconstruction_dir)
    if path is None:
        return {}, warnings
    cameras: dict[int, CameraIntrinsics] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {}, warnings + [f"Could not read COLMAP cameras.txt: {exc}"]
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        try:
            if len(parts) < 5:
                raise ValueError("camera record has too few fields")
            camera_id = int(parts[0])
            model = parts[1]
            width, height = int(parts[2]), int(parts[3])
            parameters = tuple(float(value) for value in parts[4:])
            if width <= 0 or height <= 0 or not all(math.isfinite(value) for value in parameters):
                raise ValueError("camera dimensions or parameters are invalid")
            cameras[camera_id] = CameraIntrinsics(
                camera_id=camera_id,
                model=model,
                width=width,
                height=height,
                parameters=parameters,
            )
        except (TypeError, ValueError) as exc:
            warnings.append(f"Ignored malformed cameras.txt line {line_number}: {exc}.")
    if not cameras:
        warnings.append("COLMAP cameras.txt contains no usable camera intrinsics.")
    return cameras, warnings


def load_georeference_transform(
    georeferenced_dir: Path | None,
) -> tuple[GeoreferenceTransform | None, list[str]]:
    """Load Step 3's published source-to-ENU map; never infer one independently."""
    if georeferenced_dir is None:
        return None, [
            "No Step 3 georeferenced directory was supplied; world coordinates and "
            "latitude/longitude are unavailable."
        ]
    path = georeferenced_dir / "transform.json"
    if not path.is_file():
        return None, [
            f"Step 3 transform.json was not found: {path}. World coordinates are unavailable."
        ]
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        matrix = np.asarray(document["transform"]["matrix_4x4"], dtype=float)
        target = str(document["target_coordinate_system"])
        if matrix.shape != (4, 4) or not np.all(np.isfinite(matrix)):
            raise ValueError("matrix_4x4 must be a finite 4x4 matrix")
        origin = document.get("target_reference", {}).get("enu_origin", {})
        latitude = origin.get("latitude_degrees")
        longitude = origin.get("longitude_degrees")
        altitude = origin.get("altitude_metres")
        values = (latitude, longitude, altitude)
        if all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in values):
            latitude_value, longitude_value, altitude_value = (float(value) for value in values)
        else:
            latitude_value = longitude_value = altitude_value = None
        return (
            GeoreferenceTransform(
                matrix_4x4=matrix,
                target_coordinate_system=target,
                latitude_degrees=latitude_value,
                longitude_degrees=longitude_value,
                altitude_metres=altitude_value,
            ),
            [],
        )
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        return None, [
            f"Step 3 transform.json is unusable; world coordinates are unavailable: {exc}"
        ]


def apply_georeference_transform(
    source_position: np.ndarray,
    transform: GeoreferenceTransform,
) -> np.ndarray:
    """Apply Step 3's documented homogeneous source-to-ENU transform."""
    source = np.asarray(source_position, dtype=float)
    if source.shape != (3,) or not np.all(np.isfinite(source)):
        raise ValueError("source_position must contain three finite coordinates")
    transformed = transform.matrix_4x4 @ np.append(source, 1.0)
    if abs(transformed[3]) <= np.finfo(float).eps:
        raise ValueError("Step 3 transform produced a zero homogeneous coordinate")
    return transformed[:3] / transformed[3]
