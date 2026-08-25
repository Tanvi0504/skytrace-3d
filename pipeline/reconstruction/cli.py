"""Command-line interface for SkyTrace Step 2 reconstruction."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pipeline.reconstruction.api import run_reconstruction


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.reconstruction",
        description=(
            "Run baseline COLMAP 3D reconstruction on the selected frames "
            "already produced by SkyTrace Step 1."
        ),
    )
    parser.add_argument(
        "--frames",
        required=True,
        type=Path,
        help="Selected-frames directory from Step 1 (e.g. outputs/example/frames).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New reconstruction workspace (e.g. outputs/example/reconstruction).",
    )
    parser.add_argument(
        "--backend",
        choices=["colmap"],
        default="colmap",
        help="Reconstruction backend (default: colmap).",
    )
    parser.add_argument(
        "--no-dense",
        action="store_true",
        help="Skip the optional COLMAP dense MVS pass and produce sparse output only.",
    )
    parser.add_argument(
        "--matcher",
        choices=["sequential", "exhaustive"],
        default="sequential",
        help="Feature matcher; sequential suits chronological video frames (default).",
    )
    parser.add_argument(
        "--colmap-executable",
        default="colmap",
        help="COLMAP executable name or absolute path (default: colmap on PATH).",
    )
    parser.add_argument(
        "--use-gpu",
        action="store_true",
        help="Enable GPU SIFT feature extraction/matching when COLMAP supports it.",
    )
    parser.add_argument(
        "--max-image-size",
        type=int,
        default=2000,
        help="Maximum image size for dense undistortion (default: 2000).",
    )
    parser.add_argument(
        "--per-image-camera",
        action="store_true",
        help="Do not assume all selected frames share one camera model.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and recreate a non-empty reconstruction output directory.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable INFO logging.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    result = run_reconstruction(
        frames_dir=args.frames,
        output_dir=args.output,
        backend=args.backend,
        dense=not args.no_dense,
        colmap_executable=args.colmap_executable,
        matcher=args.matcher,
        use_gpu=args.use_gpu,
        max_image_size=args.max_image_size,
        single_camera=not args.per_image_camera,
        overwrite=args.overwrite,
    )
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    print("Sparse reconstruction completed.")
    print(f"Registered images: {result.registered_image_count}/{result.input_image_count}")
    print(f"Sparse points:     {result.sparse_point_count}")
    print(f"Sparse PLY:        {result.sparse_point_cloud_path}")
    print(f"Camera poses:      {result.camera_poses_path}")
    print(f"Metadata:          {result.metadata_path}")
    if result.dense_status == "completed":
        print(f"Dense PLY:         {result.dense_point_cloud_path}")
    elif result.dense_status == "failed":
        print(
            "Warning: dense reconstruction failed; sparse output was preserved. "
            f"Details: {result.dense_error}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

