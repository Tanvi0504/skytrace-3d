"""Step 1 selected-frame discovery and conservative identity propagation."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from pipeline.objects.errors import FramesInputError
from pipeline.objects.models import FrameRecord

_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".webp"})
_FRAME_INDEX_PATTERN = re.compile(r"frame_(\d+)", re.IGNORECASE)
_NATURAL_PARTS_PATTERN = re.compile(r"(\d+)")


def _natural_key(path: Path) -> list[object]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in _NATURAL_PARTS_PATTERN.split(path.name)
    ]


def _frame_index_from_filename(filename: str) -> int | None:
    match = _FRAME_INDEX_PATTERN.search(Path(filename).name)
    return int(match.group(1)) if match else None


def _manifest_identity(frames_dir: Path) -> tuple[dict[str, tuple[int | None, float | None]], list[str]]:
    """Read Step 1's optional manifest without making it a Step 4 dependency."""
    manifest_path = frames_dir.parent / "frame_manifest.json"
    if not manifest_path.is_file():
        return {}, [
            "Step 1 frame_manifest.json was not found; timestamps are unavailable "
            "unless they can be recovered from a frame filename."
        ]
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = document.get("frames", [])
        if not isinstance(records, list):
            raise ValueError("'frames' must be an array")
        identities: dict[str, tuple[int | None, float | None]] = {}
        for record in records:
            if not isinstance(record, dict) or not record.get("filename"):
                continue
            if record.get("selected") is False:
                continue
            index_value = record.get("frame_index")
            timestamp_value = record.get("timestamp_seconds")
            frame_index = (
                int(index_value)
                if isinstance(index_value, int) and index_value >= 0
                else None
            )
            timestamp = (
                float(timestamp_value)
                if isinstance(timestamp_value, (int, float))
                and math.isfinite(float(timestamp_value))
                else None
            )
            identities[Path(str(record["filename"])).name] = (frame_index, timestamp)
        return identities, []
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {}, [f"Could not read Step 1 frame manifest: {exc}"]


def collect_selected_frames(frames_dir: Path) -> tuple[list[FrameRecord], list[str]]:
    """Validate a selected-frame directory and attach known Step 1 identities."""
    if not frames_dir.is_dir():
        raise FramesInputError(f"Selected frames directory not found: {frames_dir}")
    paths = sorted(
        (
            path
            for path in frames_dir.iterdir()
            if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES
        ),
        key=_natural_key,
    )
    if not paths:
        raise FramesInputError(
            f"Selected frames directory contains no supported image files: {frames_dir}"
        )
    identities, warnings = _manifest_identity(frames_dir)
    frames = []
    for path in paths:
        frame_index, timestamp = identities.get(path.name, (None, None))
        if frame_index is None:
            frame_index = _frame_index_from_filename(path.name)
        frames.append(
            FrameRecord(
                path=path,
                frame_index=frame_index,
                timestamp_seconds=timestamp,
            )
        )
    return frames, warnings
