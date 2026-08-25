"""Command-line interface for Step 5 scene-object association."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.scene_objects.api import associate_objects_with_3d_scene


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the stable Step 5 command-line parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.scene_objects",
        description=(
            "Triangulate tracked Step 4 object anchors from calibrated Step 2 views "
            "and apply Step 3 georeferencing when supplied."
        ),
    )
    parser.add_argument("--objects", required=True, type=Path, help="Step 4 objects directory.")
    parser.add_argument(
        "--reconstruction",
        required=True,
        type=Path,
        help="Step 2 reconstruction directory containing camera_poses.json.",
    )
    parser.add_argument(
        "--georeferenced",
        type=Path,
        default=None,
        help="Optional Step 3 output directory containing transform.json.",
    )
    parser.add_argument("--output", required=True, type=Path, help="New Step 5 output directory.")
    parser.add_argument(
        "--minimum-ray-angle-degrees",
        type=float,
        default=1.0,
        help="Below this median ray angle, emit a low-confidence estimate (default: 1).",
    )
    parser.add_argument(
        "--max-normalized-ray-residual",
        type=float,
        default=0.25,
        help=(
            "Above this ray-RMSE/median-baseline ratio, emit low confidence "
            "(default: 0.25)."
        ),
    )
    parser.add_argument(
        "--max-condition-number",
        type=float,
        default=1e8,
        help="Numerical triangulation stability limit (default: 1e8).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and recreate a non-empty Step 5 output directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute association and print the output summary."""
    args = build_arg_parser().parse_args(argv)
    result = associate_objects_with_3d_scene(
        object_dir=args.objects,
        reconstruction_dir=args.reconstruction,
        georeferenced_dir=args.georeferenced,
        output_dir=args.output,
        minimum_ray_angle_degrees=args.minimum_ray_angle_degrees,
        max_normalized_ray_residual=args.max_normalized_ray_residual,
        max_condition_number=args.max_condition_number,
        overwrite=args.overwrite,
    )
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1
    print("Scene-object association completed.")
    print(f"Tracks:          {result.track_count}")
    print(f"Estimated:       {result.estimated_count}")
    print(f"Low confidence:  {result.low_confidence_count}")
    print(f"Unavailable:     {result.unavailable_count}")
    print(f"Objects:         {result.objects_3d_path}")
    print(f"Metadata:        {result.metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
