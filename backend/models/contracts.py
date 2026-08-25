"""API contracts shared by the Step 7 backend endpoints."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING_STEP_1 = "RUNNING_STEP_1"
    RUNNING_STEP_2 = "RUNNING_STEP_2"
    RUNNING_STEP_3 = "RUNNING_STEP_3"
    RUNNING_STEP_4 = "RUNNING_STEP_4"
    RUNNING_STEP_5 = "RUNNING_STEP_5"
    RUNNING_STEP_6 = "RUNNING_STEP_6"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StepStatus(str, Enum):
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


class StepProgress(BaseModel):
    step: int
    name: str
    status: StepStatus = StepStatus.WAITING
    summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class RunStatus(BaseModel):
    run_id: str
    state: RunState
    created_at: str
    updated_at: str
    video_filename: str | None = None
    video_size_bytes: int | None = None
    error: str | None = None
    steps: list[StepProgress]


class CreateRunResponse(BaseModel):
    run_id: str
    status: RunStatus


class UploadResponse(BaseModel):
    run_id: str
    filename: str
    size_bytes: int
    content_type: str | None = None


class ProcessRequest(BaseModel):
    target_fps: float = 5.0
    blur_threshold: float = 100.0
    # Sparse SfM is browser-viewable and safe for the CPU-first Docker image.
    # Dense MVS remains available as an explicit request option.
    dense: bool = False
    overwrite: bool = False
    gps_metadata_filename: str | None = None
    resume: bool = False


class Point3D(BaseModel):
    x: float
    y: float
    z: float


class MeasurementRequest(BaseModel):
    point_a: Point3D
    point_b: Point3D
    unit: Literal["m", "metre", "meter", "meters", "metres"] = "m"


class SceneAsset(BaseModel):
    kind: Literal["point_cloud", "mesh", "unknown"]
    format: str
    url: str
    point_count: int | None = None
    source: str
    browser_notes: list[str] = Field(default_factory=list)


class SceneMetadata(BaseModel):
    run_id: str
    coordinate_system: str | None = None
    reconstruction_status: str
    georeferencing_status: str
    assets: list[SceneAsset] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class Object3D(BaseModel):
    object_id: str
    class_name: str
    track_id: int | None = None
    position_status: str
    position: list[float] | None = None
    coordinate_system: str | None = None
    detection_confidence: float | None = None
    observation_count: int | None = None
    is_dynamic_candidate: bool = False
    motion_status: str = "unknown"
    evidence_level: EvidenceLevel = EvidenceLevel.UNKNOWN
    evidence_score: float | None = None
    warnings: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class EvidenceInfo(BaseModel):
    run_id: str
    levels: dict[str, str]
    quality_regions: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResultsInfo(BaseModel):
    run_id: str
    files: dict[str, str]
    warnings: list[str] = Field(default_factory=list)
