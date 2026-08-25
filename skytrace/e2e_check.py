"""Validate a completed integrated run package in CI or a release checklist."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CRITICAL_OUTPUTS = {
    "frame extraction": "metadata.json",
    "reconstruction": "reconstruction/reconstruction_metadata.json",
    "object detection": "objects/object_metadata.json",
    "3D object association": "scene_objects/objects_3d.json",
    "report": "skytrace_report.html",
    "manifest": "result_manifest.json",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail if a SkyTrace result package lacks a required completed-stage artifact.")
    parser.add_argument("--run", type=Path, required=True, help="Path to results/<run-id>.")
    args = parser.parse_args(argv)
    missing = [f"{name}: {path}" for name, path in CRITICAL_OUTPUTS.items() if not (args.run / path).is_file()]
    manifest_path = args.run / "result_manifest.json"
    status = None
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            status = manifest.get("pipeline", {}).get("status")
        except json.JSONDecodeError:
            missing.append("manifest: invalid JSON")
    if status == "FAILED":
        missing.append("pipeline: result manifest reports FAILED")
    if missing:
        print("END-TO-END CHECK FAILED", file=sys.stderr)
        print("\n".join(missing), file=sys.stderr)
        return 1
    print("END-TO-END CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
