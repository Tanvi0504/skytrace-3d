"""Calibrated ray construction and numerically checked multi-view geometry."""

from __future__ import annotations

import itertools
import math

import cv2
import numpy as np

from pipeline.scene_objects.errors import CameraCalibrationError, GeometryError
from pipeline.scene_objects.models import (
    CameraIntrinsics,
    ReconstructionCameraPose,
    TriangulationEstimate,
    WorldRay,
)


def quaternion_to_rotation_matrix(qvec: np.ndarray) -> np.ndarray:
    """Convert COLMAP's normalized ``[qw, qx, qy, qz]`` quaternion to ``R``."""
    values = np.asarray(qvec, dtype=float)
    if values.shape != (4,) or not np.all(np.isfinite(values)):
        raise GeometryError("COLMAP quaternion must contain four finite values")
    norm = float(np.linalg.norm(values))
    if norm <= np.finfo(float).eps:
        raise GeometryError("COLMAP quaternion has zero norm")
    qw, qx, qy, qz = values / norm
    return np.array(
        [
            [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
            [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
            [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
        ],
        dtype=float,
    )


def _camera_matrix(camera: CameraIntrinsics) -> tuple[np.ndarray, np.ndarray, bool]:
    """Return OpenCV K, distortion terms, and whether the model is fisheye."""
    model = camera.model.upper()
    values = camera.parameters
    try:
        if model == "SIMPLE_PINHOLE" and len(values) == 3:
            focal, cx, cy = values
            return np.array([[focal, 0, cx], [0, focal, cy], [0, 0, 1.0]]), np.zeros(4), False
        if model == "PINHOLE" and len(values) == 4:
            fx, fy, cx, cy = values
            return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]]), np.zeros(4), False
        if model == "SIMPLE_RADIAL" and len(values) == 4:
            focal, cx, cy, k1 = values
            return np.array([[focal, 0, cx], [0, focal, cy], [0, 0, 1.0]]), np.array([k1, 0, 0, 0]), False
        if model == "RADIAL" and len(values) == 5:
            focal, cx, cy, k1, k2 = values
            return np.array([[focal, 0, cx], [0, focal, cy], [0, 0, 1.0]]), np.array([k1, k2, 0, 0]), False
        if model == "OPENCV" and len(values) == 8:
            fx, fy, cx, cy, k1, k2, p1, p2 = values
            return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]]), np.array([k1, k2, p1, p2]), False
        if model == "FULL_OPENCV" and len(values) == 12:
            fx, fy, cx, cy, *distortion = values
            return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]]), np.array(distortion), False
        if model == "OPENCV_FISHEYE" and len(values) == 8:
            fx, fy, cx, cy, *distortion = values
            return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]]), np.array(distortion), True
        if model == "SIMPLE_RADIAL_FISHEYE" and len(values) == 4:
            focal, cx, cy, k1 = values
            return np.array([[focal, 0, cx], [0, focal, cy], [0, 0, 1.0]]), np.array([k1, 0, 0, 0]), True
        if model == "RADIAL_FISHEYE" and len(values) == 5:
            focal, cx, cy, k1, k2 = values
            return np.array([[focal, 0, cx], [0, focal, cy], [0, 0, 1.0]]), np.array([k1, k2, 0, 0]), True
    except ValueError as exc:
        raise CameraCalibrationError(f"Invalid {camera.model} camera parameters") from exc
    raise CameraCalibrationError(
        f"Unsupported or malformed COLMAP camera model {camera.model!r}; "
        "no ray was estimated from this calibration."
    )


def pixel_to_camera_direction(
    pixel: tuple[float, float],
    camera: CameraIntrinsics,
) -> np.ndarray:
    """Undistort a verified pixel and return its unit camera-frame direction."""
    u, v = (float(value) for value in pixel)
    if camera.width <= 0 or camera.height <= 0:
        raise CameraCalibrationError("Camera image dimensions must be positive")
    if not np.all(np.isfinite(camera.parameters)):
        raise CameraCalibrationError("Camera parameters must all be finite")
    if (
        not np.isfinite([u, v]).all()
        or not 0.0 <= u < camera.width
        or not 0.0 <= v < camera.height
    ):
        raise GeometryError(
            f"Anchor pixel ({u}, {v}) lies outside {camera.width}x{camera.height} camera bounds"
        )
    matrix, distortion, fisheye = _camera_matrix(camera)
    if matrix[0, 0] <= 0 or matrix[1, 1] <= 0:
        raise CameraCalibrationError("Camera focal lengths must be positive")
    source = np.array([[[u, v]]], dtype=np.float64)
    if fisheye:
        normalized = cv2.fisheye.undistortPoints(source, matrix, distortion)
    else:
        normalized = cv2.undistortPoints(source, matrix, distortion)
    x, y = normalized.reshape(2)
    direction = np.array([x, y, 1.0], dtype=float)
    return direction / np.linalg.norm(direction)


