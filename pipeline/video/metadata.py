"""Video validation and metadata extraction helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import cv2

from pipeline.video.errors import (
    EmptyVideoError,
    VideoNotFoundError,
    VideoUnreadableError,
)


@dataclass
class VideoMetadata:
    """Basic properties read from the video container/codec header.

    ``frame_count`` and ``duration_seconds`` come from container metadata
    reported by OpenCV/FFmpeg, which is not always accurate for every
    codec/container combination. Callers that need an exact frame count
    should rely on the number of frames actually decoded during
    extraction instead.
    """

    filename: str
    width: int
    height: int
    fps: float
    frame_count: int | None
    duration_seconds: float | None

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "duration_seconds": self.duration_seconds,
        }


def validate_video_path(video_path: Path) -> None:
    """Validate that ``video_path`` exists, is a file, and is readable.

    Raises:
        VideoNotFoundError: If the path does not exist or is not a file.
        VideoUnreadableError: If the path exists but lacks read permission.
    """
    if not video_path.exists() or not video_path.is_file():
        raise VideoNotFoundError(f"Video file not found: {video_path}")
    if not os.access(video_path, os.R_OK):
        raise VideoUnreadableError(f"Video file is not readable: {video_path}")


def open_video_capture(video_path: Path) -> cv2.VideoCapture:
    """Open a video with OpenCV, validating that it actually decodes.

    Raises:
        VideoNotFoundError: If the file does not exist.
        VideoUnreadableError: If OpenCV cannot open the codec/container.
    """
    validate_video_path(video_path)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise VideoUnreadableError(
            f"Could not open video (unsupported codec or corrupt file): {video_path}"
        )
    return capture


def read_metadata(capture: cv2.VideoCapture, video_path: Path) -> VideoMetadata:
    """Read container-level metadata from an already-opened capture.

    Raises:
        EmptyVideoError: If the video reports zero width/height, or a
            zero/negative FPS, indicating there is no usable video stream.
    """
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    raw_frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

    if width <= 0 or height <= 0:
        raise EmptyVideoError(
            f"Video reports invalid dimensions ({width}x{height}): {video_path}"
        )
    if fps <= 0:
        raise EmptyVideoError(
            f"Video reports invalid FPS ({fps}); cannot compute sampling: {video_path}"
        )

    frame_count = raw_frame_count if raw_frame_count > 0 else None
    duration = (frame_count / fps) if frame_count else None

    return VideoMetadata(
        filename=video_path.name,
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        duration_seconds=duration,
    )
