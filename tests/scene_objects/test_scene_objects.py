from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from pipeline.scene_objects import associate_objects_with_3d_scene
from pipeline.scene_objects.geometry import (
    intersect_ray_with_plane,
    pixel_to_camera_direction,
    pixel_to_world_ray,
    triangulate_rays,
)
from pipeline.scene_objects.errors import GeometryError
from pipeline.scene_objects.inputs import apply_georeference_transform
from pipeline.scene_objects.models import (
    CameraIntrinsics,
    GeoreferenceTransform,
    ObjectObservation,
    ReconstructionCameraPose,
    WorldRay,
)


def _observation(frame: str, pixel: tuple[float, float], track_id: int = 7) -> ObjectObservation:
    u, v = pixel
    return ObjectObservation(
        detection_id=f"{frame}:1",
        track_id=track_id,
        class_name="car",
        confidence=0.9,
        frame_filename=frame,
        frame_index=0,
        timestamp_seconds=0.0,
        bbox_xyxy=(u - 5.0, v - 20.0, u + 5.0, v),
        is_dynamic_candidate=True,
    )


def _camera(camera_id: int = 1) -> CameraIntrinsics:
    return CameraIntrinsics(
        camera_id=camera_id,
        model="PINHOLE",
        width=1000,
        height=800,
        parameters=(800.0, 800.0, 500.0, 400.0),
    )


def _pose(name: str, centre: np.ndarray, image_id: int = 1) -> ReconstructionCameraPose:
    rotation = np.eye(3)
    translation = -np.asarray(centre, dtype=float)
    return ReconstructionCameraPose(
        image_id=image_id,
        image_name=name,
        camera_id=1,
        rotation_world_to_camera=rotation,
        translation_world_to_camera=translation,
        camera_center_world=np.asarray(centre, dtype=float),
    )


def _project(point: np.ndarray, centre: np.ndarray) -> tuple[float, float]:
    x, y, z = np.asarray(point, dtype=float) - np.asarray(centre, dtype=float)
    return 800.0 * x / z + 500.0, 800.0 * y / z + 400.0


def _write_synthetic_inputs(
    tmp_path: Path,
    *,
    point: np.ndarray = np.array([0.4, 0.2, 8.0]),
    centres: tuple[np.ndarray, ...] = (np.array([0.0, 0.0, 0.0]), np.array([2.0, 0.0, 0.0])),
    include_georeference: bool = True,
) -> tuple[Path, Path, Path | None, np.ndarray]:
    objects_dir = tmp_path / "objects"
    reconstruction_dir = tmp_path / "reconstruction"
    objects_dir.mkdir()
    reconstruction_dir.mkdir()
    detections = []
    poses = []
    for index, centre in enumerate(centres):
        name = f"frame_{index:06d}.jpg"
        pixel = _project(point, centre)
        detections.append(
            {
                "detection_id": f"{name}:1",
                "frame_filename": name,
                "frame_index": index,
                "timestamp_seconds": index * 0.2,
                "class": "car",
                "confidence": 0.9,
                "bbox_xyxy_pixels": [pixel[0] - 5.0, pixel[1] - 20.0, pixel[0] + 5.0, pixel[1]],
                "track_id": 7,
                "is_dynamic_candidate": True,
            }
        )
        poses.append(
            {
                "image_id": index + 1,
                "image_name": name,
                "camera_id": 1,
                "qvec_world_to_camera": [1.0, 0.0, 0.0, 0.0],
                "tvec_world_to_camera": (-centre).tolist(),
                "camera_center_world": centre.tolist(),
            }
        )
    (objects_dir / "detections.json").write_text(json.dumps({"detections": detections}))
    (objects_dir / "tracks.json").write_text(json.dumps({"tracks": [{"track_id": 7}]}))
    (reconstruction_dir / "camera_poses.json").write_text(json.dumps({"poses": poses}))
    camera_dir = reconstruction_dir / "sparse" / "text" / "0"
    camera_dir.mkdir(parents=True)
    (camera_dir / "cameras.txt").write_text("1 PINHOLE 1000 800 800 800 500 400\n")
    georeferenced_dir: Path | None = None
    if include_georeference:
        georeferenced_dir = tmp_path / "georeferenced"
        georeferenced_dir.mkdir()
        matrix = np.eye(4)
        matrix[:3, :3] *= 2.0
        matrix[:3, 3] = [100.0, 200.0, 50.0]
        (georeferenced_dir / "transform.json").write_text(
            json.dumps(
                {
                    "target_coordinate_system": "Local East-North-Up (ENU), metres",
                    "target_reference": {
                        "enu_origin": {
                            "latitude_degrees": 17.385,
                            "longitude_degrees": 78.4867,
                            "altitude_metres": 500.0,
                        }
                    },
                    "transform": {"matrix_4x4": matrix.tolist()},
                }
            )
        )
    return objects_dir, reconstruction_dir, georeferenced_dir, point


