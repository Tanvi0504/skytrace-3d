"""Readers and lightweight spatial indexing for existing Step 3/5 artifacts."""

from __future__ import annotations

import csv
import json
import math
import struct
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from pipeline.analysis.errors import MeasurementInputError, SceneInputError
from pipeline.analysis.measurements import normalize_unit
from pipeline.analysis.models import EvidenceConfig, MeasurementRequest

_PLY_SCALAR_FORMATS = {
    "char": "b",
    "int8": "b",
    "uchar": "B",
    "uint8": "B",
    "short": "h",
    "int16": "h",
    "ushort": "H",
    "uint16": "H",
    "int": "i",
    "int32": "i",
    "uint": "I",
    "uint32": "I",
    "float": "f",
    "float32": "f",
    "double": "d",
    "float64": "d",
}


@dataclass(frozen=True)
class _PlyVertexLayout:
    format_name: str
    vertex_count: int
    scalar_types: tuple[str, ...]
    property_names: tuple[str, ...]

    @property
    def x_index(self) -> int:
        return self.property_names.index("x")

    @property
    def y_index(self) -> int:
        return self.property_names.index("y")

    @property
    def z_index(self) -> int:
        return self.property_names.index("z")


def _read_ply_layout(source) -> _PlyVertexLayout:
    if source.readline().strip() != b"ply":
        raise SceneInputError("Step 3 point cloud is not a PLY file")
    format_name: str | None = None
    elements: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    while True:
        line = source.readline()
        if not line:
            raise SceneInputError("PLY header ended before end_header")
        try:
            parts = line.decode("ascii", errors="strict").strip().split()
        except UnicodeDecodeError as exc:
            raise SceneInputError("PLY header must be ASCII") from exc
        if not parts or parts[0] in {"comment", "obj_info"}:
            continue
        if parts[0] == "format" and len(parts) >= 2:
            format_name = parts[1]
        elif parts[0] == "element" and len(parts) == 3:
            try:
                current = {"name": parts[1], "count": int(parts[2]), "properties": []}
            except ValueError as exc:
                raise SceneInputError("PLY element count is invalid") from exc
            elements.append(current)
        elif parts[0] == "property":
            if current is None:
                raise SceneInputError("PLY property appeared before an element")
            current["properties"].append(parts[1:])
        elif parts[0] == "end_header":
            break
    if format_name not in {"ascii", "binary_little_endian"}:
        raise SceneInputError("Step 6 supports ASCII and binary_little_endian PLY only")
    if not elements or elements[0]["name"] != "vertex":
        raise SceneInputError("PLY must store the vertex element first")
    vertex = elements[0]
    scalar_types: list[str] = []
    names: list[str] = []
    for specification in vertex["properties"]:
        if len(specification) != 2 or specification[0] == "list":
            raise SceneInputError("PLY vertex properties must be scalar values")
        scalar_type, name = specification
        if scalar_type not in _PLY_SCALAR_FORMATS:
            raise SceneInputError(f"Unsupported PLY scalar type: {scalar_type}")
        scalar_types.append(scalar_type)
        names.append(name)
    if not {"x", "y", "z"}.issubset(names):
        raise SceneInputError("PLY vertices must contain x, y, and z coordinates")
    return _PlyVertexLayout(
        format_name=format_name,
        vertex_count=vertex["count"],
        scalar_types=tuple(scalar_types),
        property_names=tuple(names),
    )


def load_ply_points(path: Path) -> np.ndarray:
    """Read only Step 3 point coordinates; no PLY copy is written."""
    if not path.is_file():
        raise SceneInputError(f"Georeferenced point cloud not found: {path}")
    try:
        with path.open("rb") as source:
            layout = _read_ply_layout(source)
            points = np.empty((layout.vertex_count, 3), dtype=float)
            if layout.format_name == "ascii":
                for index in range(layout.vertex_count):
                    fields = source.readline().decode("ascii", errors="strict").split()
                    if len(fields) != len(layout.property_names):
                        raise SceneInputError(
                            f"ASCII PLY vertex {index} has an unexpected property count"
                        )
                    points[index] = (
                        float(fields[layout.x_index]),
                        float(fields[layout.y_index]),
                        float(fields[layout.z_index]),
                    )
            else:
                record_format = "<" + "".join(
                    _PLY_SCALAR_FORMATS[item] for item in layout.scalar_types
                )
                record_size = struct.calcsize(record_format)
                for index in range(layout.vertex_count):
                    raw = source.read(record_size)
                    if len(raw) != record_size:
                        raise SceneInputError("Binary PLY ended before all vertices were read")
                    values = struct.unpack(record_format, raw)
                    points[index] = (
                        values[layout.x_index],
                        values[layout.y_index],
                        values[layout.z_index],
                    )
    except (OSError, UnicodeDecodeError, ValueError, struct.error) as exc:
        if isinstance(exc, SceneInputError):
            raise
        raise SceneInputError(f"Could not read georeferenced point cloud: {exc}") from exc
    if points.size == 0:
        raise SceneInputError("Georeferenced point cloud contains no vertices")
    if not np.all(np.isfinite(points)):
        raise SceneInputError("Georeferenced point cloud contains non-finite coordinates")
    return points


