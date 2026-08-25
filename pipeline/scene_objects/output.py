"""Safe, reproducible writers for Step 5 scene-association outputs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pipeline.scene_objects.errors import SceneOutputError
from pipeline.scene_objects.models import (
    SceneAssociationConfig,
    SceneAssociationResult,
    SceneObjectAssociation,
)


def prepare_output_directory(config: SceneAssociationConfig) -> None:
    """Create an isolated Step 5 directory without modifying upstream artifacts."""
    output = config.output_dir.resolve()
    inputs = [config.object_dir.resolve(), config.reconstruction_dir.resolve()]
    if config.georeferenced_dir is not None:
        inputs.append(config.georeferenced_dir.resolve())
    if any(output == item or output in item.parents for item in inputs):
        raise SceneOutputError(
            "Scene-object output must not be an input directory or one of its parents: "
            f"{config.output_dir}"
        )
    if config.output_dir.exists() and any(config.output_dir.iterdir()):
        if not config.overwrite:
            raise SceneOutputError(
                f"Scene-object output directory is not empty: {config.output_dir}. "
                "Use a new directory or set overwrite=True."
            )
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_associations(config: SceneAssociationConfig, associations: list[SceneObjectAssociation]) -> None:
    """Write object markers, track summaries, trajectories, and scene annotations."""
    serialized = [association.to_dict() for association in associations]
    _write_json(
        config.objects_3d_path,
        {
            "schema_version": 1,
            "description": (
                "Per-track 3D association estimates. A position is written only when "
                "calibrated multi-view geometry is non-degenerate; it is not ground truth."
            ),
            "objects": serialized,
        },
    )
    _write_json(
        config.tracks_3d_path,
        {
            "schema_version": 1,
            "description": (
                "Track-level temporal evidence and one optional fused spatial anchor. "
                "Track IDs originate in Step 4."
            ),
            "tracks": [
                {
                    "object_id": item.object_id,
                    "track_id": item.track_id,
                    "class": item.class_name,
                    "observation_count": item.observation_count,
                    "usable_observation_count": item.usable_observation_count,
                    "first_frame_index": item.first_frame_index,
                    "last_frame_index": item.last_frame_index,
                    "detection_confidence": {
                        "minimum": item.minimum_detection_confidence,
                        "mean": item.mean_detection_confidence,
                        "median": item.median_detection_confidence,
                        "maximum": item.maximum_detection_confidence,
                    },
                    "class_consistency": item.class_consistency,
                    "position_status": item.position_status,
                    "evidence_score": item.evidence_score,
                }
                for item in associations
            ],
        },
    )
    _write_json(
        config.trajectories_path,
        {
            "schema_version": 1,
            "description": (
                "No time-resolved 3D trajectory is fabricated from 2D tracking. This "
                "baseline emits one fused anchor at most per track."
            ),
            "trajectories": [
                {
                    "object_id": item.object_id,
                    "track_id": item.track_id,
                    "status": "unavailable",
                    "reason": (
                        "Per-frame depth or independently validated temporal 3D estimates "
                        "are required before a 3D trajectory can be published."
                    ),
                }
                for item in associations
            ],
        },
    )
    _write_json(
        config.annotations_path,
        {
            "schema_version": 1,
            "description": (
                "Lightweight semantic marker annotations, not a duplicate reconstruction "
                "or an object-mesh/dimension estimate."
            ),
            "annotations": [
                {
                    "object_id": item.object_id,
                    "semantic_label": item.class_name,
                    "track_id": item.track_id,
                    "position": (
                        item.world_position.tolist()
                        if item.world_position is not None
                        else item.source_position.tolist()
                    ),
                    "coordinate_system": item.coordinate_system,
                    "position_status": item.position_status,
                    "evidence_score": item.evidence_score,
                }
                for item in associations
                if item.source_position is not None
            ],
        },
    )


def write_metadata(
    path: Path,
    result: SceneAssociationResult,
    config: SceneAssociationConfig,
) -> None:
    """Persist result state, transparent score terms, and important limitations."""
    result.metadata_path = path
    payload = result.to_dict()
    payload.update(
        {
            "schema_version": 1,
            "configuration": {
                "minimum_ray_angle_degrees": config.minimum_ray_angle_degrees,
                "max_normalized_ray_residual": config.max_normalized_ray_residual,
                "max_condition_number": config.max_condition_number,
            },
            "anchor_point": {
                "name": "bounding_box_bottom_center",
                "reason": (
                    "It is a cautious proxy for ground contact for people and ground "
                    "vehicles; it is not proof that the point lies on a scene surface."
                ),
            },
            "evidence_score": {
                "meaning": "A transparent evidence-strength indicator, not positional accuracy.",
                "formula": (
                    "mean_detection_confidence * (1 - 1 / usable_observation_count) * "
                    "sin(median_pairwise_ray_angle) * "
                    "(1 / (1 + ray_rmse / median_camera_baseline))"
                ),
                "terms": {
                    "mean_detection_confidence": "Mean Step 4 confidence across calibrated observations.",
                    "observation_support": "1 - 1/n; increases with independent calibrated views.",
                    "view_diversity": "sin of the median pairwise ray angle; parallel rays have no depth strength.",
                    "ray_consistency": "1 / (1 + ray RMSE / median camera baseline); dimensionless and scale-invariant.",
                },
            },
            "limitations": [
                "A 2D bounding box alone never produces a 3D coordinate in this module.",
                "Dynamic-capable tracks may violate the static-anchor triangulation assumption.",
                "No ground plane or point-cloud surface is inferred automatically from sparse geometry.",
                "A low-confidence estimate is not a ground-truth location or measurement result.",
                "3D trajectories remain unavailable until reliable time-resolved depth is available.",
            ],
        }
    )
    _write_json(path, payload)
