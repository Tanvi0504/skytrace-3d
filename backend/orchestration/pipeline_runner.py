"""Background adapter from the web API to the Step 10 pipeline orchestrator."""

from __future__ import annotations

import logging
from pathlib import Path
from threading import Thread

from backend.models.contracts import ProcessRequest, StepStatus
from backend.services.paths import resolve_in_run, run_dir
from backend.services.run_store import load_status, mark_completed, mark_step
from skytrace.configuration import load_config
from skytrace.orchestrator import PipelineOrchestrator

logger = logging.getLogger("backend.orchestration")


def _run_pipeline(run_id: str, request: ProcessRequest) -> None:
    directory = run_dir(run_id)
    status = load_status(run_id)
    if not status.video_filename:
        mark_step(run_id, 1, StepStatus.FAILED, error="Upload an MP4 video before processing.")
        return
    video_path = directory / "uploads" / status.video_filename
    metadata_path: Path | None = None
    if request.gps_metadata_filename:
        try:
            metadata_path = resolve_in_run(run_id, request.gps_metadata_filename)
        except ValueError:
            mark_step(run_id, 3, StepStatus.FAILED, error="Invalid GPS metadata path.")
            return
    elif (directory / "gps_metadata.json").is_file():
        metadata_path = directory / "gps_metadata.json"
    try:
        config = load_config()
        config["frame_selection"]["target_fps"] = request.target_fps
        config["frame_selection"]["blur_threshold"] = request.blur_threshold
        config["reconstruction"]["dense"] = request.dense
        if request.overwrite:
            for section in ("reconstruction", "georeferencing", "object_detection", "object_association", "analysis"):
                config[section]["overwrite_stage_outputs"] = True

        def on_stage(stage: int, state: str, summary: dict, warnings: list[str], error: str | None) -> None:
            if state == "RUNNING":
                mark_step(run_id, stage, StepStatus.RUNNING)
            elif state == "FAILED":
                mark_step(run_id, stage, StepStatus.FAILED, summary=summary, warnings=warnings, error=error)
            elif state == "PARTIAL":
                mark_step(run_id, stage, StepStatus.PARTIAL, summary=summary, warnings=warnings, error=error)
            else:
                mark_step(run_id, stage, StepStatus.COMPLETED, summary=summary, warnings=warnings, error=None)

        outcome = PipelineOrchestrator(
            run_id=run_id,
            directory=directory,
            video_path=video_path,
            metadata_path=metadata_path,
            config=config,
            resume=request.resume,
            callback=on_stage,
        ).run()
        if outcome.status != "FAILED":
            mark_completed(run_id)
    except Exception:  # Traceback is retained in server logs; the API status is concise.
        logger.exception("Processing run %s failed", run_id)
        current = load_status(run_id)
        running = next((step.step for step in current.steps if step.status == StepStatus.RUNNING), 1)
        mark_step(run_id, running, StepStatus.FAILED, error="Unexpected pipeline error. See this run's logs/errors.log for details.")


def start_background_run(run_id: str, request: ProcessRequest) -> None:
    worker = Thread(target=_run_pipeline, args=(run_id, request), daemon=True)
    worker.start()
