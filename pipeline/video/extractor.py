"""Core video ingestion, sampling, and blur-based frame filtering.

This is the only module in this package that STEP 2 (3D reconstruction)
needs to care about indirectly -- and even then, only through the files
it produces, not through any Python object. See ``docs/video_module.md``
for the file-based integration contract.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2

from pipeline.video.config import VideoProcessingConfig
from pipeline.video.errors import EmptyVideoError
from pipeline.video.metadata import VideoMetadata, open_video_capture, read_metadata
from pipeline.video.sharpness import laplacian_sharpness

logger = logging.getLogger("pipeline.video")


@dataclass
class FrameRecord:
    """Per-frame record stored in the manifest.

    ``filename`` is ``None`` for frames that were sampled but rejected
    for blur, since no image file is written for them.
    """

    frame_index: int
    timestamp_seconds: float
    sharpness_score: float
    selected: bool
    filename: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProcessingResult:
    """Summary of a completed ``process_video`` run."""

    run_id: str
    output_dir: Path
    frames_dir: Path
    metadata_path: Path
    manifest_path: Path
    rejected_path: Path
    video_metadata: VideoMetadata
    sampled_count: int
    selected_count: int
    rejected_count: int
    processing_time_seconds: float
    records: list[FrameRecord] = field(default_factory=list)


def _compute_frame_step(source_fps: float, target_fps: float) -> int:
    """Compute how many source frames to advance between samples.

    If ``target_fps`` is greater than or equal to ``source_fps``, every
    frame is sampled (step of 1).
    """
    if target_fps >= source_fps:
        return 1
    step = round(source_fps / target_fps)
    return max(1, step)


def process_video(config: VideoProcessingConfig) -> ProcessingResult:
    """Ingest a drone video, sample frames, filter by sharpness, and save.

    Args:
        config: Fully-specified processing parameters. See
            :class:`~pipeline.video.config.VideoProcessingConfig`.

    Returns:
        A :class:`ProcessingResult` describing what was produced. The
        same information is also written to disk as JSON (see
        ``docs/video_module.md``).

    Raises:
        VideoNotFoundError: The input path does not exist.
        VideoUnreadableError: OpenCV could not open/decode the video.
        EmptyVideoError: The video opened but contains no usable frames.
    """
    start_time = time.monotonic()

    capture = open_video_capture(config.video_path)
    try:
        video_metadata = read_metadata(capture, config.video_path)
        logger.info(
            "Opened video %s (%dx%d @ %.2f fps, ~%s frames)",
            config.video_path.name,
            video_metadata.width,
            video_metadata.height,
            video_metadata.fps,
            video_metadata.frame_count or "unknown",
        )

        frame_step = _compute_frame_step(video_metadata.fps, config.target_fps)
        logger.info(
            "Sampling every %d source frame(s) to target ~%.2f fps",
            frame_step,
            config.target_fps,
        )

        config.frames_dir.mkdir(parents=True, exist_ok=True)

        records: list[FrameRecord] = []
        frame_index = 0
        sampled_count = 0
        selected_count = 0

        while True:
            ok, frame = capture.read()
            if not ok:
                break

            if frame_index % frame_step == 0:
                sampled_count += 1
                score = laplacian_sharpness(frame)
                selected = score >= config.blur_threshold
                timestamp = frame_index / video_metadata.fps

                filename: str | None = None
                if selected:
                    filename = f"frame_{frame_index:06d}.jpg"
                    out_path = config.frames_dir / filename
                    cv2.imwrite(
                        str(out_path),
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, config.jpeg_quality],
                    )
                    selected_count += 1

                record = FrameRecord(
                    frame_index=frame_index,
                    timestamp_seconds=round(timestamp, 3),
                    sharpness_score=round(score, 3),
                    selected=selected,
                    filename=filename,
                )
                records.append(record)

                if config.log_per_frame:
                    logger.debug(
                        "frame %d: score=%.2f selected=%s",
                        frame_index,
                        score,
                        selected,
                    )

            frame_index += 1
    finally:
        capture.release()

    if sampled_count == 0:
        raise EmptyVideoError(
            f"No frames could be decoded from video: {config.video_path}"
        )

    rejected_count = sampled_count - selected_count
    processing_time = time.monotonic() - start_time

    logger.info(
        "Processed %d sampled frame(s): %d selected, %d rejected (%.2fs)",
        sampled_count,
        selected_count,
        rejected_count,
        processing_time,
    )
    logger.info("Output written to %s", config.output_dir)

    result = ProcessingResult(
        run_id=config.run_id,
        output_dir=config.output_dir,
        frames_dir=config.frames_dir,
        metadata_path=config.metadata_path,
        manifest_path=config.manifest_path,
        rejected_path=config.rejected_path,
        video_metadata=video_metadata,
        sampled_count=sampled_count,
        selected_count=selected_count,
        rejected_count=rejected_count,
        processing_time_seconds=round(processing_time, 4),
        records=records,
    )

    _write_outputs(config, result)
    return result


def _write_outputs(config: VideoProcessingConfig, result: ProcessingResult) -> None:
    """Write metadata.json, frame_manifest.json, and rejected_frames.json."""
    metadata_doc = {
        "run_id": result.run_id,
        "source_video": result.video_metadata.to_dict(),
        "sampling_fps": config.target_fps,
        "blur_threshold": config.blur_threshold,
        "sampled_frame_count": result.sampled_count,
        "selected_frame_count": result.selected_count,
        "rejected_frame_count": result.rejected_count,
        "processing_time_seconds": result.processing_time_seconds,
        "frames_dir": str(result.frames_dir),
    }
    config.metadata_path.write_text(json.dumps(metadata_doc, indent=2))

    manifest_doc = {
        "run_id": result.run_id,
        "frames": [r.to_dict() for r in result.records],
    }
    config.manifest_path.write_text(json.dumps(manifest_doc, indent=2))

    rejected_doc = {
        "run_id": result.run_id,
        "rejected_frames": [
            r.to_dict() for r in result.records if not r.selected
        ],
    }
    config.rejected_path.write_text(json.dumps(rejected_doc, indent=2))
