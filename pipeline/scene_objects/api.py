"""Public Step 5 API for conservative multi-view object-to-scene association."""

from __future__ import annotations

import math
import time
from collections import Counter
from pathlib import Path

import numpy as np

from pipeline.georeferencing.coordinates import enu_to_geodetic
from pipeline.georeferencing.models import LocalENUReference
from pipeline.scene_objects.errors import (
    CameraCalibrationError,
    GeometryError,
    SceneAssociationError,
)
from pipeline.scene_objects.geometry import pixel_to_world_ray, triangulate_rays
from pipeline.scene_objects.inputs import (
    apply_georeference_transform,
    load_camera_intrinsics,
    load_georeference_transform,
    load_object_observations,
    load_reconstruction_poses,
)
from pipeline.scene_objects.models import (
    GeoreferenceTransform,
    ObjectObservation,
    SceneAssociationConfig,
    SceneAssociationResult,
    SceneObjectAssociation,
    TriangulationEstimate,
)
from pipeline.scene_objects.output import (
    prepare_output_directory,
    write_associations,
    write_metadata,
)


def _track_identity(
    observations: list[ObjectObservation],
) -> tuple[str, float, float, float, float, float, int | None, int | None, bool]:
    labels = Counter(item.class_name for item in observations)
    class_name, class_count = labels.most_common(1)[0]
    confidences = np.array([item.confidence for item in observations], dtype=float)
    indices = [item.frame_index for item in observations if item.frame_index is not None]
    return (
        class_name,
        float(np.min(confidences)),
        float(np.mean(confidences)),
        float(np.median(confidences)),
        float(np.max(confidences)),
        class_count / len(observations),
        min(indices) if indices else None,
        max(indices) if indices else None,
        any(item.is_dynamic_candidate for item in observations),
    )


def _base_association(track_id: int, observations: list[ObjectObservation]) -> SceneObjectAssociation:
    (
        class_name,
        minimum_confidence,
        mean_confidence,
        median_confidence,
        maximum_confidence,
        consistency,
        first_frame,
        last_frame,
        dynamic,
    ) = _track_identity(observations)
    warnings = []
    if consistency < 1.0:
        warnings.append(
            "The tracker has inconsistent detector class labels; the most frequent label was used."
        )
    if dynamic:
        warnings.append(
            "This track is dynamic-capable. Multi-view triangulation assumes its bottom-center "
            "anchor is spatially consistent across supporting observations."
        )
    return SceneObjectAssociation(
        object_id=f"track_{track_id}",
        track_id=track_id,
        class_name=class_name,
        observation_count=len(observations),
        usable_observation_count=0,
        first_frame_index=first_frame,
        last_frame_index=last_frame,
        minimum_detection_confidence=minimum_confidence,
        mean_detection_confidence=mean_confidence,
        median_detection_confidence=median_confidence,
        maximum_detection_confidence=maximum_confidence,
        class_consistency=consistency,
        is_dynamic_candidate=dynamic,
        position_status="unavailable",
        coordinate_system="COLMAP reconstruction coordinates",
        warnings=warnings,
    )


def _evidence_score(
    estimate: TriangulationEstimate,
    usable_count: int,
    mean_confidence: float,
) -> tuple[float, dict[str, float], float]:
    """Calculate only dimensionless, documented evidence-strength terms."""
    support = 1.0 - 1.0 / usable_count
    diversity = math.sin(math.radians(estimate.median_ray_angle_degrees))
    diversity = max(0.0, min(1.0, diversity))
    if estimate.median_camera_baseline <= np.finfo(float).eps:
        consistency = 0.0
        normalized_residual = float("inf")
    else:
        normalized_residual = estimate.ray_rmse / estimate.median_camera_baseline
        consistency = 1.0 / (1.0 + normalized_residual)
    return (
        mean_confidence * support * diversity * consistency,
        {
            "mean_detection_confidence": mean_confidence,
            "observation_support": support,
            "view_diversity": diversity,
            "ray_consistency": consistency,
        },
        normalized_residual,
    )


def _set_world_position(
    association: SceneObjectAssociation,
    transform: GeoreferenceTransform | None,
) -> None:
    if association.source_position is None or transform is None:
        return
    try:
        world = apply_georeference_transform(association.source_position, transform)
    except ValueError as exc:
        association.warnings.append(f"Could not apply Step 3 transform: {exc}")
        return
    association.world_position = world
    association.coordinate_system = transform.target_coordinate_system
    association.world_coordinate_status = "estimated_transformed_coordinate_system"
    if (
        transform.latitude_degrees is not None
        and transform.longitude_degrees is not None
        and transform.altitude_metres is not None
        and "east-north-up" in transform.target_coordinate_system.lower()
    ):
        reference = LocalENUReference(
            latitude=transform.latitude_degrees,
            longitude=transform.longitude_degrees,
            altitude=transform.altitude_metres,
        )
        latitude, longitude, altitude = enu_to_geodetic(world, reference)
        association.latitude_degrees = latitude
        association.longitude_degrees = longitude
        association.altitude_metres = altitude
        association.world_coordinate_status = "estimated_local_enu_and_wgs84"
    elif "east-north-up" in transform.target_coordinate_system.lower():
        association.world_coordinate_status = "estimated_local_enu"
    else:
        association.warnings.append(
            "Step 3 target is not a usable ENU WGS-84 frame; latitude/longitude were not emitted."
        )


