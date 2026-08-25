"""Typed data models used by the Step 3 georeferencing pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True)
class GPSObservation:
    """One valid geographic observation read from external flight metadata."""

    observation_id: str
    latitude: float
    longitude: float
    altitude: float
    timestamp_seconds: Optional[float] = None
    frame_index: Optional[int] = None
    image_name: Optional[str] = None


@dataclass
class GPSDataset:
    """Parsed GPS observations plus source metadata and non-fatal warnings."""

    observations: list[GPSObservation]
    source_coordinate_system: str
    altitude_reference: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReconstructionData:
    """Artifacts loaded from a completed Step 2 reconstruction directory."""

    poses: list[CameraPose]
    point_cloud_path: Path
    source_scale_is_metric: bool
    source_scale_description: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CameraPose:
    """A Step 2 camera center in its native reconstruction coordinate system."""

    image_id: int
    image_name: str
    camera_center: np.ndarray
    timestamp_seconds: Optional[float] = None


@dataclass(frozen=True)
class LocalENUReference:
    """WGS-84 geographic origin used to define a local East-North-Up frame."""

    latitude: float
    longitude: float
    altitude: float

    def to_dict(self) -> dict[str, float]:
        return {
            "latitude_degrees": self.latitude,
            "longitude_degrees": self.longitude,
            "altitude_metres": self.altitude,
        }


@dataclass(frozen=True)
class Correspondence:
    """A reconstructed camera center paired with a local-ENU GPS position."""

    pose: CameraPose
    target_enu: np.ndarray
    gps_observation_ids: tuple[str, ...]
    method: str


@dataclass(frozen=True)
class SimilarityTransform:
    """Transform from reconstruction coordinates to local ENU metres.

    ``target = scale * rotation @ source + translation``.
    """

    scale: float
    rotation: np.ndarray
    translation: np.ndarray

    def apply(self, points: np.ndarray) -> np.ndarray:
        """Transform one ``(3,)`` point or an ``(N, 3)`` point array."""
        array = np.asarray(points, dtype=float)
        if array.shape == (3,):
            return self.scale * (self.rotation @ array) + self.translation
        if array.ndim != 2 or array.shape[1] != 3:
            raise ValueError("points must have shape (3,) or (N, 3)")
        return self.scale * (array @ self.rotation.T) + self.translation

    def matrix4x4(self) -> np.ndarray:
        """Return the homogeneous matrix representing this source-to-target map."""
        matrix = np.eye(4, dtype=float)
        matrix[:3, :3] = self.scale * self.rotation
        matrix[:3, 3] = self.translation
        return matrix

    def to_dict(self) -> dict[str, Any]:
        return {
            "equation": "target_enu_m = scale * rotation * source_colmap + translation_m",
            "scale": float(self.scale),
            "rotation_matrix": self.rotation.tolist(),
            "translation_metres": self.translation.tolist(),
            "matrix_4x4": self.matrix4x4().tolist(),
        }


@dataclass
class AlignmentEstimate:
    """A transform plus residuals measured in the target ENU coordinate frame."""

    transform: SimilarityTransform
    residuals_metres: np.ndarray
    inlier_mask: np.ndarray
    method: str

    @property
    def inlier_count(self) -> int:
        return int(np.count_nonzero(self.inlier_mask))

    @property
    def outlier_count(self) -> int:
        return int(self.inlier_mask.size - self.inlier_count)


@dataclass
class GeoreferencingConfig:
    """Tunable but conservative controls for the Step 3 pipeline."""

    reconstruction_dir: Path
    gps_metadata_path: Path
    output_dir: Path
    point_cloud_path: Optional[Path] = None
    timestamp_tolerance_seconds: float = 1.0
    ransac_threshold_metres: float = 10.0
    ransac_iterations: int = 300
    source_scale_mode: str = "auto"
    overwrite: bool = False

    def __post_init__(self) -> None:
        self.reconstruction_dir = Path(self.reconstruction_dir)
        self.gps_metadata_path = Path(self.gps_metadata_path)
        self.output_dir = Path(self.output_dir)
        if self.point_cloud_path is not None:
            self.point_cloud_path = Path(self.point_cloud_path)
        if self.timestamp_tolerance_seconds <= 0:
            raise ValueError("timestamp_tolerance_seconds must be > 0")
        if self.ransac_threshold_metres <= 0:
            raise ValueError("ransac_threshold_metres must be > 0")
        if self.ransac_iterations <= 0:
            raise ValueError("ransac_iterations must be > 0")
        if self.source_scale_mode not in {"auto", "arbitrary", "metric"}:
            raise ValueError(
                "source_scale_mode must be 'auto', 'arbitrary', or 'metric'"
            )

    @property
    def georeferenced_point_cloud_path(self) -> Path:
        return self.output_dir / "point_cloud_georef.ply"

    @property
    def camera_trajectory_path(self) -> Path:
        return self.output_dir / "camera_trajectory_georef.csv"

    @property
    def transform_path(self) -> Path:
        return self.output_dir / "transform.json"

    @property
    def validation_path(self) -> Path:
        return self.output_dir / "validation.json"

    @property
    def correspondences_path(self) -> Path:
        return self.output_dir / "correspondences.json"

    @property
    def metadata_path(self) -> Path:
        return self.output_dir / "georef_metadata.json"


@dataclass
class GeoreferencingResult:
    """Structured outcome of one georeferencing attempt."""

    success: bool
    reconstruction_dir: Path
    gps_metadata_path: Path
    output_dir: Path
    gps_observation_count: int = 0
    matched_pose_count: int = 0
    inlier_count: int = 0
    alignment_method: Optional[str] = None
    estimated_scale: Optional[float] = None
    trajectory_rmse_metres: Optional[float] = None
    trajectory_median_residual_metres: Optional[float] = None
    trajectory_max_residual_metres: Optional[float] = None
    processing_time_seconds: float = 0.0
    point_cloud_path: Optional[Path] = None
    camera_trajectory_path: Optional[Path] = None
    transform_path: Optional[Path] = None
    validation_path: Optional[Path] = None
    correspondences_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def path_value(value: Optional[Path]) -> Optional[str]:
            return str(value) if value is not None else None

        return {
            "success": self.success,
            "reconstruction_dir": str(self.reconstruction_dir),
            "gps_metadata_path": str(self.gps_metadata_path),
            "output_dir": str(self.output_dir),
            "gps_observation_count": self.gps_observation_count,
            "matched_pose_count": self.matched_pose_count,
            "inlier_count": self.inlier_count,
            "alignment_method": self.alignment_method,
            "estimated_scale": self.estimated_scale,
            "trajectory_alignment_residuals_metres": {
                "rmse": self.trajectory_rmse_metres,
                "median": self.trajectory_median_residual_metres,
                "maximum": self.trajectory_max_residual_metres,
            },
            "processing_time_seconds": round(self.processing_time_seconds, 4),
            "outputs": {
                "point_cloud": path_value(self.point_cloud_path),
                "camera_trajectory": path_value(self.camera_trajectory_path),
                "transform": path_value(self.transform_path),
                "validation": path_value(self.validation_path),
                "correspondences": path_value(self.correspondences_path),
            },
            "error": self.error,
            "warnings": self.warnings,
        }
