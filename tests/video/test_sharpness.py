from __future__ import annotations

import numpy as np
import pytest

from pipeline.video.sharpness import laplacian_sharpness
from tests.video.conftest import _make_blurry_frame, _make_sharp_frame


def test_sharp_frame_scores_higher_than_blurry() -> None:
    sharp_score = laplacian_sharpness(_make_sharp_frame(seed=42))
    blurry_score = laplacian_sharpness(_make_blurry_frame(seed=42))
    assert sharp_score > blurry_score


def test_uniform_frame_has_zero_variance() -> None:
    flat = np.full((100, 100, 3), 128, dtype=np.uint8)
    assert laplacian_sharpness(flat) == pytest.approx(0.0, abs=1e-6)


def test_empty_frame_raises_value_error() -> None:
    with pytest.raises(ValueError):
        laplacian_sharpness(np.empty((0, 0, 3), dtype=np.uint8))
