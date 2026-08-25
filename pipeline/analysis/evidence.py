"""Transparent local reconstruction-support calculations for Step 6."""

from __future__ import annotations

import itertools
import math
from typing import Any

import numpy as np

from pipeline.analysis.errors import MeasurementInputError
from pipeline.analysis.inputs import SceneContext
from pipeline.analysis.models import EvidenceConfig, EvidenceResult


def _finite_point(point: np.ndarray) -> np.ndarray:
    value = np.asarray(point, dtype=float)
    if value.shape != (3,) or not np.all(np.isfinite(value)):
        raise MeasurementInputError("Evidence point must contain three finite coordinates")
    return value


def evidence_level(score: float, config: EvidenceConfig) -> str:
    """Map an explicit configurable score threshold to an interpretable level."""
    if score >= config.high_threshold:
        return "HIGH"
    if score >= config.medium_threshold:
        return "MEDIUM"
    if score >= config.low_threshold:
        return "LOW"
    return "INSUFFICIENT"


def _camera_evidence(
    point: np.ndarray,
    scene: SceneContext,
    config: EvidenceConfig,
) -> tuple[int, float, float]:
    """Return nearby candidate camera count, largest angle, and normalised diversity.

    Step 3 exposes camera centres but not per-point visibility or view direction.
    These are therefore candidate-viewpoint signals, never an assertion that a
    camera actually observed the queried surface.
    """
    if not len(scene.camera_centres):
        return 0, 0.0, 0.0
    offsets = scene.camera_centres - point
    distances = np.linalg.norm(offsets, axis=1)
    usable = offsets[(distances <= config.camera_support_radius_metres) & (distances > 1e-12)]
    if len(usable) < 2:
        return int(len(usable)), 0.0, 0.0
    directions = usable / np.linalg.norm(usable, axis=1)[:, np.newaxis]
    angles = [
        math.degrees(math.acos(float(np.clip(left @ right, -1.0, 1.0))))
        for left, right in itertools.combinations(directions, 2)
    ]
    maximum_angle = max(angles, default=0.0)
    return (
        int(len(usable)),
        maximum_angle,
        min(1.0, maximum_angle / config.view_diversity_target_degrees),
    )


def _dynamic_contamination(
    point: np.ndarray,
    scene: SceneContext,
    config: EvidenceConfig,
) -> tuple[int, float]:
    if not len(scene.dynamic_marker_positions):
        return 0, 0.0
    distances = np.linalg.norm(scene.dynamic_marker_positions - point, axis=1)
    count = int(
        np.count_nonzero(distances <= config.dynamic_contamination_radius_metres)
    )
    return count, min(1.0, count / config.dynamic_contamination_target_count)


def calculate_evidence(
    point: np.ndarray,
    scene: SceneContext,
    config: EvidenceConfig | None = None,
) -> EvidenceResult:
    """Evaluate only presently observable local scene-support signals.

    The score is a configurable weighted sum of normalised local PLY density,
    nearby camera-centre support, and nearby camera-centre angular diversity.
    A bounded multiplier then lowers the score near Step 5 dynamic markers.
    No per-point frame visibility, feature-match count, reprojection error,
    image sharpness, depth consistency, or occlusion is inferred because the
    existing artifacts do not preserve that evidence.
    """
    selected = config or EvidenceConfig()
    location = _finite_point(point)
    density_count = scene.point_index.count_within(
        location, selected.density_radius_metres
    )
    density_score = min(1.0, density_count / selected.density_target_points)
    camera_count, maximum_angle, diversity_score = _camera_evidence(
        location, scene, selected
    )
    camera_score = min(1.0, camera_count / selected.camera_target_count)
    dynamic_count, contamination_score = _dynamic_contamination(location, scene, selected)
    weights = selected.normalized_weights
    base_score = (
        weights["reconstruction_density"] * density_score
        + weights["nearby_camera_support"] * camera_score
        + weights["nearby_camera_view_diversity"] * diversity_score
    )
    score = max(0.0, min(1.0, base_score * (1.0 - selected.dynamic_contamination_penalty * contamination_score)))
    warnings: list[str] = []
    if density_count == 0:
        warnings.append(
            "No georeferenced point-cloud vertices occur within the configured local density radius."
        )
    if camera_count == 0:
        warnings.append(
            "No Step 3 camera centres occur within the configured camera-support radius."
        )
    if dynamic_count:
        warnings.append(
            "This region is near dynamic-object markers; evidence was reduced, not invalidated."
        )
    return EvidenceResult(
        point=location,
        evidence_score=score,
        evidence_level=evidence_level(score, selected),
        direct_observation_status="UNKNOWN",
        signals={
            "reconstruction_density": {
                "point_count_within_radius": density_count,
                "radius_metres": selected.density_radius_metres,
                "target_point_count": selected.density_target_points,
                "normalized_value": density_score,
            },
            "nearby_camera_support": {
                "candidate_camera_count": camera_count,
                "radius_metres": selected.camera_support_radius_metres,
                "target_camera_count": selected.camera_target_count,
                "normalized_value": camera_score,
                "visibility_verified": False,
            },
            "nearby_camera_view_diversity": {
                "maximum_candidate_view_angle_degrees": maximum_angle,
                "target_angle_degrees": selected.view_diversity_target_degrees,
                "normalized_value": diversity_score,
                "visibility_verified": False,
            },
            "dynamic_contamination": {
                "nearby_dynamic_marker_count": dynamic_count,
                "radius_metres": selected.dynamic_contamination_radius_metres,
                "normalized_value": contamination_score,
                "score_multiplier": 1.0
                - selected.dynamic_contamination_penalty * contamination_score,
            },
        },
        warnings=tuple(warnings),
    )


