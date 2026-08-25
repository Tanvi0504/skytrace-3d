from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from pipeline.reconstruction import run_reconstruction
from pipeline.reconstruction.colmap import (
    COLMAPBackend,
    parse_colmap_text_model,
    write_camera_poses,
)
from pipeline.reconstruction.errors import ColmapCommandError
from pipeline.reconstruction.models import ReconstructionConfig


def _write_valid_frame(frames_dir: Path, name: str = "frame_000000.jpg") -> Path:
    frames_dir.mkdir(parents=True, exist_ok=True)
    image_path = frames_dir / name
    image = np.full((24, 32, 3), 127, dtype=np.uint8)
    assert cv2.imwrite(str(image_path), image)
    return image_path


def _disable_preflight(monkeypatch) -> None:
    def no_preflight(self: COLMAPBackend, config: ReconstructionConfig) -> None:
        config.colmap_executable = "colmap"

    monkeypatch.setattr(COLMAPBackend, "preflight", no_preflight)


def test_missing_frames_directory_returns_structured_failure(tmp_path: Path) -> None:
    result = run_reconstruction(
        tmp_path / "missing",
        tmp_path / "reconstruction",
        dense=False,
    )

    assert not result.success
    assert result.input_image_count == 0
    assert "not found" in (result.error or "").lower()
    assert not (tmp_path / "reconstruction").exists()


def test_empty_frames_directory_returns_structured_failure(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    result = run_reconstruction(frames_dir, tmp_path / "reconstruction", dense=False)

    assert not result.success
    assert "no supported image" in (result.error or "").lower()


def test_invalid_image_file_returns_structured_failure(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    (frames_dir / "frame_000000.jpg").write_bytes(b"not an image")

    result = run_reconstruction(frames_dir, tmp_path / "reconstruction", dense=False)

    assert not result.success
    assert "invalid or unreadable" in (result.error or "").lower()


def test_colmap_command_failure_is_logged_and_reported(
    tmp_path: Path, monkeypatch
) -> None:
    frames_dir = tmp_path / "frames"
    _write_valid_frame(frames_dir)
    _disable_preflight(monkeypatch)

    def fail_feature_extraction(
        self: COLMAPBackend, stage: str, command: list[str], logs_dir: Path
    ) -> None:
        log_path = logs_dir / f"{stage}.log"
        log_path.write_text("simulated COLMAP failure")
        raise ColmapCommandError(stage, 9, log_path)

    monkeypatch.setattr(COLMAPBackend, "_execute", fail_feature_extraction)
    output_dir = tmp_path / "reconstruction"
    result = run_reconstruction(frames_dir, output_dir, dense=False)

    assert not result.success
    assert result.input_image_count == 1
    assert "feature_extractor" in (result.error or "")
    assert (output_dir / "logs" / "feature_extractor.log").is_file()
    metadata = json.loads((output_dir / "reconstruction_metadata.json").read_text())
    assert metadata["success"] is False
    assert metadata["error"] == result.error


def test_command_generation_uses_selected_frames_and_cpu_by_default(tmp_path: Path) -> None:
    config = ReconstructionConfig(
        frames_dir=tmp_path / "frames",
        output_dir=tmp_path / "reconstruction",
    )
    backend = COLMAPBackend()

    feature = backend.build_feature_command(config)
    matcher = backend.build_match_command(config)
    mapper = backend.build_mapper_command(config)

    assert feature[:2] == ["colmap", "feature_extractor"]
    assert str(config.frames_dir) in feature
    assert feature[feature.index("--SiftExtraction.use_gpu") + 1] == "0"
    assert matcher[:2] == ["colmap", "sequential_matcher"]
    assert mapper[:2] == ["colmap", "mapper"]
    assert str(config.sparse_models_dir) in mapper


def test_colmap_text_result_parsing_and_pose_export(tmp_path: Path) -> None:
    model_dir = tmp_path / "text_model"
    model_dir.mkdir()
    (model_dir / "images.txt").write_text(
        "# Image list\n"
        "1 1 0 0 0 1 2 3 7 frame_000000.jpg\n"
        "\n"
        "2 1 0 0 0 0 0 0 7 frame_000006.jpg\n"
        "\n"
    )
    (model_dir / "points3D.txt").write_text(
        "# 3D point list\n"
        "1 1.0 2.0 3.0 255 0 0 0.1 1 0\n"
        "2 4.0 5.0 6.0 0 255 0 0.2 2 0\n"
    )

    stats = parse_colmap_text_model(model_dir)
    poses_path = tmp_path / "camera_poses.json"
    write_camera_poses(poses_path, stats.poses)

    assert stats.registered_image_count == 2
    assert stats.sparse_point_count == 2
    assert stats.poses[0]["camera_center_world"] == [-1.0, -2.0, -3.0]
    pose_document = json.loads(poses_path.read_text())
    assert pose_document["scale"] == "arbitrary; not metric or georeferenced"
    assert len(pose_document["poses"]) == 2


def test_dense_failure_preserves_sparse_output(tmp_path: Path, monkeypatch) -> None:
    frames_dir = tmp_path / "frames"
    _write_valid_frame(frames_dir)
    _disable_preflight(monkeypatch)

    def simulated_colmap(
        self: COLMAPBackend, stage: str, command: list[str], logs_dir: Path
    ) -> None:
        if stage == "mapper":
            model_dir = Path(command[command.index("--output_path") + 1]) / "0"
            model_dir.mkdir(parents=True)
            (model_dir / "cameras.bin").write_bytes(b"simulated")
        elif stage.startswith("model_converter_text_"):
            text_dir = Path(command[command.index("--output_path") + 1])
            text_dir.mkdir(parents=True, exist_ok=True)
            (text_dir / "images.txt").write_text(
                "1 1 0 0 0 0 0 0 1 frame_000000.jpg\n\n"
            )
            (text_dir / "points3D.txt").write_text("1 0 0 0 0 0 0 0\n")
        elif stage == "model_converter_ply":
            Path(command[command.index("--output_path") + 1]).write_text("ply\n")
        elif stage == "image_undistorter":
            log_path = logs_dir / "image_undistorter.log"
            log_path.write_text("simulated dense failure")
            raise ColmapCommandError(stage, 3, log_path)

    monkeypatch.setattr(COLMAPBackend, "_execute", simulated_colmap)
    result = run_reconstruction(frames_dir, tmp_path / "reconstruction", dense=True)

    assert result.success
    assert result.dense_status == "failed"
    assert result.sparse_point_cloud_path is not None
    assert result.sparse_point_cloud_path.is_file()
    assert result.dense_error is not None
