"""Safe writers for isolated Step 6 analysis artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pipeline.analysis.errors import AnalysisOutputError
from pipeline.analysis.models import AnalysisConfig, AnalysisResult, SceneMeasurementResult


def prepare_output_directory(config: AnalysisConfig) -> None:
    """Create Step 6 output without changing its Step 3/5 inputs."""
    output = config.output_dir.resolve()
    inputs = [config.scene_dir.resolve()]
    if config.scene_objects_dir is not None:
        inputs.append(config.scene_objects_dir.resolve())
    if any(output == item or output in item.parents for item in inputs):
        raise AnalysisOutputError(
            "Analysis output must not be an input directory or one of its parents: "
            f"{config.output_dir}"
        )
    if config.output_dir.exists() and any(config.output_dir.iterdir()):
        if not config.overwrite:
            raise AnalysisOutputError(
                f"Analysis output directory is not empty: {config.output_dir}. "
                "Use a new directory or set overwrite=True."
            )
        shutil.rmtree(config.output_dir)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.evidence_map_path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_measurements(
    path: Path,
    measurements: list[SceneMeasurementResult],
    coordinate_system: str,
) -> None:
    """Write values and reliability evidence together so they cannot be separated."""
    write_json(
        path,
        {
            "schema_version": 1,
            "description": (
                "Point-to-point metric measurements paired with Step 6 evidence. "
                "Evidence is reconstruction support, not measured positional accuracy."
            ),
            "coordinate_system": coordinate_system,
            "measurements": [item.to_dict() for item in measurements],
        },
    )


def write_metadata(
    path: Path,
    result: AnalysisResult,
    config: AnalysisConfig,
    *,
    coordinate_system: str,
    has_meaningful_vertical_axis: bool,
    quality_grid_warnings: list[str],
) -> None:
    """Record transparent score configuration and unavailable evidence signals."""
    result.metadata_path = path
    payload = result.to_dict()
    payload.update(
        {
            "schema_version": 1,
            "coordinate_system": coordinate_system,
            "vertical_measurement": {
                "available": has_meaningful_vertical_axis,
                "source": (
                    "Step 3 Local ENU Up coordinate"
                    if has_meaningful_vertical_axis
                    else "unavailable: Step 3 target does not declare ENU axes"
                ),
                "limitation": (
                    "The Up coordinate is only as reliable as Step 3's reconstruction-to-GPS "
                    "alignment and source altitude reference; it is not a survey-grade height claim."
                ),
            },
            "evidence_methodology": {
                "score_formula": (
                    "weighted_sum(reconstruction_density, nearby_camera_support, "
                    "nearby_camera_view_diversity) * "
                    "(1 - dynamic_contamination_penalty * normalized_dynamic_contamination)"
                ),
                "configuration": config.evidence.to_dict(),
                "direct_observation_status": (
                    "UNKNOWN: current Step 2/3 artifacts do not expose a per-point "
                    "visibility, feature-track, reprojection, or occlusion record."
                ),
                "signals_used": [
                    "local georeferenced PLY vertex density",
                    "nearby Step 3 camera-centre count (candidate support only)",
                    "nearby camera-centre angular diversity (candidate support only)",
                    "Step 5 dynamic-marker proximity as a bounded penalty",
                ],
                "signals_not_available": [
                    "per-point source-frame visibility",
                    "feature-match density",
                    "per-point reprojection error",
                    "depth consistency",
                    "occlusion state",
                    "supporting-frame image quality",
                ],
                "limitations": [
                    "Point density is only one reconstruction-support signal and does not prove accuracy.",
                    "Camera proximity and angular spread do not prove a camera observed the queried surface.",
                    "Evidence scores are configurable heuristics, not calibrated uncertainty or accuracy percentages.",
                    "Step 3 alignment residuals and any external ground-truth measurement error remain separate metrics.",
                ],
            },
            "quality_grid_warnings": quality_grid_warnings,
        }
    )
    write_json(path, payload)
