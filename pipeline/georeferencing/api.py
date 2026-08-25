"""Public API for SkyTrace Step 3 georeferencing and metric scaling."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from pipeline.georeferencing.alignment import estimate_robust_similarity_transform
from pipeline.georeferencing.coordinates import choose_enu_reference, geodetic_to_enu
from pipeline.georeferencing.correspondence import match_camera_poses_to_gps
from pipeline.georeferencing.errors import (
    CorrespondenceError,
    GeoreferencingError,
)
from pipeline.georeferencing.gps import load_gps_metadata
from pipeline.georeferencing.models import GeoreferencingConfig, GeoreferencingResult
from pipeline.georeferencing.output import (
    prepare_output_directory,
    write_camera_trajectory,
    write_correspondences,
    write_result_metadata,
    write_transform,
    write_validation,
)
from pipeline.georeferencing.ply import transform_ply
from pipeline.georeferencing.reconstruction import load_reconstruction_data


def _source_is_metric(config: GeoreferencingConfig, declared_metric: bool) -> bool:
    if config.source_scale_mode == "metric":
        return True
    if config.source_scale_mode == "arbitrary":
        return False
    return declared_metric


def georeference_reconstruction(
    reconstruction_dir: str | Path,
    gps_metadata_path: str | Path,
    output_dir: str | Path,
    *,
    point_cloud_path: str | Path | None = None,
    timestamp_tolerance_seconds: float = 1.0,
    ransac_threshold_metres: float = 10.0,
    ransac_iterations: int = 300,
    source_scale_mode: str = "auto",
    overwrite: bool = False,
) -> GeoreferencingResult:
    """Align Step 2's local model to GPS-derived local ENU metres.

    The function reads Step 2's ``camera_poses.json`` and either its dense PLY
    or sparse PLY. GPS matches use image name, Step 1 frame index, then (when
    available) a Step 1 manifest timestamp with local-ENU interpolation.

    For arbitrary-scale reconstructions it estimates a global Sim(3) from
    camera/GPS pairs. If Step 2 explicitly declares a metric source, the
    default ``source_scale_mode='auto'`` fixes the scale at 1 and estimates a
    rigid transform instead. Neither outcome claims survey or measurement
    accuracy: residuals only describe this trajectory-to-GPS fit.
    """
    started_at = time.monotonic()
    config: GeoreferencingConfig | None = None
    result: GeoreferencingResult | None = None
    output_workspace_prepared = False
    try:
        config = GeoreferencingConfig(
            reconstruction_dir=Path(reconstruction_dir),
            gps_metadata_path=Path(gps_metadata_path),
            output_dir=Path(output_dir),
            point_cloud_path=Path(point_cloud_path) if point_cloud_path else None,
            timestamp_tolerance_seconds=timestamp_tolerance_seconds,
            ransac_threshold_metres=ransac_threshold_metres,
            ransac_iterations=ransac_iterations,
            source_scale_mode=source_scale_mode,
            overwrite=overwrite,
        )
        reconstruction = load_reconstruction_data(
            config.reconstruction_dir, config.point_cloud_path
        )
        gps_dataset = load_gps_metadata(config.gps_metadata_path)
        prepare_output_directory(config)
        output_workspace_prepared = True

        reference = choose_enu_reference(gps_dataset.observations)
        gps_enu_positions = {
            observation.observation_id: geodetic_to_enu(
                observation.latitude,
                observation.longitude,
                observation.altitude,
                reference,
            )
            for observation in gps_dataset.observations
        }
        correspondences, correspondence_warnings = match_camera_poses_to_gps(
            reconstruction.poses,
            gps_dataset.observations,
            gps_enu_positions,
            timestamp_tolerance_seconds=config.timestamp_tolerance_seconds,
        )
        if len(correspondences) < 3:
            raise CorrespondenceError(
                "At least three matched camera/GPS observations are required; "
                f"found {len(correspondences)} from {len(reconstruction.poses)} poses."
            )

        source_positions = np.vstack(
            [correspondence.pose.camera_center for correspondence in correspondences]
        )
        target_positions = np.vstack(
            [correspondence.target_enu for correspondence in correspondences]
        )
        source_is_metric = _source_is_metric(
            config, reconstruction.source_scale_is_metric
        )
        alignment = estimate_robust_similarity_transform(
            source_positions,
            target_positions,
            estimate_scale=not source_is_metric,
            threshold_metres=config.ransac_threshold_metres,
            max_iterations=config.ransac_iterations,
        )

        transform_ply(
            reconstruction.point_cloud_path,
            config.georeferenced_point_cloud_path,
            alignment.transform,
        )
        transformed_centers = alignment.transform.apply(
            np.vstack([pose.camera_center for pose in reconstruction.poses])
        )
        write_camera_trajectory(
            config.camera_trajectory_path,
            reconstruction.poses,
            transformed_centers,
            correspondences,
            alignment,
        )
        write_transform(
            config.transform_path,
            alignment,
            reference,
            gps_dataset,
            source_declared_metric=reconstruction.source_scale_is_metric,
            source_scale_mode=config.source_scale_mode,
            source_scale_treated_as_metric=source_is_metric,
            source_scale_description=reconstruction.source_scale_description,
        )
        write_correspondences(config.correspondences_path, correspondences, alignment)
        write_validation(
            config.validation_path,
            pose_count=len(reconstruction.poses),
            gps_count=len(gps_dataset.observations),
            correspondences=correspondences,
            alignment=alignment,
            threshold_metres=config.ransac_threshold_metres,
        )
        inlier_residuals = alignment.residuals_metres[alignment.inlier_mask]
        warnings = (
            reconstruction.warnings + gps_dataset.warnings + correspondence_warnings
        )
        if source_is_metric:
            warnings.append(
                "Step 2 declared metric scale (or source_scale_mode forced it), so "
                "Step 3 fixed scale to 1.0 and did not apply a second scale estimate."
            )
        else:
            warnings.append(
                "Estimated scale is a global camera-trajectory-to-GPS Sim(3) fit. It "
                "does not establish survey-grade or universally accurate measurements."
            )
        if alignment.inlier_count == 3:
            warnings.append(
                "Only three inlier correspondences support this transform; collect more "
                "spatially diverse GPS-tagged frames before relying on it downstream."
            )
        result = GeoreferencingResult(
            success=True,
            reconstruction_dir=config.reconstruction_dir,
            gps_metadata_path=config.gps_metadata_path,
            output_dir=config.output_dir,
            gps_observation_count=len(gps_dataset.observations),
            matched_pose_count=len(correspondences),
            inlier_count=alignment.inlier_count,
            alignment_method=alignment.method,
            estimated_scale=float(alignment.transform.scale),
            trajectory_rmse_metres=float(np.sqrt(np.mean(inlier_residuals**2))),
            trajectory_median_residual_metres=float(np.median(inlier_residuals)),
            trajectory_max_residual_metres=float(np.max(inlier_residuals)),
            point_cloud_path=config.georeferenced_point_cloud_path,
            camera_trajectory_path=config.camera_trajectory_path,
            transform_path=config.transform_path,
            validation_path=config.validation_path,
            correspondences_path=config.correspondences_path,
            warnings=warnings,
        )
    except (GeoreferencingError, ValueError, OSError) as exc:
        if config is None:
            reconstruction_path = Path(reconstruction_dir)
            gps_path = Path(gps_metadata_path)
            output_path = Path(output_dir)
        else:
            reconstruction_path = config.reconstruction_dir
            gps_path = config.gps_metadata_path
            output_path = config.output_dir
        result = GeoreferencingResult(
            success=False,
            reconstruction_dir=reconstruction_path,
            gps_metadata_path=gps_path,
            output_dir=output_path,
            error=str(exc),
        )

    result.processing_time_seconds = time.monotonic() - started_at
    # Never add a file to an existing non-empty directory after it rejected this
    # run because overwrite=False.  Persist failures only once this invocation
    # has successfully created (or recreated) its own output workspace.
    if config is not None and output_workspace_prepared:
        write_result_metadata(config.metadata_path, result)
    return result
