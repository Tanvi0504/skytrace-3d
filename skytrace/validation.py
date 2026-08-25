"""Early input and resource validation for an integrated SkyTrace run."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any


class InputValidationError(ValueError):
    """A user-correctable input problem found before expensive processing."""


def _available_memory_bytes() -> int | None:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        available_pages = os.sysconf("SC_AVPHYS_PAGES")
        return int(page_size) * int(available_pages)
    except (AttributeError, OSError, ValueError):
        return None


def _metadata_summary(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "available": False,
            "path": None,
            "gps": "NOT PROVIDED",
            "imu": "UNKNOWN",
            "camera_intrinsics": "UNKNOWN",
        }
    if not path.is_file():
        raise InputValidationError(f"Metadata file was requested but is not readable: {path}")
    result: dict[str, Any] = {
        "available": True,
        "path": str(path),
        "gps": "PRESENT (not yet validated)",
        "imu": "UNKNOWN",
        "camera_intrinsics": "UNKNOWN",
    }
    if path.suffix.lower() != ".json":
        return result
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputValidationError(f"Metadata JSON is invalid: {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise InputValidationError("Metadata JSON must contain an object at its top level.")
    result["imu"] = "AVAILABLE" if any(key.lower() in {"imu", "attitude", "orientation"} for key in document) else "NOT AVAILABLE"
    result["camera_intrinsics"] = "AVAILABLE" if any(key.lower() in {"intrinsics", "camera", "camera_parameters"} for key in document) else "UNKNOWN"
    return result


def inspect_video(
    video_path: str | Path,
    metadata_path: str | Path | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Validate a readable video and return a report without extracting it."""
    video = Path(video_path)
    allowed_extensions = {str(value).lower() for value in config["input"]["allowed_extensions"]}
    if not video.is_file():
        raise InputValidationError(f"Video file not found: {video}")
    if video.suffix.lower() not in allowed_extensions:
        choices = ", ".join(sorted(allowed_extensions))
        raise InputValidationError(f"Unsupported video extension {video.suffix!r}. Allowed: {choices}.")
    size_bytes = video.stat().st_size
    maximum = int(config["resource_limits"]["max_video_bytes"])
    if size_bytes > maximum:
        raise InputValidationError(
            f"Video is {size_bytes / 1024 / 1024:.1f} MiB, above the configured "
            f"{maximum / 1024 / 1024:.1f} MiB upload/run limit. Use a smaller input or increase resource_limits.max_video_bytes deliberately."
        )
    try:
        import cv2
    except ImportError as exc:
        raise InputValidationError("OpenCV is unavailable. Install the Python dependencies before validating a video.") from exc
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        capture.release()
        raise InputValidationError("Video cannot be opened. Check the codec/container and use a readable MP4, MOV, AVI, or MKV file.")
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count_raw = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        readable = 0
        for _ in range(3):
            ok, _frame = capture.read()
            if ok:
                readable += 1
        if width <= 0 or height <= 0 or fps <= 0 or readable == 0:
            raise InputValidationError("Video has no usable decoded frames or invalid resolution/FPS.")
    finally:
        capture.release()
    duration = frame_count_raw / fps if frame_count_raw > 0 else None
    target_fps = float(config["frame_selection"]["target_fps"])
    expected_selected = int((duration or 0) * min(fps, target_fps)) if duration else None
    max_selected = int(config["resource_limits"]["max_selected_frames"])
    resource_warnings: list[str] = []
    if expected_selected is not None and expected_selected > max_selected:
        if config["resource_limits"].get("adaptive_frame_sampling", False):
            resource_warnings.append(
                f"Expected selected frame count ({expected_selected}) exceeds the recommended budget ({max_selected}); adaptive sampling is enabled and will be reported in the run configuration."
            )
        else:
            raise InputValidationError(
                f"Expected selected frame count ({expected_selected}) exceeds the configured budget ({max_selected}). "
                "Lower frame_selection.target_fps or explicitly enable resource_limits.adaptive_frame_sampling."
            )
    disk = shutil.disk_usage(video.parent)
    minimum_free = int(config["resource_limits"]["minimum_free_disk_bytes"])
    if disk.free < minimum_free:
        resource_warnings.append(
            f"Only {disk.free / 1024 / 1024 / 1024:.1f} GiB storage is free; the configured minimum is {minimum_free / 1024 / 1024 / 1024:.1f} GiB."
        )
    metadata = _metadata_summary(Path(metadata_path) if metadata_path else None)
    return {
        "video": {
            "path": str(video),
            "filename": video.name,
            "extension": video.suffix.lower(),
            "size_bytes": size_bytes,
            "resolution": {"width": width, "height": height},
            "fps": round(fps, 4),
            "frame_count_container": frame_count_raw if frame_count_raw > 0 else None,
            "duration_seconds": round(duration, 4) if duration is not None else None,
            "readable_probe_frames": readable,
            "expected_selected_frames": expected_selected,
        },
        "metadata": metadata,
        "resources": {
            "cpu_count": os.cpu_count(),
            "available_memory_bytes": _available_memory_bytes(),
            "storage_free_bytes": disk.free,
            "storage_total_bytes": disk.total,
        },
        "warnings": resource_warnings,
    }
