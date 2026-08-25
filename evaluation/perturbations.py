"""Synthetic video/frame perturbations for controlled robustness tests."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def apply_motion_blur(frame: np.ndarray, level: int) -> np.ndarray:
    """Apply horizontal motion blur with explicit finite levels."""
    if level < 0 or level > 3:
        raise ValueError("motion blur level must be 0, 1, 2, or 3")
    if level == 0:
        return frame.copy()
    kernel_size = {1: 5, 2: 11, 3: 21}[level]
    kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
    kernel[kernel_size // 2, :] = 1.0 / kernel_size
    return cv2.filter2D(frame, -1, kernel)


def adjust_illumination(frame: np.ndarray, *, exposure_scale: float = 1.0, contrast: float = 1.0) -> np.ndarray:
    if exposure_scale <= 0 or contrast <= 0:
        raise ValueError("exposure_scale and contrast must be positive")
    adjusted = frame.astype(np.float32) * exposure_scale
    adjusted = (adjusted - 127.5) * contrast + 127.5
    return np.clip(adjusted, 0, 255).astype(np.uint8)


def add_sensor_noise(frame: np.ndarray, *, sigma: float, seed: int = 0) -> np.ndarray:
    if sigma < 0:
        raise ValueError("sigma must be non-negative")
    rng = np.random.default_rng(seed)
    noisy = frame.astype(np.float32) + rng.normal(0.0, sigma, frame.shape)
    return np.clip(noisy, 0, 255).astype(np.uint8)


def create_degraded_video(
    source_video: str | Path,
    output_video: str | Path,
    *,
    degradation: str,
    level: int = 1,
    jpeg_quality: int = 70,
) -> dict[str, Any]:
    """Create a controlled degraded MP4 when OpenCV can decode the source."""
    source = Path(source_video)
    output = Path(output_video)
    if not source.is_file():
        raise FileNotFoundError(source)
    if degradation == "copy" or level == 0:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, output)
        return {"degradation": degradation, "level": level, "source": str(source), "output": str(output)}

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {source}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        capture.release()
        raise ValueError(f"Could not create video: {output}")
    frames = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if degradation == "motion_blur":
                frame = apply_motion_blur(frame, level)
            elif degradation == "dark":
                frame = adjust_illumination(frame, exposure_scale=max(0.2, 1.0 - level * 0.2))
            elif degradation == "bright":
                frame = adjust_illumination(frame, exposure_scale=1.0 + level * 0.25)
            elif degradation == "contrast":
                frame = adjust_illumination(frame, contrast=1.0 + level * 0.35)
            elif degradation == "sensor_noise":
                frame = add_sensor_noise(frame, sigma=level * 8.0, seed=frames)
            elif degradation == "compression":
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                if ok:
                    frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            else:
                raise ValueError(f"Unsupported degradation: {degradation}")
            writer.write(frame)
            frames += 1
    finally:
        capture.release()
        writer.release()
    return {
        "degradation": degradation,
        "level": level,
        "source": str(source),
        "output": str(output),
        "frames_written": frames,
        "codec": "mp4v",
        "fps": fps,
        "resolution": [width, height],
        "jpeg_quality": jpeg_quality if degradation == "compression" else None,
    }
