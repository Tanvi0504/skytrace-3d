"""Small JSON-backed run store for local MVP execution state."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from backend.models.contracts import RunState, RunStatus, StepProgress, StepStatus
from backend.services.paths import OUTPUTS_DIR, run_dir, validate_run_id

STEP_NAMES = {
    1: "Frame extraction",
    2: "3D reconstruction",
    3: "Georeferencing",
    4: "Object detection",
    5: "3D object association",
    6: "Measurement / reliability analysis",
    7: "Interactive viewer packaging",
}

_LOCK = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(run_id: str) -> Path:
    return run_dir(run_id) / "run_state.json"


def _default_steps() -> list[dict[str, Any]]:
    return [
        StepProgress(step=index, name=name).model_dump()
        for index, name in STEP_NAMES.items()
    ]


def create_run() -> RunStatus:
    run_id = uuid.uuid4().hex[:12]
    directory = run_dir(run_id)
    directory.mkdir(parents=True, exist_ok=False)
    status = RunStatus(
        run_id=run_id,
        state=RunState.QUEUED,
        created_at=_now(),
        updated_at=_now(),
        steps=[StepProgress(step=index, name=name) for index, name in STEP_NAMES.items()],
    )
    save_status(status)
    return status


def list_runs() -> list[str]:
    if not OUTPUTS_DIR.exists():
        return []
    return sorted(
        item.name for item in OUTPUTS_DIR.iterdir() if item.is_dir() and item.name != "__pycache__"
    )


def load_status(run_id: str) -> RunStatus:
    validate_run_id(run_id)
    path = _state_path(run_id)
    if not path.exists():
        directory = run_dir(run_id)
        if not directory.is_dir():
            raise FileNotFoundError(run_id)
        status = RunStatus(
            run_id=run_id,
            state=RunState.COMPLETED,
            created_at=_now(),
            updated_at=_now(),
            steps=[StepProgress(step=index, name=name) for index, name in STEP_NAMES.items()],
        )
        save_status(status)
        return status
    return RunStatus.model_validate(json.loads(path.read_text(encoding="utf-8")))


def save_status(status: RunStatus) -> None:
    with _LOCK:
        directory = run_dir(status.run_id)
        directory.mkdir(parents=True, exist_ok=True)
        status.updated_at = _now()
        _state_path(status.run_id).write_text(
            json.dumps(status.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )


def attach_video(run_id: str, filename: str, size_bytes: int) -> RunStatus:
    status = load_status(run_id)
    status.video_filename = filename
    status.video_size_bytes = size_bytes
    save_status(status)
    return status


def mark_step(
    run_id: str,
    step: int,
    state: StepStatus,
    *,
    summary: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    error: str | None = None,
) -> RunStatus:
    status = load_status(run_id)
    status.state = RunState[f"RUNNING_STEP_{step}"] if state == StepStatus.RUNNING else status.state
    for item in status.steps:
        if item.step == step:
            item.status = state
            item.summary = summary or item.summary
            item.warnings = warnings or item.warnings
            item.error = error
        elif item.step > step and item.status == StepStatus.WAITING:
            continue
    if state == StepStatus.FAILED:
        status.state = RunState.FAILED
        status.error = error or f"Step {step} failed"
    save_status(status)
    return status


def mark_completed(run_id: str) -> RunStatus:
    status = load_status(run_id)
    status.state = RunState.COMPLETED
    save_status(status)
    return status