class SpatialPointIndex:
    """Small dependency-free grid index for local point-density queries."""

    def __init__(self, points: np.ndarray, cell_size_metres: float) -> None:
        self.points = np.asarray(points, dtype=float)
        self.cell_size_metres = float(cell_size_metres)
        cells = np.floor(self.points / self.cell_size_metres).astype(np.int64)
        buckets: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        for index, cell in enumerate(cells):
            buckets[tuple(int(value) for value in cell)].append(index)
        self._buckets = dict(buckets)

    def count_within(self, point: np.ndarray, radius_metres: float) -> int:
        """Count actual PLY vertices inside a spherical local-neighbourhood."""
        centre = np.floor(point / self.cell_size_metres).astype(np.int64)
        span = int(math.ceil(radius_metres / self.cell_size_metres))
        candidates: list[int] = []
        for x in range(int(centre[0] - span), int(centre[0] + span + 1)):
            for y in range(int(centre[1] - span), int(centre[1] + span + 1)):
                for z in range(int(centre[2] - span), int(centre[2] + span + 1)):
                    candidates.extend(self._buckets.get((x, y, z), ()))
        if not candidates:
            return 0
        nearby = self.points[np.asarray(candidates, dtype=int)]
        squared_distance = np.sum((nearby - point) ** 2, axis=1)
        return int(np.count_nonzero(squared_distance <= radius_metres**2))


@dataclass(frozen=True)
class SceneContext:
    """Data that Step 6 can safely derive from existing Step 3/5 files."""

    scene_dir: Path
    point_cloud_path: Path
    target_coordinate_system: str
    points: np.ndarray
    point_index: SpatialPointIndex
    camera_centres: np.ndarray
    dynamic_marker_positions: np.ndarray
    warnings: tuple[str, ...]

    @property
    def has_meaningful_vertical_axis(self) -> bool:
        lower = self.target_coordinate_system.lower()
        return "enu" in lower or "east-north-up" in lower


