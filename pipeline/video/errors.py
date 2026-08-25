"""Exceptions raised by the video ingestion module.

Using a small, explicit exception hierarchy lets callers (CLI, tests,
or a future orchestrator) distinguish between different failure modes
instead of catching a generic ``Exception``.
"""

from __future__ import annotations


class VideoIngestionError(Exception):
    """Base class for all errors raised by ``pipeline.video``."""


class VideoNotFoundError(VideoIngestionError):
    """Raised when the given video path does not exist or is not a file."""


class VideoUnreadableError(VideoIngestionError):
    """Raised when OpenCV cannot open or decode the given video file."""


class EmptyVideoError(VideoIngestionError):
    """Raised when a video opens successfully but contains no usable frames."""