def pixel_to_world_ray(
    pixel: tuple[float, float],
    camera: CameraIntrinsics,
    pose: ReconstructionCameraPose,
    observation,
) -> WorldRay:
    """Construct a world-space viewing ray from actual calibration and pose."""
    camera_direction = pixel_to_camera_direction(pixel, camera)
    world_direction = pose.rotation_world_to_camera.T @ camera_direction
    world_direction /= np.linalg.norm(world_direction)
    return WorldRay(
        origin=pose.camera_center_world,
        direction=world_direction,
        observation=observation,
        camera=pose,
    )


def intersect_ray_with_plane(
    origin: np.ndarray,
    direction: np.ndarray,
    plane_normal: np.ndarray,
    plane_offset: float,
) -> np.ndarray:
    """Intersect ``origin + t * direction`` with ``normal · point + offset = 0``.

    The caller must supply a semantically justified plane. Step 5 never fits a
    ground plane automatically from an arbitrary point cloud.
    """
    origin = np.asarray(origin, dtype=float)
    direction = np.asarray(direction, dtype=float)
    normal = np.asarray(plane_normal, dtype=float)
    if origin.shape != (3,) or direction.shape != (3,) or normal.shape != (3,):
        raise GeometryError("Ray and plane vectors must each have shape (3,)")
    denominator = float(normal @ direction)
    if abs(denominator) <= 1e-12:
        raise GeometryError("Ray is parallel to the supplied plane")
    distance = -float(normal @ origin + plane_offset) / denominator
    if distance < 0:
        raise GeometryError("Plane intersection lies behind the camera")
    return origin + distance * direction


def triangulate_rays(rays: list[WorldRay]) -> TriangulationEstimate:
    """Least-squares triangulation by minimizing perpendicular point-to-ray error."""
    if len(rays) < 2:
        raise GeometryError("At least two calibrated observations are required for triangulation")
    normalized_rays: list[tuple[np.ndarray, np.ndarray]] = []
    for ray in rays:
        origin = np.asarray(ray.origin, dtype=float)
        direction = np.asarray(ray.direction, dtype=float)
        if origin.shape != (3,) or direction.shape != (3,):
            raise GeometryError("Every ray origin and direction must have shape (3,)")
        if not np.all(np.isfinite(origin)) or not np.all(np.isfinite(direction)):
            raise GeometryError("Every ray origin and direction must be finite")
        direction_norm = float(np.linalg.norm(direction))
        if direction_norm <= np.finfo(float).eps:
            raise GeometryError("Viewing-ray direction has zero length")
        normalized_rays.append((origin, direction / direction_norm))

    baselines = [
        float(np.linalg.norm(left[0] - right[0]))
        for left, right in itertools.combinations(normalized_rays, 2)
    ]
    if max(baselines) <= np.finfo(float).eps:
        raise GeometryError(
            "Calibrated observations have no camera baseline, so depth is unavailable"
        )

    system = np.zeros((3, 3), dtype=float)
    right_hand = np.zeros(3, dtype=float)
    identity = np.eye(3)
    for origin, direction in normalized_rays:
        projector = identity - np.outer(direction, direction)
        system += projector
        right_hand += projector @ origin
    if np.linalg.matrix_rank(system, tol=1e-12) < 3:
        raise GeometryError("Viewing rays are parallel or geometrically degenerate")
    condition_number = float(np.linalg.cond(system))
    if not math.isfinite(condition_number):
        raise GeometryError("Viewing-ray triangulation system is ill-conditioned")
    position = np.linalg.solve(system, right_hand)
    depths = np.array(
        [direction @ (position - origin) for origin, direction in normalized_rays],
        dtype=float,
    )
    if np.any(depths <= np.finfo(float).eps):
        raise GeometryError(
            "Triangulated point is not in front of every supporting camera"
        )
    residuals = np.array(
        [
            np.linalg.norm(
                (identity - np.outer(direction, direction)) @ (position - origin)
            )
            for origin, direction in normalized_rays
        ],
        dtype=float,
    )
    angles = []
    for left, right in itertools.combinations(normalized_rays, 2):
        # Triangulation is constrained by the angle between *lines*.  Taking
        # the absolute value avoids incorrectly treating two cameras that view
        # an object from opposite directions as 180-degree parallax.
        cosine = float(np.clip(abs(left[1] @ right[1]), -1.0, 1.0))
        angles.append(math.degrees(math.acos(cosine)))
    return TriangulationEstimate(
        position=position,
        ray_residuals=residuals,
        ray_depths=depths,
        condition_number=condition_number,
        pairwise_ray_angles_degrees=tuple(angles),
        median_camera_baseline=float(np.median(baselines)),
    )
