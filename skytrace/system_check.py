"""CLI: report whether this machine can run SkyTrace without cryptic failures."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from skytrace.configuration import ROOT_DIR


REQUIRED_PACKAGES = {
    "OpenCV": "cv2",
    "NumPy": "numpy",
    "FastAPI": "fastapi",
    "Pydantic": "pydantic",
    "PyYAML": "yaml",
    "Ultralytics": "ultralytics",
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


def collect_checks(config_path: str | Path | None = None) -> dict[str, Any]:
    """Return JSON-safe dependency status. This function never installs or downloads."""
    checks: list[dict[str, Any]] = []
    python_ok = sys.version_info >= (3, 10)
    checks.append(_status("Python", "FOUND" if python_ok else "MISSING", f"{platform.python_version()} (requires >= 3.10)", True))
    node_found, node_version = _command_version(["node", "--version"])
    checks.append(_status("Node", "FOUND" if node_found else "MISSING", node_version or "Node 20+ is required to build the frontend.", True))
    for display, module in REQUIRED_PACKAGES.items():
        found = importlib.util.find_spec(module) is not None
        checks.append(_status(display, "FOUND" if found else "MISSING", module if found else f"Install {module} from requirements.txt.", True))
    ffmpeg_found, ffmpeg_version = _command_version(["ffmpeg", "-version"])
    checks.append(_status("FFmpeg", "FOUND" if ffmpeg_found else "MISSING", ffmpeg_version or "Install FFmpeg; it is recommended for reliable video codec handling.", True))
    colmap_found, colmap_version = _command_version(["colmap", "-h"])
    checks.append(_status("COLMAP", "FOUND" if colmap_found else "MISSING", colmap_version or "Install COLMAP and make `colmap` available on PATH for live reconstruction.", True))
    model_path = ROOT_DIR / "models" / "yolo11n.pt"
    model_found = model_path.is_file() and model_path.stat().st_size > 0
    checks.append(_status("Model weights", "FOUND" if model_found else "MISSING", str(model_path) if model_found else f"Missing {model_path}; run `python -m skytrace.setup_models` or follow docs/model_weights.md.", True))
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
    memory = _memory_bytes()
    checks.append(_status("RAM", "FOUND" if memory else "UNKNOWN", f"{memory / 1024**3:.1f} GiB total" if memory else "Could not determine total memory.", False))
    checks.append(_status("CPU", "FOUND", f"{os.cpu_count() or 'unknown'} logical CPU(s)", False))
    required_failures = [item for item in checks if item["required"] and item["status"] not in {"FOUND"}]
    return {
        "system": {"os": platform.platform(), "machine": platform.machine(), "python_executable": sys.executable},
        "status": "READY" if not required_failures else "NOT READY",
        "checks": checks,
        "actions": [item["detail"] for item in required_failures],
        "config_path": str(config_path) if config_path else "config/default.yaml",
    }


def _print_human(report: dict[str, Any]) -> None:
    for item in report["checks"]:
        print(f"{item['name']}: {item['status']} — {item['detail']}")
    print()
    print(report["status"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check SkyTrace dependencies, resources, model files, and external tools.")
    parser.add_argument("--json", action="store_true", help="Print JSON for automation.")
    args = parser.parse_args(argv)
    report = collect_checks()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