def test_pixel_to_ray_uses_actual_pinhole_intrinsics() -> None:
    direction = pixel_to_camera_direction((500.0, 400.0), _camera())

    assert np.allclose(direction, [0.0, 0.0, 1.0])


def test_ray_plane_intersection_returns_known_point() -> None:
    point = intersect_ray_with_plane(
        origin=np.array([0.0, 0.0, 1.0]),
        direction=np.array([0.0, 0.0, -1.0]),
        plane_normal=np.array([0.0, 0.0, 1.0]),
        plane_offset=0.0,
    )

    assert np.allclose(point, [0.0, 0.0, 0.0])


def test_known_multiview_triangulation_recovers_synthetic_object_point() -> None:
    point = np.array([0.4, 0.2, 8.0])
    camera = _camera()
    rays = []
    for index, centre in enumerate((np.array([0.0, 0.0, 0.0]), np.array([2.0, 0.0, 0.0]))):
        name = f"frame_{index}.jpg"
        rays.append(
            pixel_to_world_ray(
                _project(point, centre),
                camera,
                _pose(name, centre, index + 1),
                _observation(name, _project(point, centre)),
            )
        )

    estimate = triangulate_rays(rays)

    assert np.allclose(estimate.position, point, atol=1e-9)
    assert estimate.ray_rmse < 1e-9
    assert estimate.median_ray_angle_degrees > 1.0


def test_triangulation_rejects_views_without_a_camera_baseline() -> None:
    camera = _camera()
    centre = np.array([0.0, 0.0, 0.0])
    rays = [
        pixel_to_world_ray(
            pixel,
            camera,
            _pose(f"frame_{index}.jpg", centre, index + 1),
            _observation(f"frame_{index}.jpg", pixel),
        )
        for index, pixel in enumerate(((500.0, 400.0), (600.0, 400.0)))
    ]

    with pytest.raises(GeometryError, match="no camera baseline"):
        triangulate_rays(rays)


def test_triangulation_rejects_point_behind_a_supporting_camera() -> None:
    observation = _observation("frame_0.jpg", (500.0, 400.0))
    rays = [
        WorldRay(
            origin=np.array([0.0, 0.0, 0.0]),
            direction=np.array([0.0, 0.0, 1.0]),
            observation=observation,
            camera=_pose("frame_0.jpg", np.array([0.0, 0.0, 0.0]), 1),
        ),
        WorldRay(
            origin=np.array([1.0, 0.0, 2.0]),
            direction=np.array([-1.0, 0.0, -3.0]),
            observation=observation,
            camera=_pose("frame_1.jpg", np.array([1.0, 0.0, 2.0]), 2),
        ),
    ]

    with pytest.raises(GeometryError, match="not in front"):
        triangulate_rays(rays)


def test_step3_matrix_coordinate_transformation_is_applied() -> None:
    matrix = np.eye(4)
    matrix[:3, :3] *= 3.0
    matrix[:3, 3] = [10.0, -2.0, 0.5]
    transform = GeoreferenceTransform(
        matrix_4x4=matrix,
        target_coordinate_system="Local East-North-Up (ENU), metres",
        latitude_degrees=None,
        longitude_degrees=None,
        altitude_metres=None,
    )

    transformed = apply_georeference_transform(np.array([1.0, 2.0, 3.0]), transform)

    assert np.allclose(transformed, [13.0, 4.0, 9.5])


def test_association_writes_georeferenced_scene_marker_and_output_schema(tmp_path: Path) -> None:
    objects_dir, reconstruction_dir, georeferenced_dir, point = _write_synthetic_inputs(tmp_path)
    output_dir = tmp_path / "scene_objects"

    result = associate_objects_with_3d_scene(
        objects_dir,
        reconstruction_dir,
        output_dir,
        georeferenced_dir=georeferenced_dir,
    )

    assert result.success
    assert result.track_count == 1
    assert result.estimated_count == 1
    objects = json.loads((output_dir / "objects_3d.json").read_text())["objects"]
    association = objects[0]
    assert association["position_status"] == "estimated"
    assert association["minimum_detection_confidence"] == 0.9
    assert association["median_detection_confidence"] == 0.9
    assert association["maximum_detection_confidence"] == 0.9
    assert np.allclose(association["source_position_reconstruction"], point, atol=1e-9)
    assert np.allclose(association["world_position"], point * 2.0 + [100.0, 200.0, 50.0], atol=1e-9)
    assert association["world_coordinate_status"] == "estimated_local_enu_and_wgs84"
    assert association["latitude_degrees"] is not None
    assert association["position_method"] == "calibrated_multi_view_ray_triangulation"
    trajectories = json.loads((output_dir / "object_trajectories.json").read_text())
    assert trajectories["trajectories"][0]["status"] == "unavailable"
    metadata = json.loads((output_dir / "association_metadata.json").read_text())
    assert "mean_detection_confidence" in metadata["evidence_score"]["formula"]


