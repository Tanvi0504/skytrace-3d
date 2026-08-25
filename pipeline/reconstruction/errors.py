"""Exceptions raised by SkyTrace's Step 2 reconstruction module."""

from __future__ import annotations

from pathlib import Path


class ReconstructionError(Exception):
    """Base class for expected reconstruction failures."""


class FramesDirectoryError(ReconstructionError):
    """Raised when the selected-frames directory is missing or invalid."""


class EmptyFramesDirectoryError(ReconstructionError):
    """Raised when a frames directory contains no supported image files."""


class InvalidImageFilesError(ReconstructionError):
    """Raised when one or more selected frame files cannot be decoded."""

    def __init__(self, invalid_files: list[Path]) -> None:
        self.invalid_files = invalid_files
        names = ", ".join(path.name for path in invalid_files)
        super().__init__(f"Invalid or unreadable image file(s): {names}")


class ColmapUnavailableError(ReconstructionError):
    """Raised when the requested COLMAP executable cannot be run."""


class UnsupportedBackendError(ReconstructionError):
    """Raised for a reconstruction backend that has not been implemented."""


class OutputDirectoryError(ReconstructionError):
    """Raised when the reconstruction workspace cannot safely be created."""


class ColmapCommandError(ReconstructionError):
    """Raised when an individual COLMAP command returns a non-zero status."""

    def __init__(
        self,
        stage: str,
        return_code: int,
        log_path: Path,
    ) -> None:
        self.stage = stage
        self.return_code = return_code
        self.log_path = log_path
        super().__init__(
            f"COLMAP {stage} failed with exit code {return_code}. "
            f"See log: {log_path}"
        )


class SparseModelNotFoundError(ReconstructionError):
    """Raised when COLMAP completes mapping but writes no sparse model."""

