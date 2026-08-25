"""Camera-to-GPS correspondence matching by identifier, frame, then time."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np

from pipeline.georeferencing.models import CameraPose, Correspondence, GPSObservation
from pipeline.georeferencing.reconstruction import frame_index_from_image_name


def _normalise_image_name(value: str) -> str:
    return Path(value).name.lower()


def _choose_direct_observation(
    candidates: list[GPSObservation],
    pose: CameraPose,
    label: str,
    warnings: list[str],
) -> GPSObservation | None:
    if len(candidates) == 1:
        return candidates[0]
    if pose.timestamp_seconds is not None:
        timestamped = [item for item in candidates if item.timestamp_seconds is not None]
        if timestamped:
            return min(
                timestamped,
                key=lambda item: abs(item.timestamp_seconds - pose.timestamp_seconds),
            )
    warnings.append(
        f"Skipped {pose.image_name}: multiple GPS observations share its {label} "
        "and cannot be disambiguated."
    )
    return None


def _interpolate_timestamp_position(
    pose: CameraPose,
    observations: list[GPSObservation],
    positions: dict[str, np.ndarray],
    tolerance_seconds: float,
) -> tuple[np.ndarray, tuple[str, ...]] | None:
    if pose.timestamp_seconds is None:
        return None
    grouped: dict[float, list[GPSObservation]] = defaultdict(list)
    for observation in observations:
        if observation.timestamp_seconds is not None:
            grouped[observation.timestamp_seconds].append(observation)
    if not grouped:
        return None
    times = np.array(sorted(grouped), dtype=float)
    query = pose.timestamp_seconds
    insertion = int(np.searchsorted(times, query))
    if insertion < len(times) and abs(times[insertion] - query) < 1e-9:
        group = grouped[float(times[insertion])]
        return (
            np.mean([positions[item.observation_id] for item in group], axis=0),
            tuple(item.observation_id for item in group),
        )
    if insertion == 0 or insertion == len(times):
        return None
    earlier, later = float(times[insertion - 1]), float(times[insertion])
    if query - earlier > tolerance_seconds or later - query > tolerance_seconds:
        return None
    earlier_group = grouped[earlier]
    later_group = grouped[later]
    earlier_position = np.mean(
        [positions[item.observation_id] for item in earlier_group], axis=0
    )
    later_position = np.mean(
        [positions[item.observation_id] for item in later_group], axis=0
    )
    fraction = (query - earlier) / (later - earlier)
    return (
        earlier_position + fraction * (later_position - earlier_position),
        tuple(item.observation_id for item in earlier_group + later_group),
    )


def match_camera_poses_to_gps(
    poses: list[CameraPose],
    observations: list[GPSObservation],
    enu_positions: dict[str, np.ndarray],
    *,
    timestamp_tolerance_seconds: float,
) -> tuple[list[Correspondence], list[str]]:
    """Pair poses with GPS using image name, source frame index, then time.

    Timestamp matching linearly interpolates local ENU positions only when both
    neighbouring GPS samples are within the configured timing tolerance.
    """
    by_image: dict[str, list[GPSObservation]] = defaultdict(list)
    by_frame: dict[int, list[GPSObservation]] = defaultdict(list)
    for observation in observations:
        if observation.image_name:
            by_image[_normalise_image_name(observation.image_name)].append(observation)
        if observation.frame_index is not None:
            by_frame[observation.frame_index].append(observation)

    matches: list[Correspondence] = []
    warnings: list[str] = []
    for pose in poses:
        observation: GPSObservation | None = None
        if _normalise_image_name(pose.image_name) in by_image:
            observation = _choose_direct_observation(
                by_image[_normalise_image_name(pose.image_name)], pose, "image name", warnings
            )
            if observation is not None:
                matches.append(
                    Correspondence(
                        pose=pose,
                        target_enu=enu_positions[observation.observation_id],
                        gps_observation_ids=(observation.observation_id,),
                        method="image_name",
                    )
                )
                continue
        frame_index = frame_index_from_image_name(pose.image_name)
        if frame_index is not None and frame_index in by_frame:
            observation = _choose_direct_observation(
                by_frame[frame_index], pose, "frame index", warnings
            )
            if observation is not None:
                matches.append(
                    Correspondence(
                        pose=pose,
                        target_enu=enu_positions[observation.observation_id],
                        gps_observation_ids=(observation.observation_id,),
                        method="frame_index",
                    )
                )
                continue
        interpolated = _interpolate_timestamp_position(
            pose, observations, enu_positions, timestamp_tolerance_seconds
        )
        if interpolated is not None:
            position, observation_ids = interpolated
            matches.append(
                Correspondence(
                    pose=pose,
                    target_enu=position,
                    gps_observation_ids=observation_ids,
                    method="timestamp_interpolated",
                )
            )

    unmatched_count = len(poses) - len(matches)
    if unmatched_count:
        warnings.append(
            f"{unmatched_count} reconstructed camera pose(s) had no usable GPS match."
        )
    if any(match.method == "timestamp_interpolated" for match in matches):
        warnings.append(
            "Some camera/GPS correspondences use linearly interpolated GPS positions; "
            "they are trajectory estimates, not independent GPS fixes."
        )
    return matches, warnings
