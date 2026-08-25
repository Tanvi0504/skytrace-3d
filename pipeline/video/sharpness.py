"""Frame sharpness / blur heuristics.

This module intentionally implements a single, well-understood metric:
the variance of the Laplacian of the grayscale image. It is a common,
cheap heuristic for relative sharpness, not a validated motion-blur
detector. Frames with a low score are *more likely* to be blurry, but
this is a filtering heuristic for Step 1 only -- it does not guarantee
that selected frames are free of motion blur, and it is not a claim
that this fully solves frame-quality assessment for the reconstruction
stage.
"""

from __future__ import annotations

import cv2
import numpy as np


def laplacian_sharpness(frame_bgr: np.ndarray) -> float:
    """Compute a Laplacian-variance sharpness score for a BGR frame.

    Args:
        frame_bgr: An HxWx3 BGR image as returned by ``cv2.VideoCapture.read``.

    Returns:
        The variance of the Laplacian of the grayscale image. Higher
        values indicate more high-frequency detail (a proxy for
        sharpness); lower values suggest a smoother/blurrier image.

    Raises:
        ValueError: If ``frame_bgr`` is empty or not a valid image array.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        raise ValueError("frame_bgr must be a non-empty image array")

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())
