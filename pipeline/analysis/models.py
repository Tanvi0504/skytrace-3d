"""Typed contracts for Step 6 measurement and evidence analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True)
class EvidenceConfig:
    """Explicit, configurable MVP evidence normalisation and thresholds.

    These defaults are engineering heuristics, not calibrated accuracy or
    uncertainty parameters. They exist to make the first evidence policy
    inspectable and adjustable as a labelled validation dataset becomes
    available.
    """

    density_radius_metres: float = 3.0
    density_target_points: int = 20
    camera_support_radius_metres: float = 80.0
    camera_target_count: int = 4
    view_diversity_target_degrees: float = 30.0
    density_weight: float = 0.50
    nearby_camera_weight: float = 0.25
    view_diversity_weight: float = 0.25
    dynamic_contamination_radius_metres: float = 3.0
    dynamic_contamination_target_count: int = 1
    dynamic_contamination_penalty: float = 0.25
    high_threshold: float = 0.75
    medium_threshold: float = 0.50
    low_threshold: float = 0.25
    quality_grid_cell_size_metres: float = 5.0
    max_quality_regions: int = 10_000
    segment_samples: int = 5
    minimum_segment_supported_fraction: float = 0.50

    def __post_init__(self) -> None:
        positive_values = {
            "density_radius_metres": self.density_radius_metres,
            "density_target_points": self.density_target_points,
            "camera_support_radius_metres": self.camera_support_radius_metres,
            "camera_target_count": self.camera_target_count,
            "view_diversity_target_degrees": self.view_diversity_target_degrees,
            "dynamic_contamination_radius_metres": self.dynamic_contamination_radius_metres,
            "dynamic_contamination_target_count": self.dynamic_contamination_target_count,
            "quality_grid_cell_size_metres": self.quality_grid_cell_size_metres,
            "max_quality_regions": self.max_quality_regions,
            "segment_samples": self.segment_samples,
        }
        if any(value <= 0 for value in positive_values.values()):
            names = ", ".join(name for name, value in positive_values.items() if value <= 0)
            raise ValueError(f"Evidence configuration values must be positive: {names}")
        weights = (
            self.density_weight,
            self.nearby_camera_weight,
            self.view_diversity_weight,
        )
        if any(value < 0.0 for value in weights) or sum(weights) <= 0.0:
            raise ValueError("Evidence signal weights must be non-negative with a positive sum")
        if not 0.0 <= self.dynamic_contamination_penalty <= 1.0:
            raise ValueError("dynamic_contamination_penalty must be within [0, 1]")
        if not 0.0 <= self.low_threshold <= self.medium_threshold <= self.high_threshold <= 1.0:
            raise ValueError("Evidence thresholds must satisfy 0 <= low <= medium <= high <= 1")
        if not 0.0 < self.minimum_segment_supported_fraction <= 1.0:
            raise ValueError("minimum_segment_supported_fraction must be within (0, 1]")

    @property
    def normalized_weights(self) -> dict[str, float]:
        total = self.density_weight + self.nearby_camera_weight + self.view_diversity_weight
        return {
            "reconstruction_density": self.density_weight / total,
            "nearby_camera_support": self.nearby_camera_weight / total,
            "nearby_camera_view_diversity": self.view_diversity_weight / total,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalization": {
                "density_radius_metres": self.density_radius_metres,
                "density_target_points": self.density_target_points,
                "camera_support_radius_metres": self.camera_support_radius_metres,
                "camera_target_count": self.camera_target_count,
                "view_diversity_target_degrees": self.view_diversity_target_degrees,
                "dynamic_contamination_radius_metres": self.dynamic_contamination_radius_metres,
                "dynamic_contamination_target_count": self.dynamic_contamination_target_count,
            },
            "weights": self.normalized_weights,
            "dynamic_contamination_penalty": self.dynamic_contamination_penalty,
            "thresholds": {
                "high": self.high_threshold,
                "medium": self.medium_threshold,
                "low": self.low_threshold,
            },
            "quality_grid": {
                "requested_cell_size_metres": self.quality_grid_cell_size_metres,
                "max_regions": self.max_quality_regions,
            },
            "segment_support": {
                "samples": self.segment_samples,
                "minimum_supported_fraction": self.minimum_segment_supported_fraction,
            },
        }


@dataclass(frozen=True)
class MeasurementRequest:
    """A caller-supplied point-to-point measurement in Step 3 coordinates."""

    measurement_id: str
    point_a: np.ndarray
    point_b: np.ndarray
    unit: str = "m"


@dataclass(frozen=True)
class DistanceMeasurement:
    """Mathematical distances retained internally in metres."""

    point_a: np.ndarray
    point_b: np.ndarray
    distance_3d_metres: float
    horizontal_distance_metres: Optional[float]
    vertical_difference_metres: Optional[float]
    unit: str

    def to_dict(self) -> dict[str, Any]:
        from pipeline.analysis.measurements import convert_distance

        return {
            "point_a": self.point_a.tolist(),
            "point_b": self.point_b.tolist(),
            "distance_3d": convert_distance(self.distance_3d_metres, self.unit),
            "horizontal_distance": (
                convert_distance(self.horizontal_distance_metres, self.unit)
                if self.horizontal_distance_metres is not None
                else None
            ),
            "vertical_difference": (
                convert_distance(self.vertical_difference_metres, self.unit)
                if self.vertical_difference_metres is not None
                else None
            ),
            "unit": self.unit,
            "distance_3d_metres": self.distance_3d_metres,
            "horizontal_distance_metres": self.horizontal_distance_metres,
            "vertical_difference_metres": self.vertical_difference_metres,
        }


@dataclass(frozen=True)
class EvidenceResult:
    """Local reconstruction support indicators for one ENU coordinate."""

    point: np.ndarray
    evidence_score: float
    evidence_level: str
    direct_observation_status: str
    signals: dict[str, Any]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "point": self.point.tolist(),
            "evidence_score": self.evidence_score,
            "evidence_level": self.evidence_level,
            "direct_observation_status": self.direct_observation_status,
            "signals": self.signals,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class SceneMeasurementResult:
    """A measurement paired with endpoint and optional segment evidence."""

    measurement_id: str
    measurement: DistanceMeasurement
    measurement_status: str
    evidence_score: float
    evidence_level: str
    endpoint_a_evidence: EvidenceResult
    endpoint_b_evidence: EvidenceResult
    segment_evidence: Optional[dict[str, Any]]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = self.measurement.to_dict()
        payload.update(
            {
                "measurement_id": self.measurement_id,
                "measurement_type": "point_to_point",
                "measurement_status": self.measurement_status,
                "evidence_score": self.evidence_score,
                "evidence_level": self.evidence_level,
                "endpoint_evidence": {
                    "point_a": self.endpoint_a_evidence.to_dict(),
                    "point_b": self.endpoint_b_evidence.to_dict(),
                },
                "segment_evidence": self.segment_evidence,
                "warnings": list(self.warnings),
            }
        )
        return payload


@dataclass
class AnalysisConfig:
    """Validated paths and controls for one isolated Step 6 run."""

    scene_dir: Path
    output_dir: Path
    scene_objects_dir: Optional[Path] = None
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    overwrite: bool = False

    def __post_init__(self) -> None:
        self.scene_dir = Path(self.scene_dir)
        self.output_dir = Path(self.output_dir)
        if self.scene_objects_dir is not None:
            self.scene_objects_dir = Path(self.scene_objects_dir)

    @property
    def measurements_path(self) -> Path:
        return self.output_dir / "measurements.json"

    @property
    def evidence_map_path(self) -> Path:
        return self.output_dir / "evidence_map" / "quality_grid.json"

    @property
    def metadata_path(self) -> Path:
        return self.output_dir / "quality_metadata.json"


@dataclass
class AnalysisResult:
    """Structured outcome of a Step 6 scene analysis run."""

    success: bool
    scene_dir: Path
    output_dir: Path
    scene_objects_dir: Optional[Path] = None
    point_count: int = 0
    camera_count: int = 0
    dynamic_marker_count: int = 0
    quality_region_count: int = 0
    measurement_count: int = 0
    recommended_measurement_count: int = 0
    insufficient_measurement_count: int = 0
    processing_time_seconds: float = 0.0
    evidence_processing_time_seconds: float = 0.0
    measurements_path: Optional[Path] = None
    evidence_map_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def path_value(path: Optional[Path]) -> Optional[str]:
            return str(path) if path is not None else None

        return {
            "success": self.success,
            "scene_dir": str(self.scene_dir),
            "scene_objects_dir": (
                str(self.scene_objects_dir) if self.scene_objects_dir is not None else None
            ),
            "output_dir": str(self.output_dir),
            "point_count": self.point_count,
            "camera_count": self.camera_count,
            "dynamic_marker_count": self.dynamic_marker_count,
            "quality_region_count": self.quality_region_count,
            "measurement_count": self.measurement_count,
            "recommended_measurement_count": self.recommended_measurement_count,
            "insufficient_measurement_count": self.insufficient_measurement_count,
            "processing_time_seconds": round(self.processing_time_seconds, 4),
            "evidence_processing_time_seconds": round(
                self.evidence_processing_time_seconds, 4
            ),
            "outputs": {
                "measurements": path_value(self.measurements_path),
                "evidence_map": path_value(self.evidence_map_path),
            },
            "error": self.error,
            "warnings": self.warnings,
        }
