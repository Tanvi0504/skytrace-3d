"""One resilient, checkpointed orchestration entry point for Steps 1-6."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from pipeline.analysis.api import analyze_georeferenced_scene
from pipeline.analysis.models import EvidenceConfig
from pipeline.georeferencing.api import georeference_reconstruction
from pipeline.objects.api import detect_and_track_objects
from pipeline.reconstruction.api import run_reconstruction
from pipeline.scene_objects.api import associate_objects_with_3d_scene
from pipeline.video import VideoProcessingConfig, process_video

from skytrace.configuration import configuration_for_report
from skytrace.observability import RunObserver, STAGE_NAMES, all_files, utc_now, write_json, write_report
from skytrace.validation import InputValidationError, inspect_video


StageCallback = Callable[[int, str, dict[str, Any], list[str], str | None], None]


@dataclass
class PipelineOutcome:
    run_id: str
    directory: Path
    status: str
    first_failed_stage: int | None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    manifest_path: Path | None = None
    report_json_path: Path | None = None
    report_html_path: Path | None = None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return document if isinstance(document, dict) else {}


def _artifact_exists(directory: Path, relative: str) -> bool:
    try:
        candidate = (directory / relative).resolve()
        return candidate.is_file() and directory.resolve() in candidate.parents
    except (OSError, ValueError):
        return False


def validate_stage_output(directory: Path, stage: int) -> tuple[bool, str, list[Path]]:
    """Validate outputs required for a checkpoint; a marker alone is never trusted."""
    checks: dict[int, tuple[list[Path], callable]] = {
        1: (
            [directory / "metadata.json", directory / "frame_manifest.json"],
            lambda: any((directory / "frames").glob("*.jpg")),
        ),
        2: (
            [directory / "reconstruction" / "reconstruction_metadata.json", directory / "reconstruction" / "camera_poses.json"],
            lambda: any(
                path.is_file()
                for path in (
                    directory / "reconstruction" / "dense" / "fused.ply",
                    directory / "reconstruction" / "sparse" / "sparse.ply",
                )
            ) and bool(_read_json(directory / "reconstruction" / "reconstruction_metadata.json").get("success")),
        ),
        3: (
            [directory / "georeferenced" / "georef_metadata.json", directory / "georeferenced" / "transform.json", directory / "georeferenced" / "point_cloud_georef.ply"],
            lambda: bool(_read_json(directory / "georeferenced" / "georef_metadata.json").get("success")),
        ),
        4: (
            [directory / "objects" / "object_metadata.json", directory / "objects" / "detections.json", directory / "objects" / "tracks.json"],
            lambda: bool(_read_json(directory / "objects" / "object_metadata.json").get("success")),
        ),
        5: (
            [directory / "scene_objects" / "objects_3d.json", directory / "scene_objects" / "association_metadata.json"],
            lambda: bool(_read_json(directory / "scene_objects" / "association_metadata.json").get("success")),
        ),
        6: (
            [directory / "analysis" / "quality_metadata.json", directory / "analysis" / "evidence_map" / "quality_grid.json"],
            lambda: bool(_read_json(directory / "analysis" / "quality_metadata.json").get("success")),
        ),
    }
    required, semantic_check = checks[stage]
    missing = [path.relative_to(directory).as_posix() for path in required if not path.is_file()]
    if missing:
        return False, f"missing required output(s): {', '.join(missing)}", required
    if not semantic_check():
        return False, "metadata does not declare a usable successful output", required
    return True, "validated", required


class PipelineOrchestrator:
    """Coordinates existing modules and owns only Step 10 operational concerns."""

    def __init__(
        self,
        *,
        run_id: str,
        directory: str | Path,
        video_path: str | Path,
        metadata_path: str | Path | None,
        config: dict[str, Any],
        resume: bool = False,
        callback: StageCallback | None = None,
    ) -> None:
        self.run_id = run_id
        self.directory = Path(directory)
        self.video_path = Path(video_path)
        self.metadata_path = Path(metadata_path) if metadata_path else None
        self.config = config
        self.resume = resume
        self.callback = callback
        self.observer = RunObserver(run_id, self.directory)
        self.warnings: list[str] = []
        self.first_failed_stage: int | None = None
        self.input_report: dict[str, Any] = {}

    def _notify(self, stage: int, status: str, summary: dict[str, Any] | None = None, warnings: list[str] | None = None, error: str | None = None) -> None:
        if self.callback:
            self.callback(stage, status, summary or {}, warnings or [], error)

    def _resumable(self, stage: int) -> bool:
        if not self.resume:
            return False
        checkpoint = self.observer.checkpoint_document(stage)
        if checkpoint is None:
            return False
        if checkpoint.get("run_id") != self.run_id or checkpoint.get("stage") != stage:
            self.observer.invalidate_checkpoint(stage, "run or stage identity does not match")
            return False
        artifacts = checkpoint.get("artifacts")
        if not isinstance(artifacts, list) or not all(isinstance(item, str) and _artifact_exists(self.directory, item) for item in artifacts):
            self.observer.invalidate_checkpoint(stage, "checkpoint artifact list is missing or invalid")
            return False
        valid, reason, _required = validate_stage_output(self.directory, stage)
        if not valid:
            self.observer.invalidate_checkpoint(stage, reason)
            return False
        started = self.observer.start(stage)
        note = "Checkpoint and required outputs were validated; expensive stage was not recomputed."
        self.observer.finish(stage, started, status="SKIPPED", summary={"resumed": True}, warnings=[note])
        if stage == 1:
            self.input_report = _read_json(self.directory / "input_report.json")
        self._notify(stage, "COMPLETED", {"resumed": True}, [note])
        self.warnings.append(f"Step {stage} resumed from a validated checkpoint.")
        return True

    def _complete_stage(self, stage: int, started: float, summary: dict[str, Any], warnings: list[str], artifacts: list[Path]) -> None:
        status = "WARNING" if warnings else "OK"
        self.observer.finish(stage, started, status=status, summary=summary, warnings=warnings)
        self.observer.checkpoint(stage, artifacts)
        self._notify(stage, "COMPLETED", summary, warnings)
        self.warnings.extend(warnings)

    def _fail_stage(self, stage: int, started: float, error: str, warnings: list[str] | None = None) -> None:
        self.observer.finish(stage, started, status="FAILED", warnings=warnings or [], error=error)
        self._notify(stage, "FAILED", {}, warnings or [], error)
        self.first_failed_stage = self.first_failed_stage or stage

    def _skip_stage(self, stage: int, reason: str) -> None:
        started = self.observer.start(stage)
        self.observer.finish(stage, started, status="SKIPPED", warnings=[reason])
        self._notify(stage, "COMPLETED", {"skipped": True}, [reason])
        self.warnings.append(f"Step {stage}: {reason}")

    def run(self) -> PipelineOutcome:
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            if not self._resumable(1):
                self._run_stage_1()
            if self.first_failed_stage is None and not self._resumable(2):
                self._run_stage_2()
            geo_available = (self.directory / "georeferenced" / "transform.json").is_file()
            if self.first_failed_stage is None and not self._resumable(3):
                geo_available = self._run_stage_3()
            if self.first_failed_stage is None and not self._resumable(4):
                self._run_stage_4()
            if self.first_failed_stage is None and not self._resumable(5):
                self._run_stage_5(geo_available)
            if self.first_failed_stage is None and not self._resumable(6):
                self._run_stage_6(geo_available)
        except Exception as exc:  # A final guard makes every unexpected failure observable.
            stage = self.first_failed_stage or self._active_stage()
            if self.first_failed_stage is None:
                self._fail_stage(stage, time.monotonic(), str(exc))
        outcome = self._package()
        self.observer.close()
        return outcome

    def _active_stage(self) -> int:
        running = [int(key) for key, value in self.observer.stages.items() if value.get("status") == "RUNNING"]
        return running[-1] if running else 1

    def _run_stage_1(self) -> None:
        started = self.observer.start(1)
        self._notify(1, "RUNNING")
        try:
            self.input_report = inspect_video(self.video_path, self.metadata_path, self.config)
            write_json(self.directory / "input_report.json", self.input_report)
            video_cfg = self.config["frame_selection"]
            target_fps = float(video_cfg["target_fps"])
            expected = self.input_report["video"].get("expected_selected_frames")
            limit = int(self.config["resource_limits"]["max_selected_frames"])
            if expected and expected > limit and self.config["resource_limits"].get("adaptive_frame_sampling", False):
                duration = float(self.input_report["video"]["duration_seconds"])
                target_fps = min(target_fps, limit / duration)
                self.input_report["effective_target_fps"] = target_fps
                self.input_report["warnings"].append(
                    f"Adaptive frame sampling lowered target FPS to {target_fps:.3f}; source video was not altered."
                )
                write_json(self.directory / "input_report.json", self.input_report)
            result = process_video(
                VideoProcessingConfig(
                    video_path=self.video_path,
                    output_dir=self.directory,
                    target_fps=target_fps,
                    blur_threshold=float(video_cfg["blur_threshold"]),
                    jpeg_quality=int(video_cfg["jpeg_quality"]),
                    run_id=self.run_id,
                )
            )
            minimum = int(self.config["reconstruction"]["minimum_selected_frames"])
            if result.selected_count < minimum:
                raise InputValidationError(
                    f"Only {result.selected_count} sharp frames were selected; at least {minimum} are required for reconstruction. "
                    "Use a less blurred video, reduce blur_threshold after review, or capture more overlap."
                )
            warnings = list(self.input_report.get("warnings", []))
            self._complete_stage(
                1,
                started,
                {
                    "sampled_frames": result.sampled_count,
                    "selected_frames": result.selected_count,
                    "rejected_frames": result.rejected_count,
                    "processing_time_seconds": result.processing_time_seconds,
                },
                warnings,
                [self.directory / "metadata.json", self.directory / "frame_manifest.json"],
            )
        except Exception as exc:
            self._fail_stage(1, started, str(exc))

    def _run_stage_2(self) -> None:
        started = self.observer.start(2)
        self._notify(2, "RUNNING")
        cfg = self.config["reconstruction"]
        result = run_reconstruction(
            self.directory / "frames",
            self.directory / "reconstruction",
            backend=str(cfg["backend"]),
            dense=bool(cfg["dense"]),
            colmap_executable=str(cfg["colmap_executable"]),
            matcher=str(cfg["matcher"]),
            use_gpu=bool(cfg["use_gpu"]),
            sift_num_threads=int(cfg["sift_num_threads"]),
            sift_max_image_size=int(cfg["sift_max_image_size"]),
            max_image_size=int(cfg["max_image_size"]),
            single_camera=bool(cfg["single_camera"]),
            overwrite=bool(cfg["overwrite_stage_outputs"]),
        )
        if not result.success:
            self._fail_stage(2, started, result.error or "COLMAP reconstruction failed.", result.warnings)
            return
        warnings = list(result.warnings)
        if result.dense_status == "failed":
            warnings.append("Dense reconstruction failed; the successful sparse reconstruction is retained.")
        self._complete_stage(
            2,
            started,
            {
                "input_images": result.input_image_count,
                "registered_images": result.registered_image_count,
                "sparse_points": result.sparse_point_count,
                "dense_status": result.dense_status,
                "processing_time_seconds": result.processing_time_seconds,
            },
            warnings,
            [self.directory / "reconstruction" / "reconstruction_metadata.json", self.directory / "reconstruction" / "camera_poses.json"],
        )

    def _run_stage_3(self) -> bool:
        if self.metadata_path is None:
            self._skip_stage(3, "GPS metadata was not supplied; continuing with local reconstruction coordinates. Metric georeferencing and Step 6 measurements are unavailable.")
            return False
        started = self.observer.start(3)
        self._notify(3, "RUNNING")
        cfg = self.config["georeferencing"]
        result = georeference_reconstruction(
            self.directory / "reconstruction",
            self.metadata_path,
            self.directory / "georeferenced",
            timestamp_tolerance_seconds=float(cfg["timestamp_tolerance_seconds"]),
            ransac_threshold_metres=float(cfg["ransac_threshold_metres"]),
            ransac_iterations=int(cfg["ransac_iterations"]),
            source_scale_mode=str(cfg["source_scale_mode"]),
            overwrite=bool(cfg["overwrite_stage_outputs"]),
        )
        if not result.success:
            reason = result.error or "Georeferencing failed."
            if bool(cfg["continue_without_gps"]):
                self._skip_stage(3, f"Georeferencing unavailable: {reason} Local reconstruction processing continues; no metric measurement will be reported.")
                return False
            self._fail_stage(3, started, reason, result.warnings)
            return False
        self._complete_stage(
            3,
            started,
            {
                "gps_observations": result.gps_observation_count,
                "matched_poses": result.matched_pose_count,
                "inliers": result.inlier_count,
                "estimated_scale": result.estimated_scale,
                "processing_time_seconds": result.processing_time_seconds,
            },
            result.warnings,
            [self.directory / "georeferenced" / "georef_metadata.json", self.directory / "georeferenced" / "transform.json", self.directory / "georeferenced" / "point_cloud_georef.ply"],
        )
        return True

    def _run_stage_4(self) -> None:
        started = self.observer.start(4)
        self._notify(4, "RUNNING")
        cfg = self.config["object_detection"]
        model_path = Path(str(cfg["model_path"]))
        if not model_path.is_file():
            self._fail_stage(
                4,
                started,
                f"Required model weights are missing: {model_path}. Run `python -m skytrace.setup_models` while online, or copy the documented file into models/ for offline setup.",
            )
            return
        result = detect_and_track_objects(
            self.directory / "frames",
            self.directory / "objects",
            model_name=str(model_path),
            confidence_threshold=float(cfg["confidence_threshold"]),
            iou_threshold=float(cfg["iou_threshold"]),
            classes=cfg.get("classes"),
            tracking=bool(cfg["tracking"]),
            tracker_config=str(cfg["tracker_config"]),
            device=str(cfg["device"]),
            mask_padding_pixels=int(cfg["mask_padding_pixels"]),
            overwrite=bool(cfg["overwrite_stage_outputs"]),
        )
        if not result.success:
            self._fail_stage(4, started, result.error or "Object detection failed.", result.warnings)
            return
        self._complete_stage(
            4,
            started,
            {
                "frames_processed": result.frames_processed,
                "frames_failed": result.frames_failed,
                "detected_objects": result.detection_count,
                "tracks": result.track_count,
                "processing_time_seconds": result.processing_time_seconds,
            },
            result.warnings,
            [self.directory / "objects" / "object_metadata.json", self.directory / "objects" / "detections.json", self.directory / "objects" / "tracks.json"],
        )

    def _run_stage_5(self, geo_available: bool) -> None:
        started = self.observer.start(5)
        self._notify(5, "RUNNING")
        cfg = self.config["object_association"]
        result = associate_objects_with_3d_scene(
            self.directory / "objects",
            self.directory / "reconstruction",
            self.directory / "scene_objects",
            georeferenced_dir=self.directory / "georeferenced" if geo_available else None,
            minimum_ray_angle_degrees=float(cfg["minimum_ray_angle_degrees"]),
            max_normalized_ray_residual=float(cfg["max_normalized_ray_residual"]),
            max_condition_number=float(cfg["max_condition_number"]),
            overwrite=bool(cfg["overwrite_stage_outputs"]),
        )
        if not result.success:
            self._fail_stage(5, started, result.error or "3D association failed.", result.warnings)
            return
        warnings = list(result.warnings)
        if not geo_available:
            warnings.append("Object coordinates remain in the local reconstruction frame because georeferencing is unavailable.")
        self._complete_stage(
            5,
            started,
            {
                "tracks": result.track_count,
                "estimated": result.estimated_count,
                "low_confidence": result.low_confidence_count,
                "unavailable": result.unavailable_count,
                "processing_time_seconds": result.processing_time_seconds,
            },
            warnings,
            [self.directory / "scene_objects" / "objects_3d.json", self.directory / "scene_objects" / "association_metadata.json"],
        )

    def _run_stage_6(self, geo_available: bool) -> None:
        if not geo_available:
            self._skip_stage(6, "Skipped because a valid georeferenced metre-valued scene is unavailable; no metric measurements or evidence map are fabricated.")
            return
        started = self.observer.start(6)
        self._notify(6, "RUNNING")
        cfg = self.config["evidence"]
        evidence = EvidenceConfig(**cfg)
        result = analyze_georeferenced_scene(
            self.directory / "georeferenced",
            self.directory / "analysis",
            scene_objects_dir=self.directory / "scene_objects",
            evidence_config=evidence,
            overwrite=bool(self.config["analysis"]["overwrite_stage_outputs"]),
        )
        if not result.success:
            self._fail_stage(6, started, result.error or "Measurement and evidence analysis failed.", result.warnings)
            return
        self._complete_stage(
            6,
            started,
            {
                "points": result.point_count,
                "cameras": result.camera_count,
                "quality_regions": result.quality_region_count,
                "dynamic_markers": result.dynamic_marker_count,
                "measurements": result.measurement_count,
                "processing_time_seconds": result.processing_time_seconds,
            },
            result.warnings,
            [self.directory / "analysis" / "quality_metadata.json", self.directory / "analysis" / "evidence_map" / "quality_grid.json"],
        )

    def _package(self) -> PipelineOutcome:
        started = self.observer.start(7)
        limitations = [
            "Georeferencing residuals and evidence scores are not survey-accuracy claims.",
            "Unobserved or occluded surfaces are not reconstructed as confirmed geometry.",
        ]
        for record in self.observer.stages.values():
            if record.get("status") in {"WARNING", "SKIPPED", "FAILED"}:
                limitations.extend(record.get("warnings", []))
                if record.get("error"):
                    limitations.append(record["error"])
        pipeline_status = "FAILED" if self.first_failed_stage else ("COMPLETED_WITH_WARNINGS" if self.warnings else "COMPLETED")
        health = {
            "run_id": self.run_id,
            "status": pipeline_status,
            "first_failed_stage": self.first_failed_stage,
            "stages": list(self.observer.stages.values()),
        }
        write_json(self.directory / "pipeline_health.json", health)
        package_indices = {
            "scene": ["reconstruction/reconstruction_metadata.json"],
            "pointcloud": ["georeferenced/point_cloud_georef.ply", "reconstruction/dense/fused.ply", "reconstruction/sparse/sparse.ply"],
            "mesh": ["reconstruction/scene.glb"],
            "objects": ["objects/detections.json", "objects/tracks.json", "scene_objects/objects_3d.json"],
            "measurements": ["analysis/measurements.json"],
            "evidence": ["analysis/evidence_map/quality_grid.json"],
            "metadata": ["input_report.json", "pipeline_health.json", "logs/metrics.json"],
        }
        for name, items in package_indices.items():
            available = [item for item in items if (self.directory / item).is_file()]
            write_json(self.directory / name / "index.json", {"source_artifacts": available})
        self.observer.finish(7, started, status="OK", summary={"package_directory": str(self.directory)})
        health["stages"] = list(self.observer.stages.values())
        write_json(self.directory / "pipeline_health.json", health)
        base_manifest = {
            "schema_version": 1,
            "run_id": self.run_id,
            "generated_at": utc_now(),
            "input": self.input_report,
            "processing_configuration": configuration_for_report(self.config),
            "pipeline": health,
            "metrics": {"total_elapsed_seconds": round(time.monotonic() - self.observer.started_monotonic, 4)},
            "warnings": list(dict.fromkeys(self.warnings)),
            "limitations": list(dict.fromkeys(limitations)),
            "output_files": [],
        }
        report_json, report_html = write_report(self.directory, base_manifest)
        reports_dir = self.directory / "reports"
        reports_dir.mkdir(exist_ok=True)
        shutil.copy2(report_json, reports_dir / report_json.name)
        shutil.copy2(report_html, reports_dir / report_html.name)
        base_manifest["output_files"] = [path.relative_to(self.directory).as_posix() for path in all_files(self.directory) if path.name != "result_manifest.json"]
        manifest_path = self.directory / "result_manifest.json"
        write_json(manifest_path, base_manifest)
        return PipelineOutcome(
            run_id=self.run_id,
            directory=self.directory,
            status=pipeline_status,
            first_failed_stage=self.first_failed_stage,
            warnings=list(dict.fromkeys(self.warnings)),
            error=next((record.get("error") for record in self.observer.stages.values() if record.get("error")), None),
            manifest_path=manifest_path,
            report_json_path=report_json,
            report_html_path=report_html,
        )
