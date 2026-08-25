"""Safe writers for Step 4 reusable object-intelligence artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pipeline.objects.errors import ObjectOutputError
from pipeline.objects.models import (
    DYNAMIC_CAPABLE_CLASSES,
    DetectorInfo,
    ObjectDetection,
    ObjectPipelineConfig,
    ObjectPipelineResult,
    TrackSummary,
)


def prepare_output_directory(config: ObjectPipelineConfig) -> None:
    """Prepare an isolated output directory without modifying source frames."""
    output = config.output_dir.resolve()
    frames = config.frames_dir.resolve()
    if output == frames or output in frames.parents:
        raise ObjectOutputError(
            "Object output must not be the selected-frames directory or one of its "
            f"parents: {config.output_dir}"
        )
    if config.output_dir.exists() and any(config.output_dir.iterdir()):
        if not config.overwrite:
            raise ObjectOutputError(
                f"Object output directory is not empty: {config.output_dir}. "
                "Use a new directory or set overwrite=True."
            )
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_detections(
    path: Path,
    detections: list[ObjectDetection],
    detector: DetectorInfo,
) -> None:
    """Write per-frame 2D detections for later 2D-to-3D association."""
    _write_json(
        path,
        {
            "schema_version": 1,
            "description": (
                "2D detections in source-image pixel coordinates. Their frame "
                "identity can later join Step 2 camera poses and Step 3 ENU cameras; "
                "they are not 3D object locations."
            ),
            "detector": {
                "backend": detector.backend,
                "model_name": detector.model_name,
                "device": detector.device,
            },
            "detections": [item.to_dict() for item in detections],
        },
    )


def write_tracks(
    path: Path,
    tracks: list[TrackSummary],
    detector: DetectorInfo,
    *,
    tracking_enabled: bool,
) -> None:
    """Write existing tracker IDs without inferring physical motion from pixels."""
    _write_json(
        path,
        {
            "schema_version": 1,
            "tracking_enabled": tracking_enabled,
            "tracker": detector.tracker_name if tracking_enabled else None,
            "description": (
                "Track IDs come from the configured existing tracker. They identify "
                "candidate temporal associations, not a camera-motion-compensated "
                "world-motion decision."
            ),
            "tracks": [item.to_dict() for item in tracks],
        },
    )


def write_metadata(
    path: Path,
    result: ObjectPipelineResult,
    config: ObjectPipelineConfig,
    detector: DetectorInfo | None,
) -> None:
    """Write success or failure metadata and explicit downstream limitations."""
    result.metadata_path = path
    payload = result.to_dict()
    payload.update(
        {
            "schema_version": 1,
            "configuration": {
                "confidence_threshold": config.confidence_threshold,
                "iou_threshold": config.iou_threshold,
                "classes": list(config.classes) if config.classes is not None else None,
                "tracking": config.tracking,
                "tracker_config": config.tracker_config if config.tracking else None,
                "mask_padding_pixels": config.mask_padding_pixels,
            },
            "dynamic_object_policy": {
                "dynamic_capable_classes": sorted(DYNAMIC_CAPABLE_CLASSES),
                "mask_rule": (
                    "Every dynamic-capable detection is included in its frame mask. "
                    "This is conservative and does not mean the object was observed moving."
                ),
                "motion_classification": (
                    "unknown: this baseline does not compensate image tracks for "
                    "drone-camera motion or estimate 3D object motion."
                ),
            },
            "future_3d_association": {
                "join_keys": [
                    "frame_filename",
                    "frame_index",
                    "timestamp_seconds",
                    "bbox_xyxy_pixels",
                ],
                "compatible_inputs": [
                    "Step 2 camera_poses.json keyed by image_name",
                    "Step 3 camera_trajectory_georef.csv keyed by image_name",
                    "camera intrinsics and multi-view correspondences",
                ],
                "limitation": (
                    "Reliable 3D placement requires camera calibration, matched views, "
                    "and geometry/ray intersection; this output contains only 2D evidence."
                ),
            },
            "detector": (
                {
                    "backend": detector.backend,
                    "model_name": detector.model_name,
                    "device": detector.device,
                    "supported_classes": list(detector.supported_classes),
                    "tracker": detector.tracker_name if config.tracking else None,
                }
                if detector is not None
                else None
            ),
        }
    )
    _write_json(path, payload)
