"""Video ingestion, frame extraction, and blur filtering (SkyTrace Step 1).

Public API:
    from pipeline.video import VideoProcessingConfig, process_video

    config = VideoProcessingConfig(
        video_path="data/test/example.mp4",
        output_dir="outputs/example",
        target_fps=5.0,
        blur_threshold=100.0,
    )
    result = process_video(config)
    print(result.frames_dir)

See ``docs/video_module.md`` for the full file-based integration contract
consumed by the (separately developed) reconstruction stage.
"""

from pipeline.video.config import VideoProcessingConfig
from pipeline.video.errors import (
    EmptyVideoError,
    VideoIngestionError,
    VideoNotFoundError,
    VideoUnreadableError,
)
from pipeline.video.extractor import FrameRecord, ProcessingResult, process_video
from pipeline.video.metadata import VideoMetadata
from pipeline.video.sharpness import laplacian_sharpness

__all__ = [
    "VideoProcessingConfig",
    "process_video",
    "ProcessingResult",
    "FrameRecord",
    "VideoMetadata",
    "laplacian_sharpness",
    "VideoIngestionError",
    "VideoNotFoundError",
    "VideoUnreadableError",
    "EmptyVideoError",
]
