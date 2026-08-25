from __future__ import annotations

import json
from pathlib import Path

import cv2
import pytest

from pipeline.video.config import VideoProcessingConfig
from pipeline.video.errors import (
    EmptyVideoError,
    VideoNotFoundError,
    VideoUnreadableError,
)
from pipeline.video.extractor import _compute_frame_step, process_video


def test_missing_video_file(tmp_path: Path) -> None:
    config = VideoProcessingConfig(
        video_path=tmp_path / "missing.mp4",
        output_dir=tmp_path / "out",
    )
    with pytest.raises(VideoNotFoundError):
        process_video(config)


def test_invalid_video_file(invalid_video_file: Path, tmp_path: Path) -> None:
    config = VideoProcessingConfig(
        video_path=invalid_video_file,
        output_dir=tmp_path / "out",
    )
    with pytest.raises(VideoUnreadableError):
        process_video(config)


def test_compute_frame_step() -> None:
    assert _compute_frame_step(source_fps=30, target_fps=5) == 6
    assert _compute_frame_step(source_fps=30, target_fps=30) == 1
    assert _compute_frame_step(source_fps=30, target_fps=60) == 1  # never upsample
    assert _compute_frame_step(source_fps=24, target_fps=1) == 24


def test_frame_extraction_sampling_rate(
    synthetic_video_all_sharp: Path, tmp_path: Path
) -> None:
    """30fps/1s video sampled at 5fps should yield 5 sampled frames."""
    config = VideoProcessingConfig(
        video_path=synthetic_video_all_sharp,
        output_dir=tmp_path / "out",
        target_fps=5.0,
        blur_threshold=100.0,
    )
    result = process_video(config)

    assert result.sampled_count == 5
    assert [r.frame_index for r in result.records] == [0, 6, 12, 18, 24]


def test_threshold_filtering(synthetic_video_mixed: Path, tmp_path: Path) -> None:
    """Alternating sharp/blurry frames should split roughly 50/50."""
    config = VideoProcessingConfig(
        video_path=synthetic_video_mixed,
        output_dir=tmp_path / "out",
        target_fps=30.0,  # sample every frame
        blur_threshold=100.0,
    )
    result = process_video(config)

    assert result.sampled_count == 60
    assert result.selected_count == 30
    assert result.rejected_count == 30
    # Even-indexed frames were generated sharp, odd ones blurry.
    for record in result.records:
        expected_selected = record.frame_index % 2 == 0
        assert record.selected == expected_selected


def test_all_frames_rejected_when_threshold_too_high(
    synthetic_video_all_sharp: Path, tmp_path: Path
) -> None:
    config = VideoProcessingConfig(
        video_path=synthetic_video_all_sharp,
        output_dir=tmp_path / "out",
        target_fps=5.0,
        blur_threshold=10_000_000.0,  # impossibly high
    )
    result = process_video(config)

    assert result.selected_count == 0
    assert result.rejected_count == result.sampled_count
    assert list(config.frames_dir.glob("*.jpg")) == []


def test_output_file_generation(
    synthetic_video_all_sharp: Path, tmp_path: Path
) -> None:
    config = VideoProcessingConfig(
        video_path=synthetic_video_all_sharp,
        output_dir=tmp_path / "out",
        target_fps=5.0,
        blur_threshold=100.0,
    )
    result = process_video(config)

    assert result.frames_dir.is_dir()
    saved_files = sorted(p.name for p in result.frames_dir.glob("*.jpg"))
    assert saved_files == [
        "frame_000000.jpg",
        "frame_000006.jpg",
        "frame_000012.jpg",
        "frame_000018.jpg",
        "frame_000024.jpg",
    ]
    # Saved files should be valid, readable images of the expected size.
    sample = cv2.imread(str(result.frames_dir / "frame_000000.jpg"))
    assert sample is not None
    assert sample.shape[:2] == (120, 160)

    assert result.metadata_path.is_file()
    assert result.manifest_path.is_file()
    assert result.rejected_path.is_file()


def test_metadata_json_generation(
    synthetic_video_all_sharp: Path, tmp_path: Path
) -> None:
    config = VideoProcessingConfig(
        video_path=synthetic_video_all_sharp,
        output_dir=tmp_path / "out",
        target_fps=5.0,
        blur_threshold=100.0,
        run_id="unit-test-run",
    )
    result = process_video(config)

    doc = json.loads(result.metadata_path.read_text())
    assert doc["run_id"] == "unit-test-run"
    assert doc["sampling_fps"] == 5.0
    assert doc["blur_threshold"] == 100.0
    assert doc["sampled_frame_count"] == 5
    assert doc["selected_frame_count"] == 5
    assert doc["rejected_frame_count"] == 0
    assert doc["processing_time_seconds"] >= 0
    assert doc["source_video"]["width"] == 160
    assert doc["source_video"]["height"] == 120

    manifest = json.loads(result.manifest_path.read_text())
    assert len(manifest["frames"]) == 5
    first = manifest["frames"][0]
    assert set(first.keys()) == {
        "frame_index",
        "timestamp_seconds",
        "sharpness_score",
        "selected",
        "filename",
    }

    rejected = json.loads(result.rejected_path.read_text())
    assert rejected["rejected_frames"] == []


def test_empty_video_raises(
    synthetic_video_all_sharp: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If every capture.read() call fails despite the video opening, we
    should surface EmptyVideoError rather than silently produce an empty
    (and misleading) successful result."""
    monkeypatch.setattr(cv2.VideoCapture, "read", lambda self: (False, None))

    config = VideoProcessingConfig(
        video_path=synthetic_video_all_sharp,
        output_dir=tmp_path / "out",
    )
    with pytest.raises(EmptyVideoError):
        process_video(config)


def test_run_id_defaults_to_output_dir_name(
    synthetic_video_all_sharp: Path, tmp_path: Path
) -> None:
    config = VideoProcessingConfig(
        video_path=synthetic_video_all_sharp,
        output_dir=tmp_path / "my_run",
    )
    assert config.run_id == "my_run"
