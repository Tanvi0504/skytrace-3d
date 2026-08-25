"""FastAPI application for the SkyTrace Step 7 MVP."""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline.analysis.api import measure_scene_distance
from pipeline.analysis.inputs import load_scene_context
from pipeline.analysis.models import EvidenceConfig

from backend.models.contracts import (
    CreateRunResponse,
    MeasurementRequest,
    ProcessRequest,
    RunStatus,
    UploadResponse,
)
from backend.orchestration.pipeline_runner import start_background_run
from backend.services.paths import MAX_UPLOAD_BYTES, resolve_in_run, run_dir, sanitize_filename
from backend.services.run_store import attach_video, create_run, list_runs, load_status
from backend.services.scene import evidence_for_run, objects_for_run, results_for_run, scene_metadata
from skytrace.system_check import collect_checks

app = FastAPI(title="SkyTrace API", version="0.10.0")
_cors_origins = [
    item.strip()
    for item in os.getenv(
        "SKYTRACE_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "backend": "healthy", "run_storage": "filesystem"}


@app.get("/health/dependencies")
def dependency_health() -> dict:
    report = collect_checks()
    values = {item["name"]: item for item in report["checks"]}
    return {
        "backend": "healthy",
        "database": "not_required",
        "reconstruction": "available" if values.get("COLMAP", {}).get("status") == "FOUND" else "unavailable",
        "object_detection": "available"
        if values.get("Model weights", {}).get("status") == "FOUND" and values.get("Ultralytics", {}).get("status") == "FOUND"
        else "unavailable",
        "measurement": "available",
        "ffmpeg": "available" if values.get("FFmpeg", {}).get("status") == "FOUND" else "unavailable",
        "gpu": values.get("GPU", {}).get("status", "UNKNOWN").lower(),
        "system_status": report["status"],
    }


@app.get("/runs")
def runs() -> dict[str, list[str]]:
    return {"runs": list_runs()}


@app.post("/runs", response_model=CreateRunResponse)
def create_processing_run() -> CreateRunResponse:
    status = create_run()
    return CreateRunResponse(run_id=status.run_id, status=status)


@app.post("/runs/{run_id}/upload", response_model=UploadResponse)
async def upload_video(run_id: str, file: UploadFile = File(...)) -> UploadResponse:
    filename = sanitize_filename(file.filename or "")
    if Path(filename).suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="Only MP4 uploads are supported for this MVP.")
    upload_dir = run_dir(run_id) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / filename
    size = 0
    with destination.open("wb") as target:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                destination.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Upload exceeds the 1 GB local MVP limit.")
            target.write(chunk)
    attach_video(run_id, filename, size)
    return UploadResponse(run_id=run_id, filename=filename, size_bytes=size, content_type=file.content_type)


@app.post("/runs/{run_id}/process", response_model=RunStatus)
def process_run(run_id: str, request: ProcessRequest, background_tasks: BackgroundTasks) -> RunStatus:
    try:
        status = load_status(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    background_tasks.add_task(start_background_run, run_id, request)
    return status


@app.get("/runs/{run_id}/status", response_model=RunStatus)
def run_status(run_id: str) -> RunStatus:
    try:
        return load_status(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc


@app.get("/runs/{run_id}/scene")
def get_scene(run_id: str):
    try:
        return scene_metadata(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc


@app.get("/runs/{run_id}/objects")
def get_objects(run_id: str):
    return {"run_id": run_id, "objects": objects_for_run(run_id)}


@app.get("/runs/{run_id}/evidence")
def get_evidence(run_id: str):
    return evidence_for_run(run_id)


@app.get("/runs/{run_id}/results")
def get_results(run_id: str):
    return results_for_run(run_id)


@app.post("/runs/{run_id}/measure")
def measure(run_id: str, request: MeasurementRequest):
    started = time.monotonic()
    directory = run_dir(run_id)
    try:
        scene = load_scene_context(directory / "georeferenced", directory / "scene_objects", EvidenceConfig())
        result = measure_scene_distance(
            scene,
            [request.point_a.x, request.point_a.y, request.point_a.z],
            [request.point_b.x, request.point_b.y, request.point_b.z],
            measurement_id=f"interactive_{int(started * 1000)}",
            unit=request.unit,
        ).to_dict()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Measurement unavailable: {exc}") from exc
    result["api_response_time_seconds"] = round(time.monotonic() - started, 4)
    return result


@app.get("/runs/{run_id}/assets/{relative_path:path}")
def run_asset(run_id: str, relative_path: str):
    try:
        path = resolve_in_run(run_id, relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path)
