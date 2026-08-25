"""Minimal, safe PLY point-cloud coordinate transformation support."""

from __future__ import annotations

import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pipeline.georeferencing.errors import PointCloudError
from pipeline.georeferencing.models import SimilarityTransform

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
class _VertexLayout:
    format_name: str
    vertex_count: int
    scalar_types: tuple[str, ...]
    property_names: tuple[str, ...]
    header: bytes

    @property
    def x_index(self) -> int:
        return self.property_names.index("x")

    @property
    def y_index(self) -> int:
        return self.property_names.index("y")

    @property
    def z_index(self) -> int:
        return self.property_names.index("z")


def _read_vertex_layout(source) -> _VertexLayout:
    header_lines: list[bytes] = []
    first_line = source.readline()
    if first_line != b"ply\n" and first_line != b"ply\r\n":
        raise PointCloudError("Point cloud is not a PLY file")
    header_lines.append(first_line)
    format_name: str | None = None
    elements: list[dict] = []
    current: dict | None = None
    while True:
        line = source.readline()
        if not line:
            raise PointCloudError("PLY header ended before end_header")
        header_lines.append(line)
        decoded = line.decode("ascii", errors="strict").strip()
        parts = decoded.split()
        if parts[:1] == ["format"] and len(parts) >= 2:
            format_name = parts[1]
        elif parts[:1] == ["element"] and len(parts) == 3:
            try:
                current = {"name": parts[1], "count": int(parts[2]), "properties": []}
            except ValueError as exc:
                raise PointCloudError("PLY element count is invalid") from exc
            elements.append(current)
        elif parts[:1] == ["property"]:
            if current is None:
                raise PointCloudError("PLY property appeared before an element")
            current["properties"].append(parts[1:])
        elif decoded == "end_header":
            break

    if format_name not in {"ascii", "binary_little_endian"}:
        raise PointCloudError(
            "Only ASCII and binary_little_endian PLY are supported for transformation"
        )
    vertex_index = next(
        (index for index, element in enumerate(elements) if element["name"] == "vertex"),
        None,
    )
    if vertex_index != 0:
        raise PointCloudError(
            "PLY must store its vertex element first so Step 3 can preserve other data"
        )
    vertex = elements[0]
    scalar_types: list[str] = []
    property_names: list[str] = []
    for property_specification in vertex["properties"]:
        if len(property_specification) != 2 or property_specification[0] == "list":
            raise PointCloudError("PLY vertex properties must be scalar values")
        scalar_type, property_name = property_specification
        if scalar_type not in _PLY_SCALAR_FORMATS:
            raise PointCloudError(f"Unsupported PLY scalar type: {scalar_type}")
        scalar_types.append(scalar_type)
        property_names.append(property_name)
    if not {"x", "y", "z"}.issubset(property_names):
        raise PointCloudError("PLY vertex properties must include x, y, and z")
    for coordinate in ("x", "y", "z"):
        scalar_type = scalar_types[property_names.index(coordinate)]
        if scalar_type not in {"float", "float32", "double", "float64"}:
            raise PointCloudError(
                f"PLY coordinate property {coordinate} must be a floating-point scalar"
            )
    return _VertexLayout(
        format_name=format_name,
        vertex_count=vertex["count"],
        scalar_types=tuple(scalar_types),
        property_names=tuple(property_names),
        header=b"".join(header_lines),
    )


def _transform_ascii(
    source,
    destination,
    layout: _VertexLayout,
    transform: SimilarityTransform,
) -> None:
    body = source.read().decode("ascii", errors="strict")
    lines = body.splitlines(keepends=True)
    if len(lines) < layout.vertex_count:
        raise PointCloudError("ASCII PLY ended before all vertices were read")
    destination.write(layout.header)
    for index, line in enumerate(lines):
        if index >= layout.vertex_count:
            destination.write(line.encode("ascii"))
            continue
        newline = "\n" if line.endswith("\n") else ""
        fields = line.strip().split()
        if len(fields) != len(layout.property_names):
            raise PointCloudError(f"ASCII PLY vertex {index} has an unexpected property count")
        try:
            point = np.array(
                [
                    float(fields[layout.x_index]),
                    float(fields[layout.y_index]),
                    float(fields[layout.z_index]),
                ]
            )
        except ValueError as exc:
            raise PointCloudError(f"ASCII PLY vertex {index} has invalid coordinates") from exc
        transformed = transform.apply(point)
        fields[layout.x_index] = f"{transformed[0]:.12g}"
        fields[layout.y_index] = f"{transformed[1]:.12g}"
        fields[layout.z_index] = f"{transformed[2]:.12g}"
        destination.write((" ".join(fields) + newline).encode("ascii"))


def _transform_binary_little_endian(
    source,
    destination,
    layout: _VertexLayout,
    transform: SimilarityTransform,
) -> None:
    record_format = "<" + "".join(
        _PLY_SCALAR_FORMATS[scalar_type] for scalar_type in layout.scalar_types
    )
    record_size = struct.calcsize(record_format)
    destination.write(layout.header)
    for index in range(layout.vertex_count):
        raw_record = source.read(record_size)
        if len(raw_record) != record_size:
            raise PointCloudError("Binary PLY ended before all vertices were read")
        values = list(struct.unpack(record_format, raw_record))
        transformed = transform.apply(
            np.array([values[layout.x_index], values[layout.y_index], values[layout.z_index]])
        )
        values[layout.x_index] = transformed[0]
        values[layout.y_index] = transformed[1]
        values[layout.z_index] = transformed[2]
        destination.write(struct.pack(record_format, *values))
    shutil.copyfileobj(source, destination)


def transform_ply(
    input_path: Path,
    output_path: Path,
    transform: SimilarityTransform,
) -> None:
    """Apply a source-to-ENU transform while preserving non-coordinate PLY data."""
    if not input_path.is_file():
        raise PointCloudError(f"Point-cloud PLY not found: {input_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.tmp")
    try:
        with input_path.open("rb") as source, temporary_path.open("wb") as destination:
            layout = _read_vertex_layout(source)
            if layout.format_name == "ascii":
                _transform_ascii(source, destination, layout, transform)
            else:
                _transform_binary_little_endian(source, destination, layout, transform)
        temporary_path.replace(output_path)
    except PointCloudError:
        temporary_path.unlink(missing_ok=True)
        raise
    except (OSError, UnicodeDecodeError, struct.error) as exc:
        temporary_path.unlink(missing_ok=True)
        raise PointCloudError(f"Could not transform PLY {input_path}: {exc}") from exc
