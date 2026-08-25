"""Background orchestration that delegates to Steps 1-6."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Thread

from pipeline.analysis.api import analyze_georeferenced_scene
from pipeline.georeferencing.api import georeference_reconstruction
from pipeline.objects.api import detect_and_track_objects
from pipeline.reconstruction.api import run_reconstruction
from pipeline.scene_objects.api import associate_objects_with_3d_scene
from pipeline.video import VideoProcessingConfig, process_video

from backend.models.contracts import ProcessRequest, StepStatus
from backend.services.paths import run_dir
from backend.services.run_store import load_status, mark_completed, mark_step

logger = logging.getLogger("backend.orchestration")


def _run_pipeline(run_id: str, request: ProcessRequest) -> None:
    directory = run_dir(run_id)
    status = load_status(run_id)
    if not status.video_filename:
        mark_step(run_id, 1, StepStatus.FAILED, error="Upload an MP4 video before processing.")
        return
    video_path = directory / "uploads" / status.video_filename
    try:
        mark_step(run_id, 1, StepStatus.RUNNING)
        video = process_video(
            VideoProcessingConfig(
                video_path=video_path,
                output_dir=directory,
                target_fps=request.target_fps,
                blur_threshold=request.blur_threshold,
                run_id=run_id,
            )
        )
        mark_step(
            run_id,
            1,
            StepStatus.COMPLETED,
            summary={
                "sampled_frames": video.sampled_count,
                "selected_frames": video.selected_count,
                "rejected_frames": video.rejected_count,
            },
        )

        mark_step(run_id, 2, StepStatus.RUNNING)
        reconstruction = run_reconstruction(
            directory / "frames",
            directory / "reconstruction",
            dense=request.dense,
            overwrite=request.overwrite,
        )
        if not reconstruction.success:
            mark_step(run_id, 2, StepStatus.FAILED, error=reconstruction.error)
            return
        mark_step(
            run_id,
            2,
            StepStatus.COMPLETED,
            summary={
                "input_images": reconstruction.input_image_count,
                "registered_images": reconstruction.registered_image_count,
                "sparse_points": reconstruction.sparse_point_count,
                "dense_status": reconstruction.dense_status,
            },
            warnings=reconstruction.warnings,
        )

        gps_path = directory / (request.gps_metadata_filename or "gps_metadata.json")
        mark_step(run_id, 3, StepStatus.RUNNING)
        georef = georeference_reconstruction(
            directory / "reconstruction",
            gps_path,
            directory / "georeferenced",
            overwrite=request.overwrite,
        )
        if not georef.success:
            mark_step(run_id, 3, StepStatus.FAILED, error=georef.error, warnings=georef.warnings)
            return
        mark_step(
            run_id,
            3,
            StepStatus.COMPLETED,
            summary={
                "gps_observations": georef.gps_observation_count,
                "matched_poses": georef.matched_pose_count,
                "inliers": georef.inlier_count,
                "estimated_scale": georef.estimated_scale,
            },
            warnings=georef.warnings,
        )

        mark_step(run_id, 4, StepStatus.RUNNING)
        objects = detect_and_track_objects(
            directory / "frames",
            directory / "objects",
            overwrite=request.overwrite,
        )
        if not objects.success:
            mark_step(run_id, 4, StepStatus.FAILED, error=objects.error, warnings=objects.warnings)
            return
        mark_step(
            run_id,
            4,
            StepStatus.COMPLETED,
            summary={
                "frames_processed": objects.frames_processed,
                "detected_objects": objects.detection_count,
                "tracks": objects.track_count,
            },
            warnings=objects.warnings,
        )

        mark_step(run_id, 5, StepStatus.RUNNING)
        associations = associate_objects_with_3d_scene(
            directory / "objects",
            directory / "reconstruction",
            directory / "scene_objects",
            georeferenced_dir=directory / "georeferenced",
            overwrite=request.overwrite,
        )
        if not associations.success:
            mark_step(run_id, 5, StepStatus.FAILED, error=associations.error, warnings=associations.warnings)
            return
        mark_step(
            run_id,
            5,
            StepStatus.COMPLETED,
            summary={
                "tracks": associations.track_count,
                "estimated": associations.estimated_count,
                "low_confidence": associations.low_confidence_count,
                "unavailable": associations.unavailable_count,
            },
            warnings=associations.warnings,
        )

        mark_step(run_id, 6, StepStatus.RUNNING)
        analysis = analyze_georeferenced_scene(
            directory / "georeferenced",
            directory / "analysis",
            scene_objects_dir=directory / "scene_objects",
            overwrite=request.overwrite,
        )
        if not analysis.success:
            mark_step(run_id, 6, StepStatus.FAILED, error=analysis.error, warnings=analysis.warnings)
            return
        mark_step(
            run_id,
            6,
            StepStatus.COMPLETED,
            summary={
                "points": analysis.point_count,
                "cameras": analysis.camera_count,
                "quality_regions": analysis.quality_region_count,
                "dynamic_markers": analysis.dynamic_marker_count,
            },
            warnings=analysis.warnings,
        )
        mark_completed(run_id)
    except Exception as exc:  # Keep user-facing errors concise; traceback stays in logs.
        logger.exception("Processing run %s failed", run_id)
        current = load_status(run_id)
        running = next((step.step for step in current.steps if step.status == StepStatus.RUNNING), 1)
        mark_step(run_id, running, StepStatus.FAILED, error=str(exc))


def start_background_run(run_id: str, request: ProcessRequest) -> None:
    worker = Thread(target=_run_pipeline, args=(run_id, request), daemon=True)
    worker.start()

