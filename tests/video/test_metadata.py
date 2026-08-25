from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.video.errors import VideoNotFoundError, VideoUnreadableError
from pipeline.video.metadata import open_video_capture, read_metadata


def test_missing_video_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.mp4"
    with pytest.raises(VideoNotFoundError):
        open_video_capture(missing)


def test_invalid_video_file_raises(invalid_video_file: Path) -> None:
    with pytest.raises(VideoUnreadableError):
        open_video_capture(invalid_video_file)


def test_metadata_extraction(synthetic_video_all_sharp: Path) -> None:
    capture = open_video_capture(synthetic_video_all_sharp)
    try:
        meta = read_metadata(capture, synthetic_video_all_sharp)
    finally:
        capture.release()

    assert meta.filename == synthetic_video_all_sharp.name
    assert meta.width == 160
    assert meta.height == 120
    assert meta.fps == pytest.approx(30.0, rel=0.05)
    assert meta.frame_count is not None
    assert meta.frame_count >= 29  # container counts can be off by one
    assert meta.duration_seconds is not None
    assert meta.duration_seconds == pytest.approx(1.0, rel=0.1)


def test_metadata_to_dict_schema(synthetic_video_all_sharp: Path) -> None:
    capture = open_video_capture(synthetic_video_all_sharp)
    try:
        meta = read_metadata(capture, synthetic_video_all_sharp)
    finally:
        capture.release()

    doc = meta.to_dict()
    expected_keys = {
        "filename",
        "width",
        "height",
        "fps",
        "frame_count",
        "duration_seconds",
    }
    assert set(doc.keys()) == expected_keys
