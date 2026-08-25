from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


client = TestClient(app)


def test_create_run_and_status():
    response = client.post("/runs")
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    status = client.get(f"/runs/{run_id}/status")
    assert status.status_code == 200
    body = status.json()
    assert body["state"] == "QUEUED"
    assert [step["step"] for step in body["steps"]] == [1, 2, 3, 4, 5, 6]


def test_upload_rejects_non_mp4():
    run_id = client.post("/runs").json()["run_id"]
    response = client.post(
        f"/runs/{run_id}/upload",
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )
    assert response.status_code == 400
    assert "MP4" in response.json()["detail"]


def test_scene_metadata_for_step_one_example_is_honest():
    response = client.get("/runs/example/scene")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "example"
    assert body["assets"] == []
    assert "No browser-supported reconstruction asset" in " ".join(body["warnings"])


def test_objects_endpoint_without_step_five_returns_empty_list():
    response = client.get("/runs/example/objects")
    assert response.status_code == 200
    assert response.json()["objects"] == []


def test_safe_asset_endpoint_blocks_path_traversal():
    response = client.get("/runs/example/assets/%2E%2E/%2E%2E/requirements.txt")
    assert response.status_code == 400


def test_measurement_reports_unavailable_without_step_three():
    response = client.post(
        "/runs/example/measure",
        json={
            "point_a": {"x": 0, "y": 0, "z": 0},
            "point_b": {"x": 1, "y": 0, "z": 0},
            "unit": "m",
        },
    )
    assert response.status_code == 422
    assert "Measurement unavailable" in response.json()["detail"]


@pytest.fixture()
def processed_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from backend.services import paths
    from backend.services import scene as scene_service

    monkeypatch.setattr(paths, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(scene_service, "run_dir", lambda run_id: tmp_path / run_id)
    monkeypatch.setattr(scene_service, "relative_to_run", lambda run_id, path: str(Path(path).resolve().relative_to((tmp_path / run_id).resolve())).replace("\\", "/"))
    run_dir = tmp_path / "processed"
    (run_dir / "georeferenced").mkdir(parents=True)
    (run_dir / "scene_objects").mkdir()
    (run_dir / "analysis" / "evidence_map").mkdir(parents=True)
    (run_dir / "georeferenced" / "point_cloud_georef.ply").write_text(
        "ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nend_header\n0 0 0\n1 0 0\n0 1 0\n",
        encoding="utf-8",
    )
    (run_dir / "georeferenced" / "transform.json").write_text(
        json.dumps(
            {
                "target_coordinate_system": "local east-north-up metres",
                "transform": {"matrix_4x4": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "scene_objects" / "objects_3d.json").write_text(
        json.dumps(
            {
                "objects": [
                    {
                        "object_id": "track_7",
                        "track_id": 7,
                        "class": "car",
                        "position_status": "estimated",
                        "world_position": [1, 2, 0],
                        "coordinate_system": "local east-north-up metres",
                        "mean_detection_confidence": 0.84,
                        "observation_count": 4,
                        "is_dynamic_candidate": True,
                        "motion_status": "unknown",
                        "evidence_score": 0.8,
                        "warnings": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "analysis" / "evidence_map" / "quality_grid.json").write_text(
        json.dumps({"regions": [{"evidence_level": "HIGH", "centre": [0, 0, 0]}]}),
        encoding="utf-8",
    )
    return "processed"


def test_processed_run_scene_objects_and_evidence(processed_run):
    scene = client.get(f"/runs/{processed_run}/scene").json()
    assert scene["assets"][0]["format"] == "PLY"
    assert scene["assets"][0]["point_count"] == 3

    objects = client.get(f"/runs/{processed_run}/objects").json()["objects"]
    assert objects[0]["class_name"] == "car"
    assert objects[0]["motion_status"] == "unknown"

    evidence = client.get(f"/runs/{processed_run}/evidence").json()
    assert evidence["levels"]["HIGH"] == "strong supporting evidence"
    assert evidence["quality_regions"][0]["evidence_level"] == "HIGH"
