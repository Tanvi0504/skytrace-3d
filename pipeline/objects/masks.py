"""Dynamic-candidate binary-mask generation for later reconstruction use."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from pipeline.objects.errors import ObjectOutputError
from pipeline.objects.models import ObjectDetection


def write_dynamic_mask(
    path: Path,
    image: np.ndarray,
    detections: list[ObjectDetection],
    *,
    padding_pixels: int,
) -> None:
    """Write a uint8 mask whose 255 pixels cover dynamic-candidate boxes.

    This deliberately masks all dynamic-capable detections, including parked
    vehicles, because Step 4 does not yet perform camera-motion-compensated
    observed-motion classification. Static-class detections remain unmasked.
    """
    height, width = image.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    for detection in detections:
        if not detection.is_dynamic_candidate:
            continue
        x1, y1, x2, y2 = detection.bbox_xyxy
        left = max(0, int(np.floor(min(x1, x2))) - padding_pixels)
        top = max(0, int(np.floor(min(y1, y2))) - padding_pixels)
        right = min(width, int(np.ceil(max(x1, x2))) + padding_pixels)
        bottom = min(height, int(np.ceil(max(y1, y2))) + padding_pixels)
        if right > left and bottom > top:
            mask[top:bottom, left:right] = 255
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), mask):
        raise ObjectOutputError(f"Could not write dynamic-object mask: {path}")
