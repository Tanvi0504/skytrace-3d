"""COLMAP implementation of SkyTrace's baseline reconstruction backend."""

from __future__ import annotations

import json
import math
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pipeline.reconstruction.backend import ReconstructionBackend
from pipeline.reconstruction.errors import (
    ColmapCommandError,
    ColmapUnavailableError,
    ReconstructionError,
    SparseModelNotFoundError,
)
from pipeline.reconstruction.models import ReconstructionConfig, ReconstructionResult


@dataclass
class SparseModelStats:
    """Counts and pose records parsed from COLMAP's text model export."""

    registered_image_count: int
    sparse_point_count: int
    poses: list[dict]


def _bool_argument(value: bool) -> str:
    return "1" if value else "0"


def _command_text(command: list[str]) -> str:
    """Render a subprocess argument list safely for a human-readable log."""
    return shlex.join(command)


def _quaternion_to_rotation_matrix(qvec: list[float]) -> list[list[float]]:
    """Convert COLMAP's normalized ``[qw, qx, qy, qz]`` quaternion to R."""
    qw, qx, qy, qz = qvec
    norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if norm == 0:
        raise ValueError("COLMAP image pose has a zero-length quaternion")
    qw, qx, qy, qz = (value / norm for value in (qw, qx, qy, qz))
    return [
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ]


def _camera_center(rotation: list[list[float]], translation: list[float]) -> list[float]:
    """Return C = -R^T t for COLMAP's world-to-camera image transform."""
    return [
        -sum(rotation[row][column] * translation[row] for row in range(3))
        for column in range(3)
    ]


