"""Readers for the Step 2 reconstruction artifacts consumed by Step 3."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

import numpy as np

from pipeline.georeferencing.errors import PointCloudError, ReconstructionInputError
from pipeline.georeferencing.models import CameraPose, ReconstructionData

_FRAME_NAME_PATTERN = re.compile(r"frame_(\d+)", re.IGNORECASE)


def frame_index_from_image_name(image_name: str) -> Optional[int]:
    """Extract Step 1's source-frame index from its selected image filename."""
    match = _FRAME_NAME_PATTERN.search(Path(image_name).name)
    return int(match.group(1)) if match else None


def _load_manifest_timestamps(reconstruction_dir: Path) -> tuple[dict[str, float], list[str]]:
    manifest_path = reconstruction_dir.parent / "frame_manifest.json"
    if not manifest_path.is_file():
        return {}, [
            "Step 1 frame_manifest.json was not found beside reconstruction/. "
            "Timestamp-based GPS matching is unavailable unless poses contain timestamps."
        ]
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = document.get("frames", [])
        timestamps = {
            str(record["filename"]): float(record["timestamp_seconds"])
            for record in records
            if isinstance(record, dict)
            and record.get("selected") is True
            and record.get("filename")
            and record.get("timestamp_seconds") is not None
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return {}, [f"Could not read Step 1 timestamp manifest: {exc}"]
    return timestamps, []


def _source_declares_metric_scale(document: dict[str, Any]) -> tuple[bool, str]:
    """Read current and forward-compatible Step 2 scale declarations.

    The current COLMAP exporter uses a human-readable ``scale`` string. Future
    reconstruction backends can instead provide an unambiguous boolean either
    at the document root or inside a structured ``scale`` object.
    """
    for key in ("scale_is_metric", "metric_scale"):
        value = document.get(key)
        if isinstance(value, bool):
            return value, f"{key}={value}"

    declaration = document.get("scale", "not declared")
    if isinstance(declaration, dict):
        value = declaration.get("is_metric")
        if isinstance(value, bool):
            return value, json.dumps(declaration, sort_keys=True)
        units = str(declaration.get("units", "")).lower()
        if units in {"m", "metre", "metres", "meter", "meters"}:
            return True, json.dumps(declaration, sort_keys=True)
        return False, json.dumps(declaration, sort_keys=True)

    description = str(declaration)
    normalised = description.lower()
    is_metric = (
        "metric" in normalised
        and "arbitrary" not in normalised
        and "not metric" not in normalised
    )
    return is_metric, description


def select_point_cloud(reconstruction_dir: Path, requested_path: Path | None) -> Path:
    """Choose the requested, dense, or sparse Step 2 PLY in that order."""
    candidates = (
        [requested_path]
        if requested_path is not None
        else [
            reconstruction_dir / "dense" / "fused.ply",
            reconstruction_dir / "sparse" / "sparse.ply",
        ]
    )
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    searched = ", ".join(str(path) for path in candidates if path is not None)
    raise PointCloudError(f"No Step 2 point-cloud PLY found. Looked for: {searched}")


def load_reconstruction_data(
    reconstruction_dir: Path,
    requested_point_cloud: Path | None = None,
) -> ReconstructionData:
    """Load camera centers, scale declaration, and one PLY from Step 2 output."""
    if not reconstruction_dir.is_dir():
        raise ReconstructionInputError(
            f"Step 2 reconstruction directory not found: {reconstruction_dir}"
        )
    poses_path = reconstruction_dir / "camera_poses.json"
    if not poses_path.is_file():
        raise ReconstructionInputError(
            f"Step 2 camera poses file not found: {poses_path}"
        )
    try:
        document = json.loads(poses_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReconstructionInputError(f"Step 2 camera poses JSON is invalid: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("poses"), list):
        raise ReconstructionInputError("Step 2 camera_poses.json must contain a 'poses' array")

    manifest_timestamps, warnings = _load_manifest_timestamps(reconstruction_dir)
    poses: list[CameraPose] = []
    for index, record in enumerate(document["poses"], start=1):
        try:
            if not isinstance(record, dict):
                raise ValueError("pose is not an object")
            image_name = str(record["image_name"])
            center = np.asarray(record["camera_center_world"], dtype=float)
            if center.shape != (3,) or not np.all(np.isfinite(center)):
                raise ValueError("camera_center_world must contain three finite numbers")
            direct_timestamp = record.get("timestamp_seconds")
            timestamp = (
                float(direct_timestamp)
                if direct_timestamp is not None
                else manifest_timestamps.get(image_name)
            )
            if timestamp is not None and not np.isfinite(timestamp):
                raise ValueError("timestamp_seconds must be finite")
            poses.append(
                CameraPose(
                    image_id=int(record.get("image_id", index)),
                    image_name=image_name,
                    camera_center=center,
                    timestamp_seconds=timestamp,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            warnings.append(f"Ignored malformed Step 2 pose {index}: {exc}.")
    if not poses:
        raise ReconstructionInputError("Step 2 camera_poses.json contains no usable poses")

    source_scale_is_metric, source_scale_description = _source_declares_metric_scale(document)
    return ReconstructionData(
        poses=poses,
        point_cloud_path=select_point_cloud(reconstruction_dir, requested_point_cloud),
        source_scale_is_metric=source_scale_is_metric,
        source_scale_description=source_scale_description,
        warnings=warnings,
    )
