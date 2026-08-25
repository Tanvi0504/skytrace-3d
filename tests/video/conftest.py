"""Shared fixtures for pipeline.video tests.

Rather than requiring a real drone video, we synthesize small MP4 files
with OpenCV. "Sharp" frames contain a high-frequency checkerboard-like
pattern; "blurry" frames are the same content after a heavy Gaussian
blur, which reliably produces a much lower Laplacian-variance score.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

FRAME_SIZE = (160, 120)  # width, height


def _make_sharp_frame(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    width, height = FRAME_SIZE
    frame = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    # Overlay a high-frequency checkerboard to guarantee strong edges.
    checker = np.indices((height, width)).sum(axis=0) % 2
    frame[checker == 0] = 0
    frame[checker == 1] = 255
    return frame


def _make_blurry_frame(seed: int) -> np.ndarray:
    sharp = _make_sharp_frame(seed)
    return cv2.GaussianBlur(sharp, (25, 25), sigmaX=15)


def _write_video(path: Path, fps: float, frames: list[np.ndarray]) -> None:
    width, height = FRAME_SIZE
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    assert writer.isOpened(), "Test setup failed: VideoWriter could not open"
    for frame in frames:
        writer.write(frame)
    writer.release()


@pytest.fixture
def synthetic_video_mixed(tmp_path: Path) -> Path:
    """A 30 fps, 2-second video alternating sharp and blurry frames."""
    video_path = tmp_path / "mixed.mp4"
    frames = []
    for i in range(60):
        frames.append(_make_sharp_frame(i) if i % 2 == 0 else _make_blurry_frame(i))
    _write_video(video_path, fps=30.0, frames=frames)
    return video_path


@pytest.fixture
def synthetic_video_all_sharp(tmp_path: Path) -> Path:
    """A 30 fps, 1-second video where every frame is sharp."""
    video_path = tmp_path / "sharp.mp4"
    frames = [_make_sharp_frame(i) for i in range(30)]
    _write_video(video_path, fps=30.0, frames=frames)
    return video_path


@pytest.fixture
def synthetic_video_all_blurry(tmp_path: Path) -> Path:
    """A 30 fps, 1-second video where every frame is heavily blurred."""
    video_path = tmp_path / "blurry.mp4"
    frames = [_make_blurry_frame(i) for i in range(30)]
    _write_video(video_path, fps=30.0, frames=frames)
    return video_path


@pytest.fixture
def invalid_video_file(tmp_path: Path) -> Path:
    """A file with a video extension but garbage content."""
    path = tmp_path / "not_a_video.mp4"
    path.write_bytes(b"this is not a real video file" * 10)
    return path
