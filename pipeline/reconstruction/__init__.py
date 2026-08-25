"""SkyTrace Step 2 baseline 3D reconstruction.

The public API consumes only the selected-frame directory created by Step 1:

    from pipeline.reconstruction import run_reconstruction
    result = run_reconstruction("outputs/example/frames", "outputs/example/reconstruction")
"""

from pipeline.reconstruction.api import run_reconstruction
from pipeline.reconstruction.backend import ReconstructionBackend
from pipeline.reconstruction.colmap import COLMAPBackend
from pipeline.reconstruction.errors import (
    ColmapCommandError,
    ColmapUnavailableError,
    EmptyFramesDirectoryError,
    FramesDirectoryError,
    InvalidImageFilesError,
    OutputDirectoryError,
    ReconstructionError,
    SparseModelNotFoundError,
    UnsupportedBackendError,
)
from pipeline.reconstruction.models import ReconstructionConfig, ReconstructionResult

__all__ = [
    "COLMAPBackend",
    "ColmapCommandError",
    "ColmapUnavailableError",
    "EmptyFramesDirectoryError",
    "FramesDirectoryError",
    "InvalidImageFilesError",
    "OutputDirectoryError",
    "ReconstructionBackend",
    "ReconstructionConfig",
    "ReconstructionError",
    "ReconstructionResult",
    "SparseModelNotFoundError",
    "UnsupportedBackendError",
    "run_reconstruction",
]

