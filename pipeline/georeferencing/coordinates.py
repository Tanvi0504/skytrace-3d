"""WGS-84 geographic/ECEF/local-ENU coordinate conversion helpers."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np

from pipeline.georeferencing.models import GPSObservation, LocalENUReference

# WGS-84 semi-major axis and inverse flattening.  These constants are used for
# a local tangent-plane conversion, avoiding the invalid practice of treating
# latitude/longitude degrees as Cartesian x/y values.
WGS84_SEMI_MAJOR_AXIS_METRES = 6_378_137.0
WGS84_INVERSE_FLATTENING = 298.257223563
WGS84_FLATTENING = 1.0 / WGS84_INVERSE_FLATTENING
WGS84_ECCENTRICITY_SQUARED = WGS84_FLATTENING * (2.0 - WGS84_FLATTENING)


def geodetic_to_ecef(
    latitude_degrees: float,
    longitude_degrees: float,
    altitude_metres: float,
) -> np.ndarray:
    """Convert WGS-84 latitude/longitude/ellipsoidal height to ECEF metres."""
    latitude = math.radians(latitude_degrees)
    longitude = math.radians(longitude_degrees)
    sin_latitude = math.sin(latitude)
    cos_latitude = math.cos(latitude)
    radius = WGS84_SEMI_MAJOR_AXIS_METRES / math.sqrt(
        1.0 - WGS84_ECCENTRICITY_SQUARED * sin_latitude * sin_latitude
    )
    return np.array(
        [
            (radius + altitude_metres) * cos_latitude * math.cos(longitude),
            (radius + altitude_metres) * cos_latitude * math.sin(longitude),
            (radius * (1.0 - WGS84_ECCENTRICITY_SQUARED) + altitude_metres)
            * sin_latitude,
        ],
        dtype=float,
    )


def ecef_to_geodetic(ecef_metres: np.ndarray) -> tuple[float, float, float]:
    """Convert WGS-84 ECEF metres to latitude, longitude, and height.

    This inverse is primarily useful for synthetic tests and round-trip checks.
    """
    x, y, z = (float(value) for value in ecef_metres)
    longitude = math.atan2(y, x)
    horizontal = math.hypot(x, y)
    latitude = math.atan2(z, horizontal * (1.0 - WGS84_ECCENTRICITY_SQUARED))
    altitude = 0.0
    for _ in range(10):
        sin_latitude = math.sin(latitude)
        radius = WGS84_SEMI_MAJOR_AXIS_METRES / math.sqrt(
            1.0 - WGS84_ECCENTRICITY_SQUARED * sin_latitude * sin_latitude
        )
        altitude = horizontal / math.cos(latitude) - radius
        updated = math.atan2(
            z,
            horizontal
            * (
                1.0
                - WGS84_ECCENTRICITY_SQUARED
                * radius
                / (radius + altitude)
            ),
        )
        if abs(updated - latitude) < 1e-13:
            latitude = updated
            break
        latitude = updated
    return math.degrees(latitude), math.degrees(longitude), altitude


def enu_rotation_matrix(reference: LocalENUReference) -> np.ndarray:
    """Return the ECEF-to-ENU rotation at a WGS-84 local tangent origin."""
    latitude = math.radians(reference.latitude)
    longitude = math.radians(reference.longitude)
    sin_latitude = math.sin(latitude)
    cos_latitude = math.cos(latitude)
    sin_longitude = math.sin(longitude)
    cos_longitude = math.cos(longitude)
    return np.array(
        [
            [-sin_longitude, cos_longitude, 0.0],
            [-sin_latitude * cos_longitude, -sin_latitude * sin_longitude, cos_latitude],
            [cos_latitude * cos_longitude, cos_latitude * sin_longitude, sin_latitude],
        ],
        dtype=float,
    )


def geodetic_to_enu(
    latitude_degrees: float,
    longitude_degrees: float,
    altitude_metres: float,
    reference: LocalENUReference,
) -> np.ndarray:
    """Convert a WGS-84 geographic point into local ENU metres."""
    point_ecef = geodetic_to_ecef(
        latitude_degrees, longitude_degrees, altitude_metres
    )
    reference_ecef = geodetic_to_ecef(
        reference.latitude, reference.longitude, reference.altitude
    )
    return enu_rotation_matrix(reference) @ (point_ecef - reference_ecef)


def enu_to_geodetic(
    enu_metres: np.ndarray,
    reference: LocalENUReference,
) -> tuple[float, float, float]:
    """Convert local ENU metres back to WGS-84 geographic coordinates."""
    reference_ecef = geodetic_to_ecef(
        reference.latitude, reference.longitude, reference.altitude
    )
    ecef = reference_ecef + enu_rotation_matrix(reference).T @ np.asarray(
        enu_metres, dtype=float
    )
    return ecef_to_geodetic(ecef)


def choose_enu_reference(
    observations: Iterable[GPSObservation],
) -> LocalENUReference:
    """Choose a reproducible median GPS origin for a compact local scene."""
    values = list(observations)
    if not values:
        raise ValueError("Cannot choose a local ENU origin without GPS observations")
    return LocalENUReference(
        latitude=float(np.median([item.latitude for item in values])),
        longitude=float(np.median([item.longitude for item in values])),
        altitude=float(np.median([item.altitude for item in values])),
    )
