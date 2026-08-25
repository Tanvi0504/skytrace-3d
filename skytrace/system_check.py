"""CLI: report whether this machine can run SkyTrace without cryptic failures."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from skytrace.configuration import ROOT_DIR, load_config


REQUIRED_PACKAGES = {
    "OpenCV": "cv2",
    "NumPy": "numpy",
    "FastAPI": "fastapi",
    "Pydantic": "pydantic",
    "PyYAML": "yaml",
    "Ultralytics": "ultralytics",
    "PyTorch": "torch",
    "Multipart upload support": "multipart",
    "Uvicorn": "uvicorn",
}


def _memory_bytes() -> int | None:
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


def _command_version(command: list[str]) -> tuple[bool, str | None]:
    if shutil.which(command[0]) is None:
        return False, None
    try:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return True, None
    return True, completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else None


def _status(name: str, status: str, detail: str, required: bool) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "required": required}


def _node_version_is_supported(value: str | None) -> bool:
    if not value:
        return False
    match = re.search(r"v?(\\d+)", value)
    return bool(match and 20 <= int(match.group(1)) <= 22)


def _storage_check() -> tuple[bool, str]:
    output_dir = ROOT_DIR / "outputs"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".skytrace-write-check-", delete=True):
            pass
    except OSError as exc:
        return False, f"{output_dir} is not writable: {exc}"
    return True, f"{output_dir} is writable"


def _configured_model_path(config: dict[str, Any] | None) -> Path:
    raw_path = str((config or {}).get("object_detection", {}).get("model_path", "models/yolo11n.pt"))
    model_path = Path(raw_path)
    return model_path if model_path.is_absolute() else ROOT_DIR / model_path


def collect_checks(config_path: str | Path | None = None, *, include_frontend: bool = True) -> dict[str, Any]:
    """Return JSON-safe dependency status. This function never installs or downloads."""
    checks: list[dict[str, Any]] = []
    python_ok = (3, 10) <= sys.version_info[:2] <= (3, 12)
    checks.append(
        _status(
            "Python",
            "FOUND" if python_ok else "MISSING",
            f"{platform.python_version()} (requires Python 3.10-3.12; Docker uses 3.11)",
            True,
        )
    )
    if include_frontend:
        node_found, node_version = _command_version(["node", "--version"])
        node_ok = node_found and _node_version_is_supported(node_version)
        checks.append(
            _status(
                "Node",
                "FOUND" if node_ok else "MISSING",
                node_version if node_ok else "Install Node.js 20-22; it is required to build and run the frontend.",
                True,
            )
        )
        frontend_node_modules = ROOT_DIR / "frontend" / "node_modules"
        dependencies_ready = frontend_node_modules.is_dir()
        checks.append(
            _status(
                "Frontend dependencies",
                "FOUND" if dependencies_ready else "MISSING",
                str(frontend_node_modules) if dependencies_ready else "Run `npm --prefix frontend ci` to install the locked frontend dependencies.",
                True,
            )
        )
    for display, module in REQUIRED_PACKAGES.items():
        found = importlib.util.find_spec(module) is not None
        checks.append(_status(display, "FOUND" if found else "MISSING", module if found else f"Install {module} from requirements.txt.", True))
    ffmpeg_found, ffmpeg_version = _command_version(["ffmpeg", "-version"])
    checks.append(_status("FFmpeg", "FOUND" if ffmpeg_found else "MISSING", ffmpeg_version or "Install FFmpeg; it is recommended for reliable video codec handling.", True))
    colmap_found, colmap_version = _command_version(["colmap", "-h"])
    checks.append(_status("COLMAP", "FOUND" if colmap_found else "MISSING", colmap_version or "Install COLMAP and make `colmap` available on PATH for live reconstruction.", True))
    config: dict[str, Any] | None = None
    requested_config = Path(config_path) if config_path else None
    try:
        config = load_config(requested_config)
        checks.append(_status("Configuration", "FOUND", str(requested_config or ROOT_DIR / "config" / "default.yaml"), True))
    except RuntimeError as exc:
        checks.append(_status("Configuration", "MISSING", f"Fix configuration before running: {exc}", True))
    model_path = _configured_model_path(config)
    model_found = model_path.is_file() and model_path.stat().st_size > 0
    checks.append(
        _status(
            "Model weights",
            "FOUND" if model_found else "MISSING",
            str(model_path) if model_found else f"Missing {model_path}; run `python -m skytrace.setup_models` or follow docs/model_weights.md.",
            True,
        )
    )
    nvidia_found, nvidia_version = _command_version(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])
    checks.append(_status("GPU", "FOUND" if nvidia_found else "NOT AVAILABLE", nvidia_version or "CPU fallback is configured by default.", False))
    cuda_found = False
    cuda_detail = "CUDA not detected. CPU mode is supported."
    if importlib.util.find_spec("torch") is not None:
        try:
            import torch

            cuda_found = bool(torch.cuda.is_available())
            cuda_detail = f"PyTorch CUDA {torch.version.cuda}" if cuda_found else "PyTorch is installed without an available CUDA device."
        except Exception as exc:  # Optional probe only.
            cuda_detail = f"Could not inspect CUDA: {exc}"
    checks.append(_status("CUDA", "FOUND" if cuda_found else "NOT AVAILABLE", cuda_detail, False))
    disk = shutil.disk_usage(ROOT_DIR)
    minimum_free = 10 * 1024**3
    disk_status = "FOUND" if disk.free >= minimum_free else "WARNING"
    checks.append(_status("Storage", disk_status, f"{disk.free / 1024**3:.1f} GiB free of {disk.total / 1024**3:.1f} GiB; recommended minimum is 10 GiB.", True))
    storage_writable, storage_detail = _storage_check()
    checks.append(_status("Run storage", "FOUND" if storage_writable else "MISSING", storage_detail, True))
    memory = _memory_bytes()
    checks.append(_status("RAM", "FOUND" if memory else "UNKNOWN", f"{memory / 1024**3:.1f} GiB total" if memory else "Could not determine total memory.", False))
    checks.append(_status("CPU", "FOUND", f"{os.cpu_count() or 'unknown'} logical CPU(s)", False))
    required_failures = [item for item in checks if item["required"] and item["status"] not in {"FOUND"}]
    return {
        "system": {"os": platform.platform(), "machine": platform.machine(), "python_executable": sys.executable},
        "status": "READY" if not required_failures else "NOT READY",
        "checks": checks,
        "actions": [item["detail"] for item in required_failures],
        "config_path": str(requested_config) if requested_config else "config/default.yaml",
    }


def _print_human(report: dict[str, Any]) -> None:
    for item in report["checks"]:
        print(f"{item['name']}: {item['status']} — {item['detail']}")
    print()
    print(report["status"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check SkyTrace dependencies, resources, model files, and external tools.")
    parser.add_argument("--json", action="store_true", help="Print JSON for automation.")
    parser.add_argument("--config", type=Path, help="Configuration profile whose model path should be checked.")
    parser.add_argument("--backend-only", action="store_true", help="Skip frontend Node/dependency checks (for the backend container health endpoint).")
    args = parser.parse_args(argv)
    report = collect_checks(args.config, include_frontend=not args.backend_only)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
