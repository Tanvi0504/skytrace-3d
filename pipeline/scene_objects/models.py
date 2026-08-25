"""Typed contracts for conservative 2D-object to 3D-scene association."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True)
class ObjectObservation:
    """One validated Step 4 2D observation belonging to a tracker ID."""

    detection_id: str
    track_id: int
    class_name: str
    confidence: float
    frame_filename: str
    frame_index: Optional[int]
    timestamp_seconds: Optional[float]
    bbox_xyxy: tuple[float, float, float, float]
    is_dynamic_candidate: bool

    @property
    def anchor_pixel(self) -> tuple[float, float]:
        """Use the box bottom centre as a cautious ground-contact proxy.

        This is more appropriate than the box centre for people and ground
        vehicles, but remains a 2D proxy rather than a proved contact point.
        """
        x1, _, x2, y2 = self.bbox_xyxy
        return ((x1 + x2) / 2.0, y2)


@dataclass(frozen=True)
class CameraIntrinsics:
    """A COLMAP camera definition in its declared pixel coordinate system."""

    camera_id: int
    model: str
    width: int
    height: int
    parameters: tuple[float, ...]


@dataclass(frozen=True)
class ReconstructionCameraPose:
    """COLMAP world-to-camera pose exported by Step 2."""

    image_id: int
    image_name: str
    camera_id: int
    rotation_world_to_camera: np.ndarray
    translation_world_to_camera: np.ndarray
    camera_center_world: np.ndarray


@dataclass(frozen=True)
class WorldRay:
    """A calibrated viewing ray in Step 2 reconstruction coordinates."""

    origin: np.ndarray
    direction: np.ndarray
    observation: ObjectObservation
    camera: ReconstructionCameraPose


@dataclass(frozen=True)
class TriangulationEstimate:
    """Least-squares point closest to a set of non-parallel calibrated rays."""

    position: np.ndarray
    ray_residuals: np.ndarray
    ray_depths: np.ndarray
    condition_number: float
    pairwise_ray_angles_degrees: tuple[float, ...]
    median_camera_baseline: float

    @property
    def ray_rmse(self) -> float:
        return float(np.sqrt(np.mean(self.ray_residuals**2)))

    @property
    def median_ray_angle_degrees(self) -> float:
        return float(np.median(self.pairwise_ray_angles_degrees))


@dataclass(frozen=True)
class GeoreferenceTransform:
    """Step 3 source-to-ENU transform and optional WGS-84 ENU origin."""

    matrix_4x4: np.ndarray
    target_coordinate_system: str
    latitude_degrees: Optional[float]
    longitude_degrees: Optional[float]
    altitude_metres: Optional[float]


@dataclass
class SceneAssociationConfig:
    """Controls for transparent numerical stability and low-evidence handling."""

    object_dir: Path
    reconstruction_dir: Path
    output_dir: Path
    georeferenced_dir: Optional[Path] = None
    minimum_ray_angle_degrees: float = 1.0
    max_normalized_ray_residual: float = 0.25
    max_condition_number: float = 1e8
    overwrite: bool = False

    def __post_init__(self) -> None:
        self.object_dir = Path(self.object_dir)
        self.reconstruction_dir = Path(self.reconstruction_dir)
        self.output_dir = Path(self.output_dir)
        if self.georeferenced_dir is not None:
            self.georeferenced_dir = Path(self.georeferenced_dir)
        if not 0.0 < self.minimum_ray_angle_degrees < 180.0:
            raise ValueError("minimum_ray_angle_degrees must be within (0, 180)")
        if self.max_normalized_ray_residual <= 0.0:
            raise ValueError("max_normalized_ray_residual must be > 0")
        if self.max_condition_number <= 1.0:
            raise ValueError("max_condition_number must be > 1")

    @property
    def objects_3d_path(self) -> Path:
        return self.output_dir / "objects_3d.json"

    @property
    def tracks_3d_path(self) -> Path:
        return self.output_dir / "object_tracks_3d.json"

    @property
    def trajectories_path(self) -> Path:
        return self.output_dir / "object_trajectories.json"

    @property
    def annotations_path(self) -> Path:
        return self.output_dir / "scene_annotations.json"

    @property
    def metadata_path(self) -> Path:
        return self.output_dir / "association_metadata.json"


@dataclass
class SceneObjectAssociation:
    """Per-track output, including unavailable outcomes without fabricated points."""

    object_id: str
    track_id: int
    class_name: str
    observation_count: int
    usable_observation_count: int
    first_frame_index: Optional[int]
    last_frame_index: Optional[int]
    minimum_detection_confidence: float
    mean_detection_confidence: float
    median_detection_confidence: float
    maximum_detection_confidence: float
    class_consistency: float
    is_dynamic_candidate: bool
    position_status: str
    position_method: Optional[str] = None
    source_position: Optional[np.ndarray] = None
    world_position: Optional[np.ndarray] = None
    coordinate_system: Optional[str] = None
    world_coordinate_status: str = "unavailable"
    latitude_degrees: Optional[float] = None
    longitude_degrees: Optional[float] = None
    altitude_metres: Optional[float] = None
    evidence_score: Optional[float] = None
    evidence_components: dict[str, float] = field(default_factory=dict)
    ray_rmse_source_units: Optional[float] = None
    normalized_ray_residual: Optional[float] = None
    median_ray_angle_degrees: Optional[float] = None
    condition_number: Optional[float] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "track_id": self.track_id,
            "class": self.class_name,
            "observation_count": self.observation_count,
            "usable_observation_count": self.usable_observation_count,
            "first_frame_index": self.first_frame_index,
            "last_frame_index": self.last_frame_index,
            "minimum_detection_confidence": self.minimum_detection_confidence,
            "mean_detection_confidence": self.mean_detection_confidence,
            "median_detection_confidence": self.median_detection_confidence,
            "maximum_detection_confidence": self.maximum_detection_confidence,
            "class_consistency": self.class_consistency,
            "is_dynamic_candidate": self.is_dynamic_candidate,
            "position_status": self.position_status,
            "position_method": self.position_method,
            "source_position_reconstruction": (
                self.source_position.tolist() if self.source_position is not None else None
            ),
            "world_position": (
                self.world_position.tolist() if self.world_position is not None else None
            ),
            "coordinate_system": self.coordinate_system,
            "world_coordinate_status": self.world_coordinate_status,
            "latitude_degrees": self.latitude_degrees,
            "longitude_degrees": self.longitude_degrees,
            "altitude_metres": self.altitude_metres,
            "evidence_score": self.evidence_score,
            "evidence_components": self.evidence_components,
            "ray_intersection_rmse_source_units": self.ray_rmse_source_units,
            "normalized_ray_residual": self.normalized_ray_residual,
            "median_ray_angle_degrees": self.median_ray_angle_degrees,
            "triangulation_condition_number": self.condition_number,
            "warnings": self.warnings,
        }


@dataclass
class SceneAssociationResult:
    """Structured API result for the full Step 5 association run."""

    success: bool
    object_dir: Path
    reconstruction_dir: Path
    output_dir: Path
    georeferenced_dir: Optional[Path] = None
    track_count: int = 0
    estimated_count: int = 0
    low_confidence_count: int = 0
    unavailable_count: int = 0
    processing_time_seconds: float = 0.0
    average_association_time_seconds: Optional[float] = None
    objects_3d_path: Optional[Path] = None
    tracks_3d_path: Optional[Path] = None
    trajectories_path: Optional[Path] = None
    annotations_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def path_value(path: Optional[Path]) -> Optional[str]:
            return str(path) if path is not None else None

        return {
            "success": self.success,
            "object_dir": str(self.object_dir),
            "reconstruction_dir": str(self.reconstruction_dir),
            "georeferenced_dir": (
                str(self.georeferenced_dir) if self.georeferenced_dir is not None else None
            ),
            "output_dir": str(self.output_dir),
            "track_count": self.track_count,
            "estimated_count": self.estimated_count,
            "low_confidence_count": self.low_confidence_count,
            "unavailable_count": self.unavailable_count,
            "processing_time_seconds": round(self.processing_time_seconds, 4),
            "average_association_time_seconds": self.average_association_time_seconds,
            "outputs": {
                "objects_3d": path_value(self.objects_3d_path),
                "object_tracks_3d": path_value(self.tracks_3d_path),
                "object_trajectories": path_value(self.trajectories_path),
                "scene_annotations": path_value(self.annotations_path),
            },
            "error": self.error,
            "warnings": self.warnings,
        }
