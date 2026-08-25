"""Typed models for Step 4 detection, tracking, masks, and handoff metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence


# COCO names that can reasonably be people, vehicles, or animals. A member of
# this set is *capable* of moving; this baseline intentionally does not claim
# it is moving in a particular flight sequence.
DYNAMIC_CAPABLE_CLASSES = frozenset(
    {
        "person",
        "bicycle",
        "car",
        "motorcycle",
        "airplane",
        "bus",
        "train",
        "truck",
        "boat",
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "elephant",
        "bear",
        "zebra",
        "giraffe",
        "drone",
    }
)


@dataclass(frozen=True)
class DetectorInfo:
    """The loaded detector identity and its model-supported labels."""

    backend: str
    model_name: str
    supported_classes: tuple[str, ...]
    device: str
    tracker_name: Optional[str] = None


@dataclass(frozen=True)
class RawDetection:
    """Detector-neutral result prior to Step 4 metadata enrichment."""

    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]
    track_id: Optional[int] = None


@dataclass(frozen=True)
class FrameRecord:
    """A selected frame plus identity data inherited from Step 1 when present."""

    path: Path
    frame_index: Optional[int]
    timestamp_seconds: Optional[float]


@dataclass
class ObjectDetection:
    """One persisted 2D object observation in a selected frame."""

    detection_id: str
    frame_filename: str
    frame_index: Optional[int]
    timestamp_seconds: Optional[float]
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]
    is_dynamic_candidate: bool
    motion_status: str
    track_id: Optional[int]
    mask_path: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "detection_id": self.detection_id,
            "frame_filename": self.frame_filename,
            "frame_index": self.frame_index,
            "timestamp_seconds": self.timestamp_seconds,
            "class": self.class_name,
            "confidence": self.confidence,
            "bbox_xyxy_pixels": list(self.bbox_xyxy),
            "track_id": self.track_id,
            "is_dynamic_candidate": self.is_dynamic_candidate,
            "motion_status": self.motion_status,
            "mask_path": self.mask_path,
        }


@dataclass(frozen=True)
class TrackSummary:
    """One existing tracker ID summarized without inferring world motion."""

    track_id: int
    classes: tuple[str, ...]
    detection_ids: tuple[str, ...]
    frame_filenames: tuple[str, ...]
    frame_indices: tuple[int, ...]
    dynamic_candidate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "classes": list(self.classes),
            "detection_count": len(self.detection_ids),
            "frame_count": len(self.frame_filenames),
            "detection_ids": list(self.detection_ids),
            "frame_filenames": list(self.frame_filenames),
            "frame_indices": list(self.frame_indices),
            "is_dynamic_candidate": self.dynamic_candidate,
            "motion_status": "unknown",
            "motion_status_reason": (
                "Tracker IDs alone do not compensate for drone-camera motion; "
                "this Step 4 baseline does not classify observed world motion."
            ),
        }


@dataclass
class ObjectPipelineConfig:
    """Validated configuration for one isolated Step 4 run."""

    frames_dir: Path
    output_dir: Path
    model_name: str = "yolo11n.pt"
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.7
    classes: Optional[tuple[str, ...]] = None
    tracking: bool = True
    tracker_config: str = "bytetrack.yaml"
    device: str = "cpu"
    mask_padding_pixels: int = 0
    overwrite: bool = False

    def __post_init__(self) -> None:
        self.frames_dir = Path(self.frames_dir)
        self.output_dir = Path(self.output_dir)
        self.model_name = str(self.model_name).strip()
        self.device = str(self.device).strip()
        self.tracker_config = str(self.tracker_config).strip()
        if not self.model_name:
            raise ValueError("model_name must not be empty")
        if not self.device:
            raise ValueError("device must not be empty")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be within [0, 1]")
        if not 0.0 <= self.iou_threshold <= 1.0:
            raise ValueError("iou_threshold must be within [0, 1]")
        if self.tracking and not self.tracker_config:
            raise ValueError("tracker_config must not be empty when tracking is enabled")
        if self.mask_padding_pixels < 0:
            raise ValueError("mask_padding_pixels must be >= 0")
        if self.classes is not None:
            names = tuple(str(name).strip().lower() for name in self.classes)
            if not names or any(not name for name in names):
                raise ValueError("classes must contain one or more non-empty class names")
            self.classes = tuple(dict.fromkeys(names))

    @property
    def masks_dir(self) -> Path:
        return self.output_dir / "masks"

    @property
    def detections_path(self) -> Path:
        return self.output_dir / "detections.json"

    @property
    def tracks_path(self) -> Path:
        return self.output_dir / "tracks.json"

    @property
    def metadata_path(self) -> Path:
        return self.output_dir / "object_metadata.json"


@dataclass
class ObjectPipelineResult:
    """Structured outcome of object detection, tracking, and mask generation."""

    success: bool
    frames_dir: Path
    output_dir: Path
    model_name: str
    detector_backend: Optional[str] = None
    device: Optional[str] = None
    frames_processed: int = 0
    frames_failed: int = 0
    detection_count: int = 0
    dynamic_candidate_count: int = 0
    track_count: int = 0
    detected_classes: list[str] = field(default_factory=list)
    supported_classes: list[str] = field(default_factory=list)
    processing_time_seconds: float = 0.0
    frames_per_second: Optional[float] = None
    detections_path: Optional[Path] = None
    tracks_path: Optional[Path] = None
    masks_dir: Optional[Path] = None
    metadata_path: Optional[Path] = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def path_value(value: Optional[Path]) -> Optional[str]:
            return str(value) if value is not None else None

        return {
            "success": self.success,
            "frames_dir": str(self.frames_dir),
            "output_dir": str(self.output_dir),
            "model_name": self.model_name,
            "detector_backend": self.detector_backend,
            "device": self.device,
            "frames_processed": self.frames_processed,
            "frames_failed": self.frames_failed,
            "detection_count": self.detection_count,
            "dynamic_candidate_count": self.dynamic_candidate_count,
            "track_count": self.track_count,
            "detected_classes": self.detected_classes,
            "supported_classes": self.supported_classes,
            "processing_time_seconds": round(self.processing_time_seconds, 4),
            "frames_per_second": self.frames_per_second,
            "outputs": {
                "detections": path_value(self.detections_path),
                "tracks": path_value(self.tracks_path),
                "masks": path_value(self.masks_dir),
            },
            "error": self.error,
            "warnings": self.warnings,
        }


def normalise_requested_classes(classes: Optional[Sequence[str]]) -> Optional[tuple[str, ...]]:
    """Preserve a public API sequence while configuration stores an immutable tuple."""
    return tuple(classes) if classes is not None else None