def parse_colmap_text_model(text_model_dir: Path) -> SparseModelStats:
    """Parse registration counts, 3D-point counts, and poses from COLMAP TXT."""
    images_path = text_model_dir / "images.txt"
    points_path = text_model_dir / "points3D.txt"
    if not images_path.is_file() or not points_path.is_file():
        raise SparseModelNotFoundError(
            f"COLMAP text model export is incomplete: {text_model_dir}"
        )

    poses: list[dict] = []
    image_lines = images_path.read_text(encoding="utf-8").splitlines()
    line_index = 0
    while line_index < len(image_lines):
        line = image_lines[line_index].strip()
        line_index += 1
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 10:
            continue
        try:
            image_id = int(fields[0])
            qvec = [float(value) for value in fields[1:5]]
            tvec = [float(value) for value in fields[5:8]]
            camera_id = int(fields[8])
        except ValueError:
            continue
        rotation = _quaternion_to_rotation_matrix(qvec)
        poses.append(
            {
                "image_id": image_id,
                "image_name": " ".join(fields[9:]),
                "camera_id": camera_id,
                "qvec_world_to_camera": qvec,
                "tvec_world_to_camera": tvec,
                "camera_center_world": _camera_center(rotation, tvec),
            }
        )
        # Each image-pose line is followed by its 2D observation line, which
        # may be empty. Consume exactly that record without interpreting it.
        if line_index < len(image_lines):
            line_index += 1

    sparse_point_count = sum(
        1
        for line in points_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return SparseModelStats(
        registered_image_count=len(poses),
        sparse_point_count=sparse_point_count,
        poses=poses,
    )


def write_camera_poses(path: Path, poses: list[dict]) -> None:
    """Write parsed COLMAP poses with their coordinate convention documented."""
    payload = {
        "coordinate_system": "COLMAP local reconstruction coordinates",
        "scale": "arbitrary; not metric or georeferenced",
        "pose_convention": (
            "qvec_world_to_camera and tvec_world_to_camera satisfy "
            "x_camera = R(qvec) * x_world + tvec"
        ),
        "poses": poses,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class COLMAPBackend(ReconstructionBackend):
    """Run a conventional COLMAP SfM pipeline and optional dense MVS pass."""

    name = "colmap"

    def preflight(self, config: ReconstructionConfig) -> None:
        executable = config.colmap_executable
        executable_path = Path(executable).expanduser()
        if executable_path.parent != Path("."):
            if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
                raise ColmapUnavailableError(
                    f"COLMAP executable is not runnable: {executable}. "
                    "Install COLMAP or pass its path with --colmap-executable."
                )
            config.colmap_executable = str(executable_path)
            return

        resolved = shutil.which(executable)
        if resolved is None:
            raise ColmapUnavailableError(
                "COLMAP was not found on PATH. Install COLMAP and ensure the "
                "'colmap' executable is accessible, or pass --colmap-executable."
            )
        config.colmap_executable = resolved

    def build_feature_command(self, config: ReconstructionConfig) -> list[str]:
        command = [
            config.colmap_executable,
            "feature_extractor",
            "--database_path",
            str(config.database_path),
            "--image_path",
            str(config.frames_dir),
            "--ImageReader.single_camera",
            _bool_argument(config.single_camera),
            "--SiftExtraction.use_gpu",
            _bool_argument(config.use_gpu),
            "--SiftExtraction.num_threads",
            str(config.sift_num_threads),
            "--SiftExtraction.max_image_size",
            str(config.sift_max_image_size),
        ]
        return command

    def build_match_command(self, config: ReconstructionConfig) -> list[str]:
        command = [
            config.colmap_executable,
            f"{config.matcher}_matcher",
            "--database_path",
            str(config.database_path),
            "--SiftMatching.use_gpu",
            _bool_argument(config.use_gpu),
            "--SiftMatching.num_threads",
            str(config.sift_num_threads),
        ]
        return command

    def build_mapper_command(self, config: ReconstructionConfig) -> list[str]:
        return [
            config.colmap_executable,
            "mapper",
            "--database_path",
            str(config.database_path),
            "--image_path",
            str(config.frames_dir),
            "--output_path",
            str(config.sparse_models_dir),
        ]

    def build_model_converter_command(
        self,
        config: ReconstructionConfig,
        input_path: Path,
        output_path: Path,
        output_type: str,
    ) -> list[str]:
        return [
            config.colmap_executable,
            "model_converter",
            "--input_path",
            str(input_path),
            "--output_path",
            str(output_path),
            "--output_type",
            output_type,
        ]

    def build_dense_commands(
        self,
        config: ReconstructionConfig,
        sparse_model_dir: Path,
    ) -> list[tuple[str, list[str]]]:
        return [
            (
                "image_undistorter",
                [
                    config.colmap_executable,
                    "image_undistorter",
                    "--image_path",
                    str(config.frames_dir),
                    "--input_path",
                    str(sparse_model_dir),
                    "--output_path",
                    str(config.dense_dir),
                    "--output_type",
                    "COLMAP",
                    "--max_image_size",
                    str(config.max_image_size),
                ],
            ),
            (
                "patch_match_stereo",
                [
                    config.colmap_executable,
                    "patch_match_stereo",
                    "--workspace_path",
                    str(config.dense_dir),
                    "--workspace_format",
                    "COLMAP",
                    "--PatchMatchStereo.geom_consistency",
                    "true",
                ],
            ),
            (
                "stereo_fusion",
                [
                    config.colmap_executable,
                    "stereo_fusion",
                    "--workspace_path",
                    str(config.dense_dir),
                    "--workspace_format",
                    "COLMAP",
                    "--input_type",
                    "geometric",
                    "--output_path",
                    str(config.dense_point_cloud_path),
                ],
            ),
        ]

    def _execute(self, stage: str, command: list[str], logs_dir: Path) -> None:
        """Run one COLMAP command and preserve stdout/stderr in a stage log."""
        log_path = logs_dir / f"{stage}.log"
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            log_path.write_text(
                f"$ {_command_text(command)}\n\nUnable to start COLMAP: {exc}\n",
                encoding="utf-8",
            )
            raise ColmapCommandError(stage, -1, log_path) from exc

        log_path.write_text(
            "\n".join(
                [
                    f"$ {_command_text(command)}",
                    f"\nExit code: {completed.returncode}",
                    "\n--- stdout ---",
                    completed.stdout or "",
                    "\n--- stderr ---",
                    completed.stderr or "",
                ]
            ),
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise ColmapCommandError(stage, completed.returncode, log_path)

    @staticmethod
    def _find_sparse_models(models_dir: Path) -> list[Path]:
        if not models_dir.is_dir():
            return []
        return sorted(
            (
                path
                for path in models_dir.iterdir()
                if path.is_dir()
                and (
                    (path / "cameras.bin").is_file()
                    or (path / "cameras.txt").is_file()
                )
            ),
            key=lambda path: path.name,
        )

    def _export_and_select_sparse_model(
        self,
        config: ReconstructionConfig,
    ) -> tuple[Path, SparseModelStats]:
        model_paths = self._find_sparse_models(config.sparse_models_dir)
        if not model_paths:
            raise SparseModelNotFoundError(
                "COLMAP mapper completed but did not create a sparse model. "
                f"See logs in {config.logs_dir}."
            )

        candidates: list[tuple[Path, Path, SparseModelStats]] = []
        for model_path in model_paths:
            text_path = config.sparse_text_dir / model_path.name
            text_path.mkdir(parents=True, exist_ok=True)
            self._execute(
                f"model_converter_text_{model_path.name}",
                self.build_model_converter_command(
                    config, model_path, text_path, "TXT"
                ),
                config.logs_dir,
            )
            candidates.append(
                (model_path, text_path, parse_colmap_text_model(text_path))
            )

        model_path, text_path, stats = max(
            candidates,
            key=lambda candidate: (
                candidate[2].registered_image_count,
                candidate[2].sparse_point_count,
            ),
        )
        self._execute(
            "model_converter_ply",
            self.build_model_converter_command(
                config, model_path, config.sparse_ply_path, "PLY"
            ),
            config.logs_dir,
        )
        write_camera_poses(config.camera_poses_path, stats.poses)
        return model_path, stats

    def run(
        self,
        config: ReconstructionConfig,
        image_paths: list[Path],
    ) -> ReconstructionResult:
        """Execute sparse SfM, then attempt dense MVS without losing sparse output."""
        config.logs_dir.mkdir(parents=True, exist_ok=True)
        config.sparse_models_dir.mkdir(parents=True, exist_ok=True)
        config.sparse_text_dir.mkdir(parents=True, exist_ok=True)

        self._execute("feature_extractor", self.build_feature_command(config), config.logs_dir)
        self._execute("feature_matcher", self.build_match_command(config), config.logs_dir)
        self._execute("mapper", self.build_mapper_command(config), config.logs_dir)
        sparse_model_dir, sparse_stats = self._export_and_select_sparse_model(config)

        result = ReconstructionResult(
            success=True,
            backend=self.name,
            input_image_count=len(image_paths),
            registered_image_count=sparse_stats.registered_image_count,
            sparse_point_count=sparse_stats.sparse_point_count,
            dense_status="not_requested" if not config.dense else "pending",
            output_dir=config.output_dir,
            database_path=config.database_path,
            sparse_model_dir=sparse_model_dir,
            sparse_text_dir=config.sparse_text_dir / sparse_model_dir.name,
            sparse_point_cloud_path=config.sparse_ply_path,
            camera_poses_path=config.camera_poses_path,
            dense_dir=config.dense_dir if config.dense else None,
            dense_point_cloud_path=(
                config.dense_point_cloud_path if config.dense else None
            ),
            logs_dir=config.logs_dir,
        )
        if not config.dense:
            return result

        try:
            config.dense_dir.mkdir(parents=True, exist_ok=True)
            for stage, command in self.build_dense_commands(config, sparse_model_dir):
                self._execute(stage, command, config.logs_dir)
            result.dense_status = "completed"
        except (OSError, ReconstructionError) as exc:
            # Sparse output remains usable by design.
            result.dense_status = "failed"
            result.dense_error = str(exc)
            result.warnings.append(
                "Dense reconstruction failed after sparse SfM completed. "
                "The sparse model, point cloud, poses, and command logs were preserved."
            )
        return result
