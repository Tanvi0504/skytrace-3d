"""Read existing SkyTrace artifacts for UI-friendly API responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.models.contracts import EvidenceInfo, EvidenceLevel, Object3D, ResultsInfo, SceneAsset, SceneMetadata
from backend.services.paths import relative_to_run, run_dir

EVIDENCE_LEGEND = {
    "HIGH": "strong supporting evidence",
    "MEDIUM": "moderate supporting evidence",
    "LOW": "weak supporting evidence",
    "INSUFFICIENT": "insufficient evidence for reliable interpretation",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _ply_vertex_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        with path.open("rb") as source:
            for raw in source:
                line = raw.decode("ascii", errors="ignore").strip()
                if line.startswith("element vertex"):
                    return int(line.split()[-1])
                if line == "end_header":
                    break
    except (OSError, ValueError):
        return None
    return None


def _asset(run_id: str, path: Path, source: str) -> SceneAsset | None:
    if not path.is_file():
        return None
    suffix = path.suffix.lower().lstrip(".")
    if suffix not in {"ply", "obj", "gltf", "glb"}:
        return None
    kind = "point_cloud" if suffix == "ply" else "mesh"
    notes = []
    if suffix == "ply":
        notes.append("Loaded in browser as a point cloud; original reconstruction file is unchanged.")
    return SceneAsset(
        kind=kind,
        format=suffix.upper(),
        url=f"/runs/{run_id}/assets/{relative_to_run(run_id, path)}",
        point_count=_ply_vertex_count(path) if suffix == "ply" else None,
        source=source,
        browser_notes=notes,
    )


def scene_metadata(run_id: str) -> SceneMetadata:
    directory = run_dir(run_id)
    video_meta = _read_json(directory / "metadata.json")
    reconstruction = _read_json(directory / "reconstruction" / "reconstruction_metadata.json")
    georef = _read_json(directory / "georeferenced" / "georef_metadata.json")
    analysis = _read_json(directory / "analysis" / "quality_metadata.json")
    transform = _read_json(directory / "georeferenced" / "transform.json")

    assets = [
        asset
        for asset in (
            _asset(run_id, directory / "georeferenced" / "point_cloud_georef.ply", "Step 3 georeferenced PLY"),
            _asset(run_id, directory / "reconstruction" / "dense" / "fused.ply", "Step 2 dense PLY"),
            _asset(run_id, directory / "reconstruction" / "sparse" / "sparse.ply", "Step 2 sparse PLY"),
            _asset(run_id, directory / "reconstruction" / "scene.glb", "Step 2 exported GLB"),
        )
        if asset is not None
    ]
    warnings: list[str] = []
    for doc in (video_meta, reconstruction, georef, analysis):
        raw = doc.get("warnings")
        if isinstance(raw, list):
            warnings.extend(str(item) for item in raw)
    if not assets:
        warnings.append("No browser-supported reconstruction asset was found for this run.")

    return SceneMetadata(
        run_id=run_id,
        coordinate_system=transform.get("target_coordinate_system"),
        reconstruction_status="available" if reconstruction.get("success") else "missing_or_failed",
        georeferencing_status="available" if georef.get("success") else "missing_or_failed",
        assets=assets,
        summary={
            "video": video_meta,
            "reconstruction": reconstruction,
            "georeferencing": georef,
            "analysis": analysis,
        },
        warnings=warnings,
    )


def objects_for_run(run_id: str) -> list[Object3D]:
    path = run_dir(run_id) / "scene_objects" / "objects_3d.json"
    if not path.is_file():
        return []
    document = _read_json(path)
    objects = document.get("objects", [])
    response: list[Object3D] = []
    for item in objects if isinstance(objects, list) else []:
        if not isinstance(item, dict):
            continue
        position = item.get("world_position") or item.get("source_position_reconstruction")
        evidence_score = item.get("evidence_score")
        if evidence_score is None:
            level = EvidenceLevel.UNKNOWN
        elif evidence_score >= 0.75:
            level = EvidenceLevel.HIGH
        elif evidence_score >= 0.5:
            level = EvidenceLevel.MEDIUM
        elif evidence_score >= 0.25:
            level = EvidenceLevel.LOW
        else:
            level = EvidenceLevel.INSUFFICIENT
        response.append(
            Object3D(
                object_id=str(item.get("object_id", "object")),
                class_name=str(item.get("class", "unknown")),
                track_id=item.get("track_id"),
                position_status=str(item.get("position_status", "unavailable")),
                position=position if isinstance(position, list) else None,
                coordinate_system=item.get("coordinate_system"),
                detection_confidence=item.get("mean_detection_confidence"),
                observation_count=item.get("observation_count"),
                is_dynamic_candidate=bool(item.get("is_dynamic_candidate", False)),
                motion_status=str(item.get("motion_status", "unknown")),
                evidence_level=level,
                evidence_score=evidence_score,
                warnings=[str(warning) for warning in item.get("warnings", [])],
                raw=item,
            )
        )
    return response


def evidence_for_run(run_id: str) -> EvidenceInfo:
    path = run_dir(run_id) / "analysis" / "evidence_map" / "quality_grid.json"
    document = _read_json(path)
    regions = document.get("regions", [])
    return EvidenceInfo(
        run_id=run_id,
        levels=EVIDENCE_LEGEND,
        quality_regions=regions if isinstance(regions, list) else [],
        warnings=[] if path.is_file() else ["Step 6 evidence map is not available for this run."],
    )


def results_for_run(run_id: str) -> ResultsInfo:
    directory = run_dir(run_id)
    files: dict[str, str] = {}
    for path in directory.rglob("*"):
        if path.is_file() and path.name != "run_state.json":
            files[relative_to_run(run_id, path)] = f"/runs/{run_id}/assets/{relative_to_run(run_id, path)}"
    return ResultsInfo(run_id=run_id, files=files)

