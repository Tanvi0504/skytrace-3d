from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.video.config import VideoProcessingConfig


def test_defaults_and_derived_paths(tmp_path: Path) -> None:
    config = VideoProcessingConfig(
        video_path=tmp_path / "in.mp4",
        output_dir=tmp_path / "outputs" / "run1",
    )
    assert config.target_fps == 5.0
    assert config.blur_threshold == 100.0
    assert config.run_id == "run1"
    assert config.frames_dir == tmp_path / "outputs" / "run1" / "frames"
    assert config.metadata_path.name == "metadata.json"
    assert config.manifest_path.name == "frame_manifest.json"
    assert config.rejected_path.name == "rejected_frames.json"


@pytest.mark.parametrize("bad_fps", [0, -1, -0.5])
def test_invalid_target_fps_rejected(tmp_path: Path, bad_fps: float) -> None:
    with pytest.raises(ValueError):
        VideoProcessingConfig(
            video_path=tmp_path / "in.mp4",
            output_dir=tmp_path / "out",
            target_fps=bad_fps,
        )


def test_negative_blur_threshold_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        VideoProcessingConfig(
            video_path=tmp_path / "in.mp4",
            output_dir=tmp_path / "out",
            blur_threshold=-1,
        )


@pytest.mark.parametrize("bad_quality", [-1, 101])
def test_invalid_jpeg_quality_rejected(tmp_path: Path, bad_quality: int) -> None:
    with pytest.raises(ValueError):
        VideoProcessingConfig(
            video_path=tmp_path / "in.mp4",
            output_dir=tmp_path / "out",
            jpeg_quality=bad_quality,
        )


def test_explicit_run_id_respected(tmp_path: Path) -> None:
    config = VideoProcessingConfig(
        video_path=tmp_path / "in.mp4",
        output_dir=tmp_path / "out",
        run_id="custom-id",
    )
    assert config.run_id == "custom-id"