def test_invalid_object_metadata_returns_structured_failure(tmp_path: Path) -> None:
    objects_dir = tmp_path / "objects"
    objects_dir.mkdir()
    (objects_dir / "detections.json").write_text(json.dumps({"detections": "invalid"}))

    result = associate_objects_with_3d_scene(
        objects_dir,
        tmp_path / "missing-reconstruction",
        tmp_path / "scene_objects",
    )

    assert not result.success
    assert "must contain a 'detections' array" in (result.error or "")


def test_missing_camera_pose_marks_track_unavailable_without_fake_coordinate(tmp_path: Path) -> None:
    objects_dir, reconstruction_dir, _, _ = _write_synthetic_inputs(tmp_path, include_georeference=False)
    document = json.loads((objects_dir / "detections.json").read_text())
    document["detections"][1]["frame_filename"] = "pose_missing.jpg"
    (objects_dir / "detections.json").write_text(json.dumps(document))

    result = associate_objects_with_3d_scene(objects_dir, reconstruction_dir, tmp_path / "scene_objects")

    assert result.success
    assert result.unavailable_count == 1
    association = json.loads((tmp_path / "scene_objects" / "objects_3d.json").read_text())["objects"][0]
    assert association["source_position_reconstruction"] is None
    assert any("No Step 2 camera pose" in warning for warning in association["warnings"])


def test_invalid_camera_intrinsics_marks_track_unavailable(tmp_path: Path) -> None:
    objects_dir, reconstruction_dir, _, _ = _write_synthetic_inputs(tmp_path, include_georeference=False)
    camera_path = reconstruction_dir / "sparse" / "text" / "0" / "cameras.txt"
    camera_path.write_text("1 PINHOLE 1000 800 800 800 500\n")

    result = associate_objects_with_3d_scene(objects_dir, reconstruction_dir, tmp_path / "scene_objects")

    assert result.success
    assert result.unavailable_count == 1
    association = json.loads((tmp_path / "scene_objects" / "objects_3d.json").read_text())["objects"][0]
    assert association["position_status"] == "unavailable"
    assert association["source_position_reconstruction"] is None


def test_low_view_diversity_is_marked_low_confidence(tmp_path: Path) -> None:
    objects_dir, reconstruction_dir, _, _ = _write_synthetic_inputs(
        tmp_path,
        point=np.array([0.2, 0.1, 50.0]),
        centres=(np.array([0.0, 0.0, 0.0]), np.array([0.01, 0.0, 0.0])),
        include_georeference=False,
    )

    result = associate_objects_with_3d_scene(
        objects_dir,
        reconstruction_dir,
        tmp_path / "scene_objects",
        minimum_ray_angle_degrees=1.0,
        max_condition_number=1e12,
    )

    assert result.success
    assert result.low_confidence_count == 1
    association = json.loads((tmp_path / "scene_objects" / "objects_3d.json").read_text())["objects"][0]
    assert association["position_status"] == "low_confidence"
    assert association["source_position_reconstruction"] is not None


def test_no_tracked_observations_writes_empty_association_outputs(tmp_path: Path) -> None:
    objects_dir, reconstruction_dir, _, _ = _write_synthetic_inputs(tmp_path, include_georeference=False)
    (objects_dir / "detections.json").write_text(
        json.dumps(
            {
                "detections": [
                    {
                        "frame_filename": "frame_000000.jpg",
                        "class": "car",
                        "confidence": 0.9,
                        "bbox_xyxy_pixels": [1, 1, 3, 4],
                        "track_id": None,
                    }
                ]
            }
        )
    )

    result = associate_objects_with_3d_scene(objects_dir, reconstruction_dir, tmp_path / "scene_objects")

    assert result.success
    assert result.track_count == 0
    objects = json.loads((tmp_path / "scene_objects" / "objects_3d.json").read_text())["objects"]
    assert objects == []
