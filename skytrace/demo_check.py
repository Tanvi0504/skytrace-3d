"""CLI: verify that the deterministic demo and its live services are ready."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from skytrace.configuration import ROOT_DIR


DEMO_RUN_ID = "processed-demo"


def _get_json(url: str) -> tuple[bool, Any]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status == 200, json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _reachable(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status == 200, f"HTTP {response.status}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, str(exc)


def check_demo(backend_url: str, frontend_url: str, offline: bool = False) -> dict[str, Any]:
    run = ROOT_DIR / "outputs" / DEMO_RUN_ID
    checks: list[dict[str, str]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "status": "OK" if passed else "FAILED", "detail": detail})

    add("Demo result", (run / "run_state.json").is_file(), str(run / "run_state.json"))
    add("Demo point cloud", (run / "georeferenced" / "point_cloud_georef.ply").is_file(), str(run / "georeferenced" / "point_cloud_georef.ply"))
    add("Demo 3D objects", (run / "scene_objects" / "objects_3d.json").is_file(), str(run / "scene_objects" / "objects_3d.json"))
    add("Demo evidence", (run / "analysis" / "evidence_map" / "quality_grid.json").is_file(), str(run / "analysis" / "evidence_map" / "quality_grid.json"))
    if not offline:
        health_ok, health = _get_json(f"{backend_url.rstrip('/')}/health")
        add("Backend health", health_ok and isinstance(health, dict) and health.get("backend") == "healthy", str(health))
        dependency_ok, dependency = _get_json(f"{backend_url.rstrip('/')}/health/dependencies")
        add("Dependency API", dependency_ok and isinstance(dependency, dict), str(dependency))
        scene_ok, scene = _get_json(f"{backend_url.rstrip('/')}/runs/{DEMO_RUN_ID}/scene")
        add("3D viewer API", scene_ok and bool(scene.get("assets")) if isinstance(scene, dict) else False, str(scene))
        objects_ok, objects = _get_json(f"{backend_url.rstrip('/')}/runs/{DEMO_RUN_ID}/objects")
        add("Object API", objects_ok and isinstance(objects, dict) and bool(objects.get("objects")), str(objects))
        evidence_ok, evidence = _get_json(f"{backend_url.rstrip('/')}/runs/{DEMO_RUN_ID}/evidence")
        add("Evidence API", evidence_ok and isinstance(evidence, dict) and bool(evidence.get("quality_regions")), str(evidence))
        frontend_ok, frontend = _reachable(frontend_url)
        add("Frontend", frontend_ok, frontend)
    ready = all(item["status"] == "OK" for item in checks)
    return {"status": "DEMO READY" if ready else "DEMO NOT READY", "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify SkyTrace's live and pre-processed demo readiness.")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:8080")
    parser.add_argument("--offline", action="store_true", help="Check checked-in demo artifacts only; do not claim live-demo readiness.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = check_demo(args.backend_url, args.frontend_url, args.offline)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for check in report["checks"]:
            print(f"{check['name']}: {check['status']} — {check['detail']}")
        print()
        print(report["status"])
    return 0 if report["status"] == "DEMO READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
