"""Typed configuration and result objects for Step 2 reconstruction."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ReconstructionConfig:
    """Configuration shared by reconstruction backends.

    The input is deliberately only a selected-frame directory. This keeps
    Step 2 independent of the video ingestion implementation from Step 1.
    """

    frames_dir: Path
    output_dir: Path
    dense: bool = True
    colmap_executable: str = "colmap"
    matcher: str = "sequential"
    use_gpu: bool = False
    sift_num_threads: int = 1
    sift_max_image_size: int = 1600
    max_image_size: int = 2000
    single_camera: bool = True
    overwrite: bool = False

    def __post_init__(self) -> None:
        self.frames_dir = Path(self.frames_dir)
        self.output_dir = Path(self.output_dir)
        if self.matcher not in {"sequential", "exhaustive"}:
            raise ValueError(
                "matcher must be 'sequential' or 'exhaustive', "
                f"got {self.matcher!r}"
            )
        if self.max_image_size <= 0:
            raise ValueError(
                f"max_image_size must be > 0, got {self.max_image_size}"
            )
        if self.sift_num_threads <= 0:
            raise ValueError(
                f"sift_num_threads must be > 0, got {self.sift_num_threads}"
            )
        if self.sift_max_image_size <= 0:
            raise ValueError(
                "sift_max_image_size must be > 0, "
                f"got {self.sift_max_image_size}"
            )

    @property
    def database_path(self) -> Path:
        return self.output_dir / "database.db"

    @property
    def sparse_models_dir(self) -> Path:
        return self.output_dir / "sparse" / "models"

    @property
    def sparse_text_dir(self) -> Path:
        return self.output_dir / "sparse" / "text"

    @property
    def sparse_ply_path(self) -> Path:
        return self.output_dir / "sparse" / "sparse.ply"

    @property
    def camera_poses_path(self) -> Path:
        return self.output_dir / "camera_poses.json"

    @property
    def dense_dir(self) -> Path:
        return self.output_dir / "dense"

    @property
    def dense_point_cloud_path(self) -> Path:
        return self.dense_dir / "fused.ply"

    @property
    def logs_dir(self) -> Path:
        return self.output_dir / "logs"

    @property
    def metadata_path(self) -> Path:
        return self.output_dir / "reconstruction_metadata.json"


@dataclass
class ReconstructionResult:
    """Structured outcome of a reconstruction attempt.

    ``success`` reflects sparse reconstruction, the required baseline. A
    dense failure therefore leaves ``success`` true if a usable sparse model
    was produced; inspect ``dense_status`` and ``dense_error`` separately.
    Coordinates are COLMAP's local, arbitrary-scale reconstruction frame and
    are not georeferenced or metric by implication.
    """

    success: bool
    backend: str
    input_image_count: int
    output_dir: Path
    registered_image_count: Optional[int] = None
    sparse_point_count: Optional[int] = None
    dense_status: str = "not_requested"
    processing_time_seconds: float = 0.0
    database_path: Optional[Path] = None
    sparse_model_dir: Optional[Path] = None
    sparse_text_dir: Optional[Path] = None
    sparse_point_cloud_path: Optional[Path] = None
    camera_poses_path: Optional[Path] = None
    dense_dir: Optional[Path] = None
    dense_point_cloud_path: Optional[Path] = None
    metadata_path: Optional[Path] = None
    logs_dir: Optional[Path] = None
    error: Optional[str] = None
    dense_error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the result."""

        def path_string(path: Optional[Path]) -> Optional[str]:
            return str(path) if path is not None else None

        return {
            "success": self.success,
            "backend": self.backend,
            "input_image_count": self.input_image_count,
            "registered_image_count": self.registered_image_count,
            "sparse_point_count": self.sparse_point_count,
            "dense_status": self.dense_status,
            "processing_time_seconds": round(self.processing_time_seconds, 4),
            "output_locations": {
                "output_dir": path_string(self.output_dir),
                "database": path_string(self.database_path),
                "sparse_model": path_string(self.sparse_model_dir),
                "sparse_text": path_string(self.sparse_text_dir),
                "sparse_point_cloud": path_string(self.sparse_point_cloud_path),
                "camera_poses": path_string(self.camera_poses_path),
                "dense_dir": path_string(self.dense_dir),
                "dense_point_cloud": path_string(self.dense_point_cloud_path),
                "logs": path_string(self.logs_dir),
            },
            "error": self.error,
            "dense_error": self.dense_error,
            "warnings": self.warnings,
        }
