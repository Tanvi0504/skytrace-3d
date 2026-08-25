"""Command-line entry point for Step 3 georeferencing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.georeferencing.api import georeference_reconstruction


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.georeferencing",
        description=(
            "Align a completed SkyTrace Step 2 reconstruction to GPS-derived "
            "local ENU coordinates in metres."
        ),
    )
    parser.add_argument(
        "--reconstruction",
        required=True,
        type=Path,
        help="Step 2 reconstruction directory containing camera_poses.json and PLY.",
    )
    parser.add_argument(
        "--gps",
        required=True,
        type=Path,
        help="GPS/flight metadata in documented CSV or JSON format.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New georeferencing output directory (e.g. outputs/example/georeferenced).",
    )
    parser.add_argument(
        "--point-cloud",
        type=Path,
        default=None,
        help="Optional PLY override; defaults to dense/fused.ply then sparse/sparse.ply.",
    )
    parser.add_argument(
        "--timestamp-tolerance-seconds",
        type=float,
        default=1.0,
        help="Maximum distance to each GPS sample for timestamp interpolation (default: 1.0).",
    )
    parser.add_argument(
        "--ransac-threshold-metres",
        type=float,
        default=10.0,
        help="Trajectory-fit inlier tolerance in ENU metres, not an accuracy claim (default: 10).",
    )
    parser.add_argument(
        "--ransac-iterations",
        type=int,
        default=300,
        help="Maximum deterministic RANSAC samples (default: 300).",
    )
    parser.add_argument(
        "--source-scale-mode",
        choices=["auto", "arbitrary", "metric"],
        default="auto",
        help="Whether Step 2 source scale is unknown/arbitrary or already metric (default: auto).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and recreate a non-empty georeferencing output directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = georeference_reconstruction(
        reconstruction_dir=args.reconstruction,
        gps_metadata_path=args.gps,
        output_dir=args.output,
        point_cloud_path=args.point_cloud,
        timestamp_tolerance_seconds=args.timestamp_tolerance_seconds,
        ransac_threshold_metres=args.ransac_threshold_metres,
        ransac_iterations=args.ransac_iterations,
        source_scale_mode=args.source_scale_mode,
        overwrite=args.overwrite,
    )
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1
    print("Georeferencing completed.")
    print(f"Matched poses:     {result.matched_pose_count}")
    print(f"RANSAC inliers:    {result.inlier_count}")
    print(f"Estimated scale:   {result.estimated_scale}")
    print(f"Point cloud:       {result.point_cloud_path}")
    print(f"Camera trajectory: {result.camera_trajectory_path}")
    print(f"Transform:         {result.transform_path}")
    print(f"Validation:        {result.validation_path}")
    print(f"Metadata:          {result.metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
