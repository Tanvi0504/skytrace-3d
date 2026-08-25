"""Writers for reproducible Step 3 georeferencing artifacts."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.georeferencing.errors import GeoreferenceOutputError
from pipeline.georeferencing.models import (
    AlignmentEstimate,
    CameraPose,
    Correspondence,
    GeoreferencingConfig,
    GeoreferencingResult,
    GPSDataset,
    LocalENUReference,
)


def prepare_output_directory(config: GeoreferencingConfig) -> None:
    """Create a fresh Step 3 directory without risking a Step 2 input folder."""
    output = config.output_dir.resolve()
    reconstruction = config.reconstruction_dir.resolve()
    if output == reconstruction or output in reconstruction.parents:
        raise GeoreferenceOutputError(
            "Georeferencing output must not be the reconstruction directory or one "
            f"of its parents: {config.output_dir}"
        )
    if config.output_dir.exists() and any(config.output_dir.iterdir()):
        if not config.overwrite:
            raise GeoreferenceOutputError(
                f"Georeferencing output directory is not empty: {config.output_dir}. "
                "Use a new directory or set overwrite=True."
            )
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_camera_trajectory(
    path: Path,
    poses: list[CameraPose],
    transformed_centers: np.ndarray,
    correspondences: list[Correspondence],
    alignment: AlignmentEstimate,
) -> None:
    """Write every reconstructed camera in the target local-ENU coordinate frame."""
    matching_index = {item.pose.image_id: index for index, item in enumerate(correspondences)}
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination,
            fieldnames=[
                "image_id",
                "image_name",
                "timestamp_seconds",
                "source_colmap_x",
                "source_colmap_y",
                "source_colmap_z",
                "enu_east_m",
                "enu_north_m",
                "enu_up_m",
                "matched_gps_observation_ids",
                "match_method",
                "alignment_residual_m",
                "alignment_inlier",
            ],
        )
        writer.writeheader()
        for pose, target_center in zip(poses, transformed_centers):
            match_index = matching_index.get(pose.image_id)
            match = correspondences[match_index] if match_index is not None else None
            writer.writerow(
                {
                    "image_id": pose.image_id,
                    "image_name": pose.image_name,
                    "timestamp_seconds": pose.timestamp_seconds,
                    "source_colmap_x": pose.camera_center[0],
                    "source_colmap_y": pose.camera_center[1],
                    "source_colmap_z": pose.camera_center[2],
                    "enu_east_m": target_center[0],
                    "enu_north_m": target_center[1],
                    "enu_up_m": target_center[2],
                    "matched_gps_observation_ids": (
                        ";".join(match.gps_observation_ids) if match else ""
                    ),
                    "match_method": match.method if match else "",
                    "alignment_residual_m": (
                        alignment.residuals_metres[match_index]
                        if match_index is not None
                        else ""
                    ),
                    "alignment_inlier": (
                        bool(alignment.inlier_mask[match_index])
                        if match_index is not None
                        else ""
                    ),
                }
            )


def write_correspondences(
    path: Path,
    correspondences: list[Correspondence],
    alignment: AlignmentEstimate,
) -> None:
    """Persist used and rejected trajectory observations without deleting evidence."""
    payload = {
        "description": (
            "Camera/GPS trajectory correspondences. Residuals are in local ENU metres "
            "after fitting and are not 3D reconstruction accuracy measurements."
        ),
        "correspondences": [
            {
                "image_id": correspondence.pose.image_id,
                "image_name": correspondence.pose.image_name,
                "gps_observation_ids": list(correspondence.gps_observation_ids),
                "match_method": correspondence.method,
                "source_camera_center_colmap": correspondence.pose.camera_center.tolist(),
                "target_gps_enu_metres": correspondence.target_enu.tolist(),
                "residual_metres": float(alignment.residuals_metres[index]),
                "inlier": bool(alignment.inlier_mask[index]),
                "rejection_reason": (
                    None
                    if alignment.inlier_mask[index]
                    else "Residual exceeds configured RANSAC inlier threshold"
                ),
            }
            for index, correspondence in enumerate(correspondences)
        ],
    }
    write_json(path, payload)


def write_transform(
    path: Path,
    alignment: AlignmentEstimate,
    reference: LocalENUReference,
    gps_dataset: GPSDataset,
    *,
    source_declared_metric: bool,
    source_scale_mode: str,
    source_scale_treated_as_metric: bool,
    source_scale_description: str,
) -> None:
    """Write all parameters necessary to reproduce the source-to-ENU map."""
    payload = {
        "schema_version": 1,
        "source_coordinate_system": "COLMAP reconstruction coordinates",
        "source_scale_declaration": source_scale_description,
        "source_declared_metric": source_declared_metric,
        "source_scale_mode": source_scale_mode,
        "source_scale_treated_as_metric": source_scale_treated_as_metric,
        "scale_estimated": not source_scale_treated_as_metric,
        "target_coordinate_system": "Local East-North-Up (ENU), metres",
        "target_reference": {
            "geographic_coordinate_system": gps_dataset.source_coordinate_system,
            "altitude_reference": gps_dataset.altitude_reference,
            "enu_origin": reference.to_dict(),
        },
        "alignment_method": alignment.method,
        "gps_points_used": alignment.inlier_count,
        "gps_points_rejected_as_outliers": alignment.outlier_count,
        "transform": alignment.transform.to_dict(),
    }
    write_json(path, payload)


def write_validation(
    path: Path,
    *,
    pose_count: int,
    gps_count: int,
    correspondences: list[Correspondence],
    alignment: AlignmentEstimate,
    threshold_metres: float,
) -> None:
    """Write trajectory-fit diagnostics with intentionally conservative labels."""
    inlier_residuals = alignment.residuals_metres[alignment.inlier_mask]
    support = (
        "limited: only the minimum three inlier correspondences constrain the transform"
        if alignment.inlier_count == 3
        else "more than the minimum three inlier correspondences support the transform"
    )
    payload = {
        "metric_scope": (
            "These are camera-trajectory-to-GPS alignment residuals in local ENU metres. "
            "They are not a measured 3D geometry error, measurement accuracy, or survey accuracy."
        ),
        "reconstructed_camera_pose_count": pose_count,
        "gps_observation_count": gps_count,
        "matched_camera_gps_count": len(correspondences),
        "matched_pose_percentage": 100.0 * len(correspondences) / pose_count,
        "inlier_count": alignment.inlier_count,
        "outlier_count": alignment.outlier_count,
        "ransac_inlier_threshold_metres": threshold_metres,
        "alignment_support_assessment": support,
        "residuals_metres": {
            "inlier_rmse": float(np.sqrt(np.mean(inlier_residuals**2))),
            "inlier_median": float(np.median(inlier_residuals)),
            "inlier_maximum": float(np.max(inlier_residuals)),
            "all_matched_maximum": float(np.max(alignment.residuals_metres)),
        },
    }
    write_json(path, payload)


def write_result_metadata(path: Path, result: GeoreferencingResult) -> None:
    """Write the structured API result for both successful and failed attempts."""
    result.metadata_path = path
    write_json(path, result.to_dict())
