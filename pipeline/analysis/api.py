"""Public Step 6 API for metric scene measurement and support evidence."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from pipeline.analysis.errors import AnalysisError
from pipeline.analysis.evidence import (
    build_quality_grid,
    calculate_evidence,
    calculate_segment_evidence,
    evidence_level,
)
from pipeline.analysis.inputs import SceneContext, load_scene_context
from pipeline.analysis.measurements import measure_distance
from pipeline.analysis.models import (
    AnalysisConfig,
    AnalysisResult,
    EvidenceConfig,
    MeasurementRequest,
    SceneMeasurementResult,
)
from pipeline.analysis.output import (
    prepare_output_directory,
    write_json,
    write_measurements,
    write_metadata,
)


def measure_scene_distance(
    scene: SceneContext,
    point_a,
    point_b,
    *,
    measurement_id: str = "measurement_1",
    unit: str = "m",
    evidence_config: EvidenceConfig | None = None,
) -> SceneMeasurementResult:
    """Measure two Step 3 points and attach conservative endpoint/segment evidence."""
    config = evidence_config or EvidenceConfig()
    distance = measure_distance(
        point_a,
        point_b,
        unit=unit,
        horizontal_and_vertical_meaningful=scene.has_meaningful_vertical_axis,
    )
    endpoint_a = calculate_evidence(distance.point_a, scene, config)
    endpoint_b = calculate_evidence(distance.point_b, scene, config)
    segment = calculate_segment_evidence(distance.point_a, distance.point_b, scene, config)
    score = min(endpoint_a.evidence_score, endpoint_b.evidence_score)
    if segment["available"] and segment["evidence_score"] is not None:
        score = min(score, float(segment["evidence_score"]))
    level = evidence_level(score, config)
    warnings: list[str] = []
    for label, endpoint in (("Point A", endpoint_a), ("Point B", endpoint_b)):
        if endpoint.evidence_level in {"LOW", "INSUFFICIENT"}:
            warnings.append(f"{label} lies in a poorly supported reconstructed region.")
        if endpoint.signals["dynamic_contamination"]["nearby_dynamic_marker_count"]:
            warnings.append(f"{label} is near dynamic-object marker evidence.")
    if not segment["available"]:
        warnings.append(str(segment["reason"]))
    if not scene.has_meaningful_vertical_axis:
        warnings.append(
            "The Step 3 coordinate system does not declare ENU axes, so horizontal and vertical values are unavailable."
        )
    if level == "INSUFFICIENT":
        warnings.append(
            "Measurement is not recommended: at least one required evidence component is insufficient."
        )
    return SceneMeasurementResult(
        measurement_id=str(measurement_id),
        measurement=distance,
        measurement_status=("INSUFFICIENT_EVIDENCE" if level == "INSUFFICIENT" else "ESTIMATED"),
        evidence_score=score,
        evidence_level=level,
        endpoint_a_evidence=endpoint_a,
        endpoint_b_evidence=endpoint_b,
        segment_evidence=segment,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def analyze_georeferenced_scene(
    scene_dir: str | Path,
    output_dir: str | Path,
    *,
    scene_objects_dir: str | Path | None = None,
    measurements: Iterable[MeasurementRequest] | None = None,
    evidence_config: EvidenceConfig | None = None,
    overwrite: bool = False,
) -> AnalysisResult:
    """Build an evidence grid and optional reliable/unreliable measurements.

    Step 6 requires Step 3's published metre-valued transform and point cloud.
    It does not estimate a new scale, alter the point cloud, or turn evidence
    into an accuracy claim.
    """
    started_at = time.monotonic()
    config: AnalysisConfig | None = None
    output_prepared = False
    result: AnalysisResult | None = None
    grid_warnings: list[str] = []
    try:
        config = AnalysisConfig(
            scene_dir=Path(scene_dir),
            output_dir=Path(output_dir),
            scene_objects_dir=Path(scene_objects_dir) if scene_objects_dir else None,
            evidence=evidence_config or EvidenceConfig(),
            overwrite=overwrite,
        )
        scene = load_scene_context(
            config.scene_dir, config.scene_objects_dir, config.evidence
        )
        requests = list(measurements or [])
        request_ids = [str(item.measurement_id).strip() for item in requests]
        if any(not identifier for identifier in request_ids) or len(set(request_ids)) != len(request_ids):
            raise ValueError("Measurement IDs must be non-empty and unique")
        prepare_output_directory(config)
        output_prepared = True

        evidence_started_at = time.monotonic()
        quality_grid, grid_warnings = build_quality_grid(scene, config.evidence)
        measurement_results = [
            measure_scene_distance(
                scene,
                request.point_a,
                request.point_b,
                measurement_id=request.measurement_id,
                unit=request.unit,
                evidence_config=config.evidence,
            )
            for request in requests
        ]
        evidence_elapsed = time.monotonic() - evidence_started_at
        write_json(config.evidence_map_path, quality_grid)
        write_measurements(
            config.measurements_path, measurement_results, scene.target_coordinate_system
        )
        result = AnalysisResult(
            success=True,
            scene_dir=config.scene_dir,
            scene_objects_dir=config.scene_objects_dir,
            output_dir=config.output_dir,
            point_count=len(scene.points),
            camera_count=len(scene.camera_centres),
            dynamic_marker_count=len(scene.dynamic_marker_positions),
            quality_region_count=len(quality_grid["regions"]),
            measurement_count=len(measurement_results),
            recommended_measurement_count=sum(
                item.measurement_status == "ESTIMATED" for item in measurement_results
            ),
            insufficient_measurement_count=sum(
                item.measurement_status == "INSUFFICIENT_EVIDENCE"
                for item in measurement_results
            ),
            evidence_processing_time_seconds=evidence_elapsed,
            measurements_path=config.measurements_path,
            evidence_map_path=config.evidence_map_path,
            warnings=list(scene.warnings) + grid_warnings,
        )
    except (AnalysisError, OSError, ValueError) as exc:
        result = AnalysisResult(
            success=False,
            scene_dir=Path(scene_dir),
            scene_objects_dir=Path(scene_objects_dir) if scene_objects_dir else None,
            output_dir=Path(output_dir),
            error=str(exc),
        )

    result.processing_time_seconds = time.monotonic() - started_at
    if config is not None and output_prepared:
        write_metadata(
            config.metadata_path,
            result,
            config,
            coordinate_system=scene.target_coordinate_system,
            has_meaningful_vertical_axis=scene.has_meaningful_vertical_axis,
            quality_grid_warnings=grid_warnings,
        )
    return result
