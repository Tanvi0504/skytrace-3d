"""Unit-safe geometric measurement primitives for Step 6."""

from __future__ import annotations

from typing import Iterable

import numpy as np

from pipeline.analysis.errors import MeasurementInputError
from pipeline.analysis.models import DistanceMeasurement

_UNIT_ALIASES = {
    "m": "m",
    "metre": "m",
    "metres": "m",
    "meter": "m",
    "meters": "m",
    "cm": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "centimeter": "cm",
    "centimeters": "cm",
    "km": "km",
    "kilometre": "km",
    "kilometres": "km",
    "kilometer": "km",
    "kilometers": "km",
}
_METRES_TO_UNIT = {"m": 1.0, "cm": 100.0, "km": 0.001}


def normalize_unit(unit: str) -> str:
    """Return one supported display unit while retaining metre calculations."""
    normalised = _UNIT_ALIASES.get(str(unit).strip().lower())
    if normalised is None:
        raise MeasurementInputError("unit must be one of: m, cm, km")
    return normalised


def _point(value: Iterable[float], label: str) -> np.ndarray:
    try:
        point = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise MeasurementInputError(f"{label} must contain three finite coordinates") from exc
    if point.shape != (3,) or not np.all(np.isfinite(point)):
        raise MeasurementInputError(f"{label} must contain three finite coordinates")
    return point


def convert_distance(distance_metres: float, unit: str) -> float:
    """Convert a finite metre value only at the presentation boundary."""
    if not np.isfinite(distance_metres):
        raise MeasurementInputError("distance_metres must be finite")
    return float(distance_metres) * _METRES_TO_UNIT[normalize_unit(unit)]


def measure_distance(
    point_a: Iterable[float],
    point_b: Iterable[float],
    *,
    unit: str = "m",
    horizontal_and_vertical_meaningful: bool = True,
) -> DistanceMeasurement:
    """Calculate distinct 3D, horizontal, and vertical distances in metres.

    ``horizontal_and_vertical_meaningful`` should only be true for a coordinate
    frame with documented horizontal axes and an Up/vertical axis, such as
    Step 3's local ENU metres.
    """
    a = _point(point_a, "point_a")
    b = _point(point_b, "point_b")
    selected_unit = normalize_unit(unit)
    delta = b - a
    distance_3d = float(np.linalg.norm(delta))
    horizontal = float(np.linalg.norm(delta[:2])) if horizontal_and_vertical_meaningful else None
    vertical = float(abs(delta[2])) if horizontal_and_vertical_meaningful else None
    return DistanceMeasurement(
        point_a=a,
        point_b=b,
        distance_3d_metres=distance_3d,
        horizontal_distance_metres=horizontal,
        vertical_difference_metres=vertical,
        unit=selected_unit,
    )
