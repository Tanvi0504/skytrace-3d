"""Input and workspace validation for Step 2 reconstruction."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import cv2

from pipeline.reconstruction.errors import (
    EmptyFramesDirectoryError,
    FramesDirectoryError,
    InvalidImageFilesError,
    OutputDirectoryError,
)

SUPPORTED_IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff"}


def validate_frames_directory(frames_dir: Path) -> list[Path]:
    """Return sorted, decodable selected frames from a Step 1 output folder."""
    if not frames_dir.exists() or not frames_dir.is_dir():
        raise FramesDirectoryError(
            f"Selected frames directory was not found or is not a directory: "
            f"{frames_dir}"
        )
    if not os.access(frames_dir, os.R_OK):
        raise FramesDirectoryError(f"Selected frames directory is not readable: {frames_dir}")

    image_paths = sorted(
        (
            path
            for path in frames_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        ),
        key=lambda path: path.name,
    )
    if not image_paths:
        raise EmptyFramesDirectoryError(
            f"No supported image frames found in: {frames_dir}"
        )

    invalid_files = []
    for image_path in image_paths:
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None or image.size == 0:
            invalid_files.append(image_path)
    if invalid_files:
        raise InvalidImageFilesError(invalid_files)
    return image_paths


def prepare_output_directory(
    output_dir: Path,
    frames_dir: Path,
    *,
    overwrite: bool,
) -> None:
    """Create a fresh reconstruction workspace without risking Step 1 files."""
    resolved_output = output_dir.resolve()
    resolved_frames = frames_dir.resolve()
    if resolved_output == resolved_frames or resolved_output in resolved_frames.parents:
        raise OutputDirectoryError(
            "Reconstruction output must not be the frames directory or one of its "
            f"parents: {output_dir}"
        )

    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise OutputDirectoryError(
                f"Reconstruction output directory is not empty: {output_dir}. "
                "Use a new directory or set overwrite=True."
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