def _load_target_coordinate_system(scene_dir: Path) -> str:
    path = scene_dir / "transform.json"
    if not path.is_file():
        raise SceneInputError(
            f"Step 3 transform.json was not found: {path}. Metric measurement is unavailable."
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        target = str(document["target_coordinate_system"]).strip()
        matrix = np.asarray(document["transform"]["matrix_4x4"], dtype=float)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SceneInputError(f"Step 3 transform.json is invalid: {exc}") from exc
    if matrix.shape != (4, 4) or not np.all(np.isfinite(matrix)):
        raise SceneInputError("Step 3 transform.json must contain a finite transform.matrix_4x4")
    lower = target.lower()
    if not target or ("metre" not in lower and "meter" not in lower):
        raise SceneInputError(
            "Step 3 target coordinate system does not declare metre units; metric measurement is unavailable."
        )
    return target


def _load_camera_centres(scene_dir: Path) -> tuple[np.ndarray, list[str]]:
    path = scene_dir / "camera_trajectory_georef.csv"
    if not path.is_file():
        return np.empty((0, 3), dtype=float), [
            "Step 3 camera_trajectory_georef.csv is unavailable; nearby-camera evidence is zero."
        ]
    centres: list[list[float]] = []
    warnings: list[str] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as source:
            for row_number, row in enumerate(csv.DictReader(source), start=2):
                try:
                    point = [
                        float(row["enu_east_m"]),
                        float(row["enu_north_m"]),
                        float(row["enu_up_m"]),
                    ]
                    if not np.all(np.isfinite(point)):
                        raise ValueError("coordinates are not finite")
                    centres.append(point)
                except (KeyError, TypeError, ValueError) as exc:
                    warnings.append(f"Ignored malformed georeferenced camera row {row_number}: {exc}.")
    except OSError as exc:
        return np.empty((0, 3), dtype=float), [f"Could not read camera trajectory: {exc}"]
    if not centres:
        warnings.append("No usable Step 3 camera centers are available for camera-support evidence.")
    return np.asarray(centres, dtype=float).reshape((-1, 3)), warnings


def _load_dynamic_marker_positions(
    scene_objects_dir: Path | None,
    target_coordinate_system: str,
) -> tuple[np.ndarray, list[str]]:
    if scene_objects_dir is None:
        return np.empty((0, 3), dtype=float), [
            "No Step 5 scene-object directory was supplied; dynamic contamination is unassessed."
        ]
    path = scene_objects_dir / "objects_3d.json"
    if not path.is_file():
        return np.empty((0, 3), dtype=float), [
            f"Step 5 objects_3d.json was not found: {path}; dynamic contamination is unassessed."
        ]
    warnings: list[str] = []
    positions: list[np.ndarray] = []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        objects = document["objects"]
        if not isinstance(objects, list):
            raise ValueError("objects must be an array")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return np.empty((0, 3), dtype=float), [
            f"Step 5 dynamic-object evidence is invalid and was not used: {exc}"
        ]
    for row_number, record in enumerate(objects, start=1):
        if not isinstance(record, dict) or not record.get("is_dynamic_candidate"):
            continue
        if record.get("coordinate_system") != target_coordinate_system:
            warnings.append(
                f"Ignored dynamic Step 5 marker {row_number}: its coordinate system does not match Step 3."
            )
            continue
        try:
            point = np.asarray(record["world_position"], dtype=float)
            if point.shape != (3,) or not np.all(np.isfinite(point)):
                raise ValueError("world_position must contain three finite coordinates")
            positions.append(point)
        except (KeyError, TypeError, ValueError) as exc:
            warnings.append(f"Ignored dynamic Step 5 marker {row_number}: {exc}.")
    if not positions:
        warnings.append("No usable dynamic Step 5 markers overlap the Step 3 coordinate system.")
    return np.asarray(positions, dtype=float).reshape((-1, 3)), warnings


def load_scene_context(
    scene_dir: Path,
    scene_objects_dir: Path | None,
    evidence_config: EvidenceConfig,
) -> SceneContext:
    """Load metre-valued Step 3 geometry and optional Step 5 marker evidence."""
    if not scene_dir.is_dir():
        raise SceneInputError(f"Step 3 georeferenced scene directory not found: {scene_dir}")
    target = _load_target_coordinate_system(scene_dir)
    point_cloud_path = scene_dir / "point_cloud_georef.ply"
    points = load_ply_points(point_cloud_path)
    cameras, camera_warnings = _load_camera_centres(scene_dir)
    dynamics, object_warnings = _load_dynamic_marker_positions(scene_objects_dir, target)
    return SceneContext(
        scene_dir=scene_dir,
        point_cloud_path=point_cloud_path,
        target_coordinate_system=target,
        points=points,
        point_index=SpatialPointIndex(points, evidence_config.density_radius_metres),
        camera_centres=cameras,
        dynamic_marker_positions=dynamics,
        warnings=tuple(camera_warnings + object_warnings),
    )


def _measurement_point(value: Any, label: str) -> np.ndarray:
    try:
        point = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise MeasurementInputError(f"{label} must contain three finite coordinates") from exc
    if point.shape != (3,) or not np.all(np.isfinite(point)):
        raise MeasurementInputError(f"{label} must contain three finite coordinates")
    return point


def load_measurement_requests(path: Path) -> list[MeasurementRequest]:
    """Read an optional stable JSON request list for the Step 6 CLI."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        records = document["measurements"] if isinstance(document, dict) else document
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MeasurementInputError(f"Measurement request JSON is invalid: {exc}") from exc
    if not isinstance(records, list):
        raise MeasurementInputError("Measurement request JSON must contain a 'measurements' array")
    requests: list[MeasurementRequest] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        try:
            if not isinstance(record, dict):
                raise ValueError("record is not an object")
            measurement_id = str(record.get("measurement_id", f"measurement_{index}")).strip()
            if not measurement_id or measurement_id in seen_ids:
                raise ValueError("measurement_id must be non-empty and unique")
            seen_ids.add(measurement_id)
            requests.append(
                MeasurementRequest(
                    measurement_id=measurement_id,
                    point_a=_measurement_point(record["point_a"], "point_a"),
                    point_b=_measurement_point(record["point_b"], "point_b"),
                    unit=normalize_unit(record.get("unit", "m")),
                )
            )
        except (KeyError, TypeError, ValueError, MeasurementInputError) as exc:
            raise MeasurementInputError(f"Measurement request {index} is invalid: {exc}") from exc
    return requests
