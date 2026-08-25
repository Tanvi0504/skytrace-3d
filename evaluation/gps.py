"""Controlled GPS perturbation helpers for Step 8."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any


def perturb_gps_metadata(
    source_path: str | Path,
    output_path: str | Path,
    *,
    horizontal_noise_metres: float,
    altitude_noise_metres: float = 0.0,
    seed: int = 0,
) -> dict[str, Any]:
    """Write a controlled GPS-noise copy of metadata without claiming it is a real distribution."""
    if horizontal_noise_metres < 0 or altitude_noise_metres < 0:
        raise ValueError("GPS noise magnitudes must be non-negative")
    source = Path(source_path)
    output = Path(output_path)
    document = json.loads(source.read_text(encoding="utf-8"))
    observations = document.get("observations", document if isinstance(document, list) else None)
    if not isinstance(observations, list):
        raise ValueError("GPS metadata must be a list or contain an observations array")

    rng = random.Random(seed)
    perturbed = []
    for item in observations:
        if not isinstance(item, dict):
            raise ValueError("GPS observation must be an object")
        latitude = float(item["latitude"])
        longitude = float(item["longitude"])
        altitude = float(item.get("altitude", item.get("altitude_metres", 0.0)))
        bearing = rng.uniform(0.0, math.tau)
        radius = horizontal_noise_metres
        north = math.cos(bearing) * radius
        east = math.sin(bearing) * radius
        metres_per_degree_lat = 111_320.0
        metres_per_degree_lon = max(1e-9, 111_320.0 * math.cos(math.radians(latitude)))
        clone = dict(item)
        clone["latitude"] = latitude + north / metres_per_degree_lat
        clone["longitude"] = longitude + east / metres_per_degree_lon
        clone["altitude"] = altitude + rng.uniform(-altitude_noise_metres, altitude_noise_metres)
        clone["controlled_perturbation"] = {
            "horizontal_noise_metres": horizontal_noise_metres,
            "altitude_noise_metres": altitude_noise_metres,
            "east_offset_metres": east,
            "north_offset_metres": north,
        }
        perturbed.append(clone)

    payload = dict(document) if isinstance(document, dict) else {"observations": observations}
    payload["observations"] = perturbed
    payload["controlled_experiment"] = {
        "type": "gps_noise",
        "horizontal_noise_metres": horizontal_noise_metres,
        "altitude_noise_metres": altitude_noise_metres,
        "seed": seed,
        "distribution_note": "Fixed-radius random bearing perturbation for stress testing, not a GPS error model.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
