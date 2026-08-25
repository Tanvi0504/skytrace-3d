"""Flexible GPS CSV/JSON reader for externally supplied flight metadata."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from pipeline.georeferencing.errors import GPSMetadataError
from pipeline.georeferencing.models import GPSDataset, GPSObservation

_LATITUDE_FIELDS = ("latitude", "lat", "gps_latitude")
_LONGITUDE_FIELDS = ("longitude", "lon", "lng", "gps_longitude")
_ALTITUDE_FIELDS = (
    "altitude",
    "altitude_m",
    "altitude_metres",
    "altitude_meters",
    "height",
    "gps_altitude",
    "relative_altitude",
)
_TIMESTAMP_FIELDS = ("timestamp", "timestamp_seconds", "time", "time_seconds")
_FRAME_FIELDS = ("frame_index", "frame_number", "frame", "image_id")
_IMAGE_FIELDS = ("image_name", "filename", "frame_filename", "image", "file")


def _normalise_record(record: dict[str, Any]) -> dict[str, Any]:
    return {str(key).strip().lower(): value for key, value in record.items()}


def _first_value(record: dict[str, Any], field_names: Iterable[str]) -> Any:
    for field_name in field_names:
        value = record.get(field_name)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _float_value(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _optional_timestamp(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return _float_value(value, "timestamp")
    except ValueError:
        try:
            text = str(value).replace("Z", "+00:00")
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                raise ValueError("ISO timestamp requires an explicit timezone")
            return parsed.timestamp()
        except (TypeError, ValueError) as exc:
            raise ValueError("timestamp must be numeric seconds or ISO-8601 with timezone") from exc


def _optional_frame_index(value: Any) -> Optional[int]:
    if value is None:
        return None
    numeric = _float_value(value, "frame_index")
    if not numeric.is_integer() or numeric < 0:
        raise ValueError("frame_index must be a non-negative integer")
    return int(numeric)


def _parse_observation(record: dict[str, Any], observation_id: str) -> GPSObservation:
    normalised = _normalise_record(record)
    latitude = _float_value(_first_value(normalised, _LATITUDE_FIELDS), "latitude")
    longitude = _float_value(_first_value(normalised, _LONGITUDE_FIELDS), "longitude")
    altitude = _float_value(_first_value(normalised, _ALTITUDE_FIELDS), "altitude")
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude must be within [-90, 90]")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError("longitude must be within [-180, 180]")
    image_value = _first_value(normalised, _IMAGE_FIELDS)
    image_name = str(image_value).strip() if image_value is not None else None
    return GPSObservation(
        observation_id=observation_id,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        timestamp_seconds=_optional_timestamp(_first_value(normalised, _TIMESTAMP_FIELDS)),
        frame_index=_optional_frame_index(_first_value(normalised, _FRAME_FIELDS)),
        image_name=image_name or None,
    )


def _read_json(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GPSMetadataError(f"GPS JSON is invalid: {path}: {exc}") from exc
    if isinstance(document, list):
        records, metadata = document, {}
    elif isinstance(document, dict):
        metadata = document
        records = next(
            (
                document[key]
                for key in ("observations", "gps", "records")
                if isinstance(document.get(key), list)
            ),
            None,
        )
    else:
        records, metadata = None, {}
    if not isinstance(records, list):
        raise GPSMetadataError(
            "GPS JSON must be an array or an object containing an "
            "'observations', 'gps', or 'records' array"
        )
    if not all(isinstance(record, dict) for record in records):
        raise GPSMetadataError("Every GPS JSON observation must be an object")
    return records, metadata


def _read_csv(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            if reader.fieldnames is None:
                raise GPSMetadataError("GPS CSV must include a header row")
            return list(reader), {}
    except UnicodeDecodeError as exc:
        raise GPSMetadataError(f"GPS CSV is not UTF-8 text: {path}") from exc


def load_gps_metadata(path: Path) -> GPSDataset:
    """Load valid GPS observations from documented CSV or JSON inputs.

    Invalid rows are not silently used: they are omitted and described in the
    returned warnings. At least one fully valid 3D observation is required.
    """
    if not path.exists() or not path.is_file():
        raise GPSMetadataError(f"GPS metadata file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        records, metadata = _read_json(path)
    elif suffix == ".csv":
        records, metadata = _read_csv(path)
    else:
        raise GPSMetadataError("GPS metadata must use a .csv or .json extension")

    observations: list[GPSObservation] = []
    warnings: list[str] = []
    for index, record in enumerate(records, start=1):
        try:
            observations.append(_parse_observation(record, f"row_{index}"))
        except ValueError as exc:
            warnings.append(f"Ignored GPS row {index}: {exc}.")
    if not observations:
        reason = " ".join(warnings) if warnings else "The file contains no rows."
        raise GPSMetadataError(f"No valid 3D GPS observations were found. {reason}")

    normalised_metadata = _normalise_record(metadata)
    source_crs = str(
        _first_value(normalised_metadata, ("coordinate_system", "crs", "source_crs"))
        or "WGS 84 geographic latitude/longitude (assumed)"
    )
    altitude_reference = str(
        _first_value(normalised_metadata, ("altitude_reference", "vertical_datum"))
        or "supplied altitude datum (not declared)"
    )
    if "assumed" in source_crs:
        warnings.append(
            "GPS source CRS was not declared; WGS-84 geographic latitude/longitude "
            "was assumed."
        )
    if "not declared" in altitude_reference:
        warnings.append(
            "GPS altitude datum was not declared. ENU vertical differences are used, "
            "but absolute height interpretation is limited."
        )
    return GPSDataset(
        observations=observations,
        source_coordinate_system=source_crs,
        altitude_reference=altitude_reference,
        warnings=warnings,
    )
