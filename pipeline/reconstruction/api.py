"""Public API for SkyTrace Step 2 reconstruction."""

from __future__ import annotations

import json
import time
from pathlib import Path

from pipeline.reconstruction.backend import ReconstructionBackend
from pipeline.reconstruction.colmap import COLMAPBackend
from pipeline.reconstruction.errors import ReconstructionError, UnsupportedBackendError
from pipeline.reconstruction.models import ReconstructionConfig, ReconstructionResult
from pipeline.reconstruction.validation import (
    prepare_output_directory,
    validate_frames_directory,
)


def _get_backend(name: str) -> ReconstructionBackend:
    if name.lower() == "colmap":
        return COLMAPBackend()
    raise UnsupportedBackendError(
        f"Unsupported reconstruction backend: {name!r}. "
        "Available backends: colmap."
    )


def _write_metadata(result: ReconstructionResult, metadata_path: Path) -> None:
    result.metadata_path = metadata_path
    metadata_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")


def run_reconstruction(
    frames_dir: str | Path,
    output_dir: str | Path,
    backend: str = "colmap",
    dense: bool = True,
    *,
    colmap_executable: str = "colmap",
    matcher: str = "sequential",
    use_gpu: bool = False,
    sift_num_threads: int = 1,
    sift_max_image_size: int = 1600,
    max_image_size: int = 2000,
    single_camera: bool = True,
    overwrite: bool = False,
) -> ReconstructionResult:
    """Reconstruct selected Step 1 frames with the requested backend.

    A successful sparse reconstruction produces local, arbitrary-scale COLMAP
    coordinates. It does not provide georeferencing or a metric-accuracy claim.
    Dense MVS is attempted only when requested; dense failure is reported while
    preserving a successful sparse model.
    """
    started_at = time.monotonic()
    config: ReconstructionConfig | None = None
    image_count = 0
    try:
        config = ReconstructionConfig(
            frames_dir=Path(frames_dir),
            output_dir=Path(output_dir),
            dense=dense,
            colmap_executable=colmap_executable,
            matcher=matcher,
            use_gpu=use_gpu,
            sift_num_threads=sift_num_threads,
            sift_max_image_size=sift_max_image_size,
            max_image_size=max_image_size,
            single_camera=single_camera,
            overwrite=overwrite,
        )
        image_paths = validate_frames_directory(config.frames_dir)
        image_count = len(image_paths)
        selected_backend = _get_backend(backend)
        selected_backend.preflight(config)
        prepare_output_directory(
            config.output_dir,
            config.frames_dir,
            overwrite=config.overwrite,
        )
        result = selected_backend.run(config, image_paths)
    except (ReconstructionError, ValueError) as exc:
        result = ReconstructionResult(
            success=False,
            backend=backend,
            input_image_count=image_count,
            output_dir=config.output_dir if config is not None else Path(output_dir),
            dense_status="not_started" if dense else "not_requested",
            error=str(exc),
        )

    result.processing_time_seconds = time.monotonic() - started_at
    # A workspace may not exist for invalid inputs or a missing executable. If
    # it was created, persist the outcome so failed command runs are auditable.
    if config is not None and config.output_dir.is_dir():
        _write_metadata(result, config.metadata_path)
    return result
