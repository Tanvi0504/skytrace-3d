"""Opt-in real-model smoke test for the checked-in selected-frame sequence."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pipeline.objects import detect_and_track_objects


@pytest.mark.integration
def test_pretrained_yolo_processes_example_selected_frames(tmp_path: Path) -> None:
    """Exercise the real optional backend only when explicitly requested.

    This test can download model weights and is therefore skipped in the normal
    unit suite. It asserts pipeline completion rather than a particular object
    label because the bundled video is not a labelled detection benchmark.
    """
    if os.environ.get("SKYTRACE_RUN_OBJECT_INTEGRATION") != "1":
        pytest.skip("set SKYTRACE_RUN_OBJECT_INTEGRATION=1 to run pretrained YOLO")
    pytest.importorskip("ultralytics")
    frames_dir = Path("outputs/example/frames")
    if not frames_dir.is_dir():
        pytest.skip("checked-in example selected-frame sequence is unavailable")

    result = detect_and_track_objects(
        frames_dir=frames_dir,
        output_dir=tmp_path / "objects",
        device=os.environ.get("SKYTRACE_OBJECT_INTEGRATION_DEVICE", "cpu"),
    )

    assert result.success, result.error
    assert result.frames_processed > 0
    assert result.detections_path is not None and result.detections_path.is_file()
