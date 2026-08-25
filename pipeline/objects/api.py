"""Public API for Step 4 object detection, tracking, and dynamic masks."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional, Sequence

import cv2

from pipeline.objects.detector import ObjectDetector, UltralyticsYOLODetector
from pipeline.objects.errors import ObjectPipelineError
from pipeline.objects.frames import collect_selected_frames
from pipeline.objects.masks import write_dynamic_mask
from pipeline.objects.models import (
    DYNAMIC_CAPABLE_CLASSES,
    DetectorInfo,
    ObjectDetection,
    ObjectPipelineConfig,
    ObjectPipelineResult,
    RawDetection,
    TrackSummary,
    normalise_requested_classes,
)
from pipeline.objects.output import (
    prepare_output_directory,
    write_detections,
    write_metadata,
    write_tracks,
)


def _valid_detection(
    raw: RawDetection,
    config: ObjectPipelineConfig,
) -> tuple[RawDetection | None, str | None]:
    """Validate detector-neutral output before exposing it to later stages."""
    class_name = str(raw.class_name).strip().lower()
    try:
        confidence = float(raw.confidence)
        coordinates = tuple(float(value) for value in raw.bbox_xyxy)
    except (TypeError, ValueError):
        return None, "detector returned a non-numeric confidence or bounding box"
    if not class_name:
        return None, "detector returned an empty class name"
    if len(coordinates) != 4 or not all(math.isfinite(value) for value in coordinates):
        return None, "detector returned a non-finite or malformed bounding box"
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        return None, "detector returned an invalid confidence"
    x1, y1, x2, y2 = coordinates
    if x2 <= x1 or y2 <= y1:
        return None, "detector returned a bounding box with non-positive area"
    if confidence < config.confidence_threshold:
        return None, None
    if config.classes is not None and class_name not in config.classes:
        return None, None
    return (
        RawDetection(
            class_name=class_name,
            confidence=confidence,
            bbox_xyxy=coordinates,
            track_id=raw.track_id if config.tracking else None,
        ),
        None,
    )


def _summarise_tracks(detections: list[ObjectDetection]) -> list[TrackSummary]:
    """Summarize supplied tracker IDs without estimating image or world motion."""
    grouped: dict[int, list[ObjectDetection]] = defaultdict(list)
    for detection in detections:
        if detection.track_id is not None:
            grouped[detection.track_id].append(detection)
    summaries = []
    for track_id in sorted(grouped):
        observations = grouped[track_id]
        frame_filenames = tuple(dict.fromkeys(item.frame_filename for item in observations))
        frame_indices = tuple(
            dict.fromkeys(
                item.frame_index for item in observations if item.frame_index is not None
            )
        )
        summaries.append(
            TrackSummary(
                track_id=track_id,
                classes=tuple(sorted({item.class_name for item in observations})),
                detection_ids=tuple(item.detection_id for item in observations),
                frame_filenames=frame_filenames,
                frame_indices=frame_indices,
                dynamic_candidate=any(item.is_dynamic_candidate for item in observations),
            )
        )
    return summaries


def detect_and_track_objects(
    frames_dir: str | Path,
    output_dir: str | Path,
    *,
    model_name: str = "yolo11n.pt",
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.7,
    classes: Optional[Sequence[str]] = None,
    tracking: bool = True,
    tracker_config: str = "bytetrack.yaml",
    device: str = "cpu",
    mask_padding_pixels: int = 0,
    overwrite: bool = False,
    detector: ObjectDetector | None = None,
) -> ObjectPipelineResult:
    """Detect selected-frame objects, retain tracker IDs, and write dynamic masks.

    The default lazy backend is pretrained Ultralytics YOLO with its supported
    ByteTrack integration. A custom ``detector`` is accepted to keep the model
    replaceable and to permit lightweight tests. Detections store 2D evidence
    only; they do not prove object motion or provide a 3D location.
    """
    started_at = time.monotonic()
    config: ObjectPipelineConfig | None = None
    output_workspace_prepared = False
    detector_info: DetectorInfo | None = None
    result: ObjectPipelineResult | None = None
    try:
        config = ObjectPipelineConfig(
            frames_dir=Path(frames_dir),
            output_dir=Path(output_dir),
            model_name=model_name,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            classes=normalise_requested_classes(classes),
            tracking=tracking,
            tracker_config=tracker_config,
            device=device,
            mask_padding_pixels=mask_padding_pixels,
            overwrite=overwrite,
        )
        frames, warnings = collect_selected_frames(config.frames_dir)
        prepare_output_directory(config)
        output_workspace_prepared = True

        active_detector = detector or UltralyticsYOLODetector(
            config.model_name, config.device
        )
        detector_info = active_detector.initialize()
        if config.classes is not None:
            unavailable = sorted(set(config.classes) - set(detector_info.supported_classes))
            if unavailable:
                warnings.append(
                    "Requested class(es) are not reported by the loaded model and will "
                    f"not be detected: {', '.join(unavailable)}."
                )

        detections: list[ObjectDetection] = []
        frames_processed = 0
        frames_failed = 0
        for frame in frames:
            image = cv2.imread(str(frame.path), cv2.IMREAD_COLOR)
            if image is None:
                frames_failed += 1
                warnings.append(f"Skipped unreadable frame: {frame.path.name}")
                continue
            try:
                raw_detections = active_detector.detect(
                    image,
                    confidence_threshold=config.confidence_threshold,
                    iou_threshold=config.iou_threshold,
                    classes=config.classes,
                    tracking=config.tracking,
                    tracker_config=config.tracker_config,
                )
            except Exception as exc:  # A single backend failure must not stop the sequence.
                frames_failed += 1
                warnings.append(f"Skipped {frame.path.name}: detector failed: {exc}")
                continue

            frame_detections: list[ObjectDetection] = []
            for ordinal, raw_detection in enumerate(raw_detections, start=1):
                valid, reason = _valid_detection(raw_detection, config)
                if reason is not None:
                    warnings.append(
                        f"Ignored malformed detection in {frame.path.name}: {reason}."
                    )
                    continue
                if valid is None:
                    continue
                dynamic_candidate = valid.class_name in DYNAMIC_CAPABLE_CLASSES
                frame_detections.append(
                    ObjectDetection(
                        detection_id=f"{frame.path.name}:{ordinal}",
                        frame_filename=frame.path.name,
                        frame_index=frame.frame_index,
                        timestamp_seconds=frame.timestamp_seconds,
                        class_name=valid.class_name,
                        confidence=valid.confidence,
                        bbox_xyxy=valid.bbox_xyxy,
                        is_dynamic_candidate=dynamic_candidate,
                        motion_status="unknown" if dynamic_candidate else "not_evaluated",
                        track_id=valid.track_id,
                    )
                )

            mask_path = config.masks_dir / f"{frame.path.stem}.png"
            try:
                write_dynamic_mask(
                    mask_path,
                    image,
                    frame_detections,
                    padding_pixels=config.mask_padding_pixels,
                )
                relative_mask_path = mask_path.relative_to(config.output_dir).as_posix()
                for item in frame_detections:
                    item.mask_path = relative_mask_path
            except (ObjectPipelineError, OSError) as exc:
                warnings.append(f"No mask written for {frame.path.name}: {exc}")
            detections.extend(frame_detections)
            frames_processed += 1

        tracks = _summarise_tracks(detections)
        if config.tracking and detections and not tracks:
            warnings.append(
                "Tracking was enabled but the detector returned no track IDs. "
                "Detections remain usable, but temporal association is unavailable."
            )
        success = frames_processed > 0
        result = ObjectPipelineResult(
            success=success,
            frames_dir=config.frames_dir,
            output_dir=config.output_dir,
            model_name=detector_info.model_name,
            detector_backend=detector_info.backend,
            device=detector_info.device,
            frames_processed=frames_processed,
            frames_failed=frames_failed,
            detection_count=len(detections),
            dynamic_candidate_count=sum(
                item.is_dynamic_candidate for item in detections
            ),
            track_count=len(tracks),
            detected_classes=sorted({item.class_name for item in detections}),
            supported_classes=list(detector_info.supported_classes),
            frames_per_second=(
                frames_processed / (time.monotonic() - started_at)
                if time.monotonic() > started_at
                else None
            ),
            detections_path=config.detections_path,
            tracks_path=config.tracks_path,
            masks_dir=config.masks_dir,
            error=(
                None
                if success
                else "No selected frame could be processed successfully."
            ),
            warnings=warnings,
        )
        write_detections(config.detections_path, detections, detector_info)
        write_tracks(
            config.tracks_path,
            tracks,
            detector_info,
            tracking_enabled=config.tracking,
        )
    except (ObjectPipelineError, OSError, ValueError) as exc:
        result = ObjectPipelineResult(
            success=False,
            frames_dir=Path(frames_dir),
            output_dir=Path(output_dir),
            model_name=model_name,
            error=str(exc),
        )

    result.processing_time_seconds = time.monotonic() - started_at
    if result.frames_processed > 0 and result.processing_time_seconds > 0:
        result.frames_per_second = result.frames_processed / result.processing_time_seconds
    if config is not None and output_workspace_prepared:
        write_metadata(config.metadata_path, result, config, detector_info)
    return result
