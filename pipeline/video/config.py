"""Configuration objects for the video ingestion module.

All tunable parameters flow through :class:`VideoProcessingConfig` so that
nothing is hard-coded inside the processing logic. The CLI (``cli.py``)
simply builds one of these from ``argv`` and passes it to
:func:`pipeline.video.extractor.process_video`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VideoProcessingConfig:
    """Parameters controlling video ingestion and frame filtering.

    Attributes:
        video_path: Path to the input drone video.
        output_dir: Directory the run's outputs will be written to. This
            directory is treated as the run directory itself (e.g.
            ``outputs/example``), not a parent of it. ``frames/``,
            ``metadata.json``, ``frame_manifest.json`` and
            ``rejected_frames.json`` are created directly inside it.
        target_fps: Desired sampling rate, in frames per second, of the
            *output* frame sequence. Must be > 0. If it is greater than
            the video's native FPS, every frame is sampled.
        blur_threshold: Minimum acceptable Laplacian-variance sharpness
            score. Sampled frames scoring below this are rejected (still
            recorded in the manifest, but not saved to disk).
        run_id: Optional identifier for this run. Defaults to the final
            path component of ``output_dir`` if not given.
        jpeg_quality: JPEG quality (0-100) used when saving selected
            frames.
        log_per_frame: If True, emit a DEBUG-level log line for every
            sampled frame. Off by default to avoid flooding logs.
    """

    video_path: Path
    output_dir: Path
    target_fps: float = 5.0
    blur_threshold: float = 100.0
    run_id: str | None = None
    jpeg_quality: int = 95
    log_per_frame: bool = False

    def __post_init__(self) -> None:
        self.video_path = Path(self.video_path)
        self.output_dir = Path(self.output_dir)

        if self.target_fps <= 0:
            raise ValueError(f"target_fps must be > 0, got {self.target_fps}")
        if self.blur_threshold < 0:
            raise ValueError(
                f"blur_threshold must be >= 0, got {self.blur_threshold}"
            )
        if not 0 <= self.jpeg_quality <= 100:
            raise ValueError(
                f"jpeg_quality must be between 0 and 100, got {self.jpeg_quality}"
            )
        if self.run_id is None:
            self.run_id = self.output_dir.name

    @property
    def frames_dir(self) -> Path:
        return self.output_dir / "frames"

    @property
    def metadata_path(self) -> Path:
        return self.output_dir / "metadata.json"

    @property
    def manifest_path(self) -> Path:
        return self.output_dir / "frame_manifest.json"

    @property
    def rejected_path(self) -> Path:
        return self.output_dir / "rejected_frames.json"