def _associate_track(
    track_id: int,
    observations: list[ObjectObservation],
    poses,
    cameras,
    transform: GeoreferenceTransform | None,
    config: SceneAssociationConfig,
) -> SceneObjectAssociation:
    association = _base_association(track_id, observations)
    rays = []
    for observation in observations:
        pose = poses.get(observation.frame_filename)
        if pose is None:
            association.warnings.append(
                f"No Step 2 camera pose matches {observation.frame_filename}."
            )
            continue
        camera = cameras.get(pose.camera_id)
        if camera is None:
            association.warnings.append(
                f"No usable intrinsics were found for camera ID {pose.camera_id}."
            )
            continue
        try:
            rays.append(
                pixel_to_world_ray(observation.anchor_pixel, camera, pose, observation)
            )
        except (CameraCalibrationError, GeometryError) as exc:
            association.warnings.append(
                f"Could not create a calibrated ray for {observation.frame_filename}: {exc}"
            )
    association.usable_observation_count = len(rays)
    if len(rays) < 2:
        association.warnings.append(
            "3D location unavailable: fewer than two calibrated observations support this track."
        )
        return association
    try:
        estimate = triangulate_rays(rays)
    except GeometryError as exc:
        association.warnings.append(f"3D location unavailable: {exc}")
        return association
    if estimate.condition_number > config.max_condition_number:
        association.condition_number = estimate.condition_number
        association.warnings.append(
            "3D location unavailable: viewing rays are numerically too ill-conditioned "
            "for the configured stability limit."
        )
        return association

    score, components, normalized_residual = _evidence_score(
        estimate, len(rays), association.mean_detection_confidence
    )
    association.source_position = estimate.position
    association.position_method = "calibrated_multi_view_ray_triangulation"
    association.evidence_score = score
    association.evidence_components = components
    association.ray_rmse_source_units = estimate.ray_rmse
    association.normalized_ray_residual = normalized_residual
    association.median_ray_angle_degrees = estimate.median_ray_angle_degrees
    association.condition_number = estimate.condition_number
    if (
        estimate.median_ray_angle_degrees < config.minimum_ray_angle_degrees
        or normalized_residual > config.max_normalized_ray_residual
    ):
        association.position_status = "low_confidence"
        association.warnings.append(
            "Triangulation produced a coordinate but has low geometric evidence under "
            "the configured ray-angle or normalized-residual criteria."
        )
    else:
        association.position_status = "estimated"
    _set_world_position(association, transform)
    return association


def associate_objects_with_3d_scene(
    object_dir: str | Path,
    reconstruction_dir: str | Path,
    output_dir: str | Path,
    *,
    georeferenced_dir: str | Path | None = None,
    minimum_ray_angle_degrees: float = 1.0,
    max_normalized_ray_residual: float = 0.25,
    max_condition_number: float = 1e8,
    overwrite: bool = False,
) -> SceneAssociationResult:
    """Associate Step 4 tracks to Step 2/3 geometry without inventing depth.

    A source-coordinate marker is emitted only from at least two calibrated,
    non-degenerate views using least-squares point-to-ray triangulation. Step 3
    world coordinates are emitted only by applying its stored transform. Missing
    calibration, poses, or adequate geometry creates an explicit unavailable
    result rather than a guessed coordinate.
    """
    started_at = time.monotonic()
    config: SceneAssociationConfig | None = None
    output_workspace_prepared = False
    result: SceneAssociationResult | None = None
    try:
        config = SceneAssociationConfig(
            object_dir=Path(object_dir),
            reconstruction_dir=Path(reconstruction_dir),
            output_dir=Path(output_dir),
            georeferenced_dir=Path(georeferenced_dir) if georeferenced_dir else None,
            minimum_ray_angle_degrees=minimum_ray_angle_degrees,
            max_normalized_ray_residual=max_normalized_ray_residual,
            max_condition_number=max_condition_number,
            overwrite=overwrite,
        )
        tracks, warnings = load_object_observations(config.object_dir)
        poses, pose_warnings = load_reconstruction_poses(config.reconstruction_dir)
        cameras, camera_warnings = load_camera_intrinsics(config.reconstruction_dir)
        transform, georef_warnings = load_georeference_transform(config.georeferenced_dir)
        warnings.extend(pose_warnings + camera_warnings + georef_warnings)
        prepare_output_directory(config)
        output_workspace_prepared = True

        associations = [
            _associate_track(track_id, observations, poses, cameras, transform, config)
            for track_id, observations in sorted(tracks.items())
        ]
        write_associations(config, associations)
        result = SceneAssociationResult(
            success=True,
            object_dir=config.object_dir,
            reconstruction_dir=config.reconstruction_dir,
            georeferenced_dir=config.georeferenced_dir,
            output_dir=config.output_dir,
            track_count=len(associations),
            estimated_count=sum(item.position_status == "estimated" for item in associations),
            low_confidence_count=sum(
                item.position_status == "low_confidence" for item in associations
            ),
            unavailable_count=sum(
                item.position_status == "unavailable" for item in associations
            ),
            objects_3d_path=config.objects_3d_path,
            tracks_3d_path=config.tracks_3d_path,
            trajectories_path=config.trajectories_path,
            annotations_path=config.annotations_path,
            warnings=warnings,
        )
    except (SceneAssociationError, OSError, ValueError) as exc:
        result = SceneAssociationResult(
            success=False,
            object_dir=Path(object_dir),
            reconstruction_dir=Path(reconstruction_dir),
            georeferenced_dir=Path(georeferenced_dir) if georeferenced_dir else None,
            output_dir=Path(output_dir),
            error=str(exc),
        )

    result.processing_time_seconds = time.monotonic() - started_at
    if result.track_count:
        result.average_association_time_seconds = result.processing_time_seconds / result.track_count
    if config is not None and output_workspace_prepared:
        write_metadata(config.metadata_path, result, config)
    return result
