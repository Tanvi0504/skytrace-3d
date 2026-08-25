from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from pipeline.objects import detect_and_track_objects
from pipeline.objects.detector import ObjectDetector
from pipeline.objects.errors import DetectorInitializationError
from pipeline.objects.models import DetectorInfo, RawDetection


class FakeDetector(ObjectDetector):
    """Small deterministic detector that exercises the public replacement seam."""

    def __init__(self, responses: list[list[RawDetection] | Exception]) -> None:
        self.responses = responses
        self.initialized = False
        self.calls: list[dict[str, object]] = []

    def initialize(self) -> DetectorInfo:
        self.initialized = True
        return DetectorInfo(
            backend="fake-detector",
            model_name="fake-pretrained-model",
            supported_classes=("person", "car", "building"),
            device="cpu",
            tracker_name="ByteTrack",
        )

    def detect(
        self,
        image: np.ndarray,
        *,
        confidence_threshold: float,
        iou_threshold: float,
        classes: tuple[str, ...] | None,
        tracking: bool,
        tracker_config: str,
    ) -> list[RawDetection]:
        self.calls.append(
            {
                "confidence_threshold": confidence_threshold,
                "iou_threshold": iou_threshold,
                "classes": classes,
                "tracking": tracking,
                "tracker_config": tracker_config,
            }
        )
        response = self.responses[len(self.calls) - 1]
        if isinstance(response, Exception):
            raise response
        return response


class InitializationFailureDetector(FakeDetector):
    def __init__(self) -> None:
        super().__init__([])

    def initialize(self) -> DetectorInfo:
        raise DetectorInitializationError("pretrained weights are unavailable")


def _write_frame(path: Path, value: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((20, 30, 3), value, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def _frames(tmp_path: Path, count: int = 2) -> Path:
    frames_dir = tmp_path / "frames"
    for index in range(count):
        _write_frame(frames_dir / f"frame_{index * 6:06d}.jpg", value=index)
    (tmp_path / "frame_manifest.json").write_text(
        json.dumps(
            {
                "frames": [
                    {
                        "filename": f"frame_{index * 6:06d}.jpg",
                        "frame_index": index * 6,
                        "timestamp_seconds": index * 0.2,
                        "selected": True,
                    }
                    for index in range(count)
                ]
            }
        )
    )
    return frames_dir


def _person(track_id: int | None = 7, confidence: float = 0.95) -> RawDetection:
    return RawDetection("person", confidence, (2.0, 3.0, 12.0, 13.0), track_id)


def test_invalid_frames_directory_returns_structured_failure(tmp_path: Path) -> None:
    result = detect_and_track_objects(
        tmp_path / "missing",
        tmp_path / "objects",
        detector=FakeDetector([]),
    )

    assert not result.success
    assert "Selected frames directory not found" in (result.error or "")


def test_empty_frames_directory_returns_structured_failure(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()

    result = detect_and_track_objects(
        frames_dir,
        tmp_path / "objects",
        detector=FakeDetector([]),
    )

    assert not result.success
    assert "contains no supported image files" in (result.error or "")


def test_detection_schema_masks_and_tracker_schema_are_written(tmp_path: Path) -> None:
    frames_dir = _frames(tmp_path)
    detector = FakeDetector(
        [
            [_person(), RawDetection("building", 0.88, (16.0, 2.0, 27.0, 12.0), 3)],
            [_person()],
        ]
    )
    output_dir = tmp_path / "objects"

    result = detect_and_track_objects(frames_dir, output_dir, detector=detector)

    assert result.success
    assert detector.initialized
    assert result.frames_processed == 2
    assert result.detection_count == 3
    assert result.dynamic_candidate_count == 2
    assert result.track_count == 2
    detections = json.loads((output_dir / "detections.json").read_text())["detections"]
    assert detections[0] == {
        "detection_id": "frame_000000.jpg:1",
        "frame_filename": "frame_000000.jpg",
        "frame_index": 0,
        "timestamp_seconds": 0.0,
        "class": "person",
        "confidence": 0.95,
        "bbox_xyxy_pixels": [2.0, 3.0, 12.0, 13.0],
        "track_id": 7,
        "is_dynamic_candidate": True,
        "motion_status": "unknown",
        "mask_path": "masks/frame_000000.png",
    }
    tracks = json.loads((output_dir / "tracks.json").read_text())
    assert tracks["tracking_enabled"] is True
    person_track = next(track for track in tracks["tracks"] if track["track_id"] == 7)
    assert person_track["frame_count"] == 2
    assert person_track["motion_status"] == "unknown"
    mask = cv2.imread(str(output_dir / "masks" / "frame_000000.png"), cv2.IMREAD_GRAYSCALE)
    assert mask[5, 4] == 255  # person: dynamic-capable and therefore masked
    assert mask[5, 20] == 0  # building: retained as a static-scene annotation
    metadata = json.loads((output_dir / "object_metadata.json").read_text())
    assert metadata["future_3d_association"]["join_keys"] == [
        "frame_filename",
        "frame_index",
        "timestamp_seconds",
        "bbox_xyxy_pixels",
    ]


def test_thresholds_and_requested_classes_are_enforced_at_pipeline_boundary(
    tmp_path: Path,
) -> None:
    frames_dir = _frames(tmp_path, count=1)
    detector = FakeDetector(
        [
            [_person(confidence=0.40), _person(track_id=8, confidence=0.91), RawDetection("building", 0.99, (1, 1, 4, 4), 2)]
        ]
    )

    result = detect_and_track_objects(
        frames_dir,
        tmp_path / "objects",
        confidence_threshold=0.5,
        iou_threshold=0.4,
        classes=["person"],
        detector=detector,
    )

    assert result.success
    assert result.detection_count == 1
    assert result.detected_classes == ["person"]
    assert detector.calls[0]["confidence_threshold"] == 0.5
    assert detector.calls[0]["iou_threshold"] == 0.4
    assert detector.calls[0]["classes"] == ("person",)


def test_no_detections_still_writes_an_empty_mask(tmp_path: Path) -> None:
    frames_dir = _frames(tmp_path, count=1)

    result = detect_and_track_objects(
        frames_dir,
        tmp_path / "objects",
        detector=FakeDetector([[]]),
    )

    assert result.success
    assert result.detection_count == 0
    mask = cv2.imread(str(tmp_path / "objects" / "masks" / "frame_000000.png"), cv2.IMREAD_GRAYSCALE)
    assert np.count_nonzero(mask) == 0


def test_one_detector_failure_does_not_stop_other_frames(tmp_path: Path) -> None:
    frames_dir = _frames(tmp_path)

    result = detect_and_track_objects(
        frames_dir,
        tmp_path / "objects",
        detector=FakeDetector([[_person()], RuntimeError("temporary accelerator error")]),
    )

    assert result.success
    assert result.frames_processed == 1
    assert result.frames_failed == 1
    assert result.detection_count == 1
    assert any("temporary accelerator error" in warning for warning in result.warnings)


def test_detector_initialization_failure_writes_structured_metadata(tmp_path: Path) -> None:
    frames_dir = _frames(tmp_path, count=1)
    output_dir = tmp_path / "objects"

    result = detect_and_track_objects(
        frames_dir,
        output_dir,
        detector=InitializationFailureDetector(),
    )

    assert not result.success
    assert "pretrained weights are unavailable" in (result.error or "")
    metadata = json.loads((output_dir / "object_metadata.json").read_text())
    assert metadata["success"] is False
    assert metadata["detector"] is None