def calculate_segment_evidence(
    point_a: np.ndarray,
    point_b: np.ndarray,
    scene: SceneContext,
    config: EvidenceConfig,
) -> dict[str, Any]:
    """Assess intermediate support only when the segment crosses local geometry.

    A distance between separately reconstructed objects need not have a PLY
    surface in the air between them. In that case endpoint evidence remains
    valid, but the result states that no between-endpoint geometry was used.
    """
    interior_points = np.linspace(point_a, point_b, config.segment_samples + 2)[1:-1]
    samples = [calculate_evidence(point, scene, config) for point in interior_points]
    supported = [
        sample
        for sample in samples
        if sample.signals["reconstruction_density"]["point_count_within_radius"] > 0
    ]
    supported_fraction = len(supported) / len(samples) if samples else 0.0
    available = supported_fraction >= config.minimum_segment_supported_fraction
    return {
        "available": available,
        "sample_count": len(samples),
        "supported_sample_count": len(supported),
        "supported_fraction": supported_fraction,
        "minimum_supported_fraction": config.minimum_segment_supported_fraction,
        "evidence_score": min((item.evidence_score for item in supported), default=None)
        if available
        else None,
        "evidence_level": (
            evidence_level(min(item.evidence_score for item in supported), config)
            if available
            else "UNAVAILABLE"
        ),
        "reason": (
            None
            if available
            else "Intermediate geometry was not sufficiently represented by local point-cloud support; endpoint evidence only was used."
        ),
    }


def build_quality_grid(
    scene: SceneContext,
    config: EvidenceConfig,
) -> tuple[dict[str, Any], list[str]]:
    """Create a compact voxel-region map, not a duplicate point cloud."""
    cell_size = config.quality_grid_cell_size_metres
    while True:
        cells = np.floor(scene.points / cell_size).astype(np.int64)
        unique_cells, counts = np.unique(cells, axis=0, return_counts=True)
        if len(unique_cells) <= config.max_quality_regions:
            break
        cell_size *= 2.0
    warnings: list[str] = []
    if cell_size != config.quality_grid_cell_size_metres:
        warnings.append(
            "Quality-grid cell size was increased to bound the number of output regions; "
            f"effective cell size is {cell_size:g} metres."
        )
    regions = []
    for cell, count in zip(unique_cells, counts):
        centre = (cell.astype(float) + 0.5) * cell_size
        evidence = calculate_evidence(centre, scene, config)
        regions.append(
            {
                "grid_cell": [int(value) for value in cell],
                "centre": centre.tolist(),
                "cell_size_metres": cell_size,
                "source_point_count_in_cell": int(count),
                "evidence_score": evidence.evidence_score,
                "evidence_level": evidence.evidence_level,
                "direct_observation_status": evidence.direct_observation_status,
                "signals": evidence.signals,
            }
        )
    return (
        {
            "schema_version": 1,
            "description": (
                "Voxel-region evidence summary referencing the Step 3 PLY; this file "
                "does not copy source point-cloud vertices. Per-point direct visibility "
                "is unavailable in the current pipeline artifacts."
            ),
            "source_point_cloud": str(scene.point_cloud_path),
            "coordinate_system": scene.target_coordinate_system,
            "requested_cell_size_metres": config.quality_grid_cell_size_metres,
            "effective_cell_size_metres": cell_size,
            "regions": regions,
        },
        warnings,
    )
