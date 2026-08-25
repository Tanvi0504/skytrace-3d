"""Run directory and safe-path helpers."""

from __future__ import annotations

import re
from pathlib import Path

RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
SAFE_FILENAME_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+")

ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = ROOT_DIR / "outputs"
MAX_UPLOAD_BYTES = 1024 * 1024 * 1024


def sanitize_filename(filename: str) -> str:
    cleaned = SAFE_FILENAME_PATTERN.sub("_", Path(filename).name).strip("._")
    return cleaned or "upload.mp4"


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Invalid run ID")
    return run_id


def run_dir(run_id: str) -> Path:
    return OUTPUTS_DIR / validate_run_id(run_id)


def resolve_in_run(run_id: str, relative_path: str | Path) -> Path:
    base = run_dir(run_id).resolve()
    candidate = (base / relative_path).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("Requested path is outside the run directory")
    return candidate


def relative_to_run(run_id: str, path: str | Path) -> str:
    return str(Path(path).resolve().relative_to(run_dir(run_id).resolve())).replace("\\", "/")

