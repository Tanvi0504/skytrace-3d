"""Explicit (never implicit) download command for required model weights."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

from skytrace.configuration import ROOT_DIR


YOLO11N_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download the explicitly requested SkyTrace YOLO model to a local, checked path.")
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "models" / "yolo11n.pt", help="Local destination (default: models/yolo11n.pt).")
    parser.add_argument("--url", default=YOLO11N_URL, help="Approved model URL; use only a vetted mirror in an offline/controlled deployment.")
    parser.add_argument("--force", action="store_true", help="Replace an existing local weight file.")
    args = parser.parse_args(argv)
    target = args.output
    if target.exists() and not args.force:
        print(f"Model already exists: {target} ({target.stat().st_size / 1024**2:.1f} MiB, sha256={_sha256(target)}). Use --force to replace it.")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".download")
    try:
        print(f"Downloading YOLO11n explicitly to {target} …")
        with urllib.request.urlopen(args.url, timeout=60) as response, temporary.open("wb") as destination:
            shutil.copyfileobj(response, destination)
        if temporary.stat().st_size < 1024 * 1024:
            raise RuntimeError("Downloaded file is unexpectedly small; refusing to use it as model weights.")
        temporary.replace(target)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        print(f"Model setup failed: {exc}", file=sys.stderr)
        print("Offline setup: place a vetted yolo11n.pt file at models/yolo11n.pt; see docs/model_weights.md.", file=sys.stderr)
        return 1
    print(f"Model ready: {target} ({target.stat().st_size / 1024**2:.1f} MiB, sha256={_sha256(target)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
