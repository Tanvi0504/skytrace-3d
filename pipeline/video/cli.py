"""Command-line interface for video ingestion.

Usage:
    python -m pipeline.video --video data/test/example.mp4 \\
        --output outputs/example --target-fps 5 --blur-threshold 100
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pipeline.video.config import VideoProcessingConfig
from pipeline.video.errors import VideoIngestionError
from pipeline.video.extractor import process_video


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.video",
        description=(
            "Extract, sample, and blur-filter frames from a single-pass "
            "drone video for later 3D reconstruction."
        ),
    )
    parser.add_argument(
        "--video", required=True, type=Path, help="Path to the input video file."
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Run output directory (e.g. outputs/example).",
    )
    parser.add_argument(
        "--target-fps",
        type=float,
        default=5.0,
        help="Target sampling rate in frames per second (default: 5.0).",
    )
    parser.add_argument(
        "--blur-threshold",
        type=float,
        default=100.0,
        help=(
            "Minimum Laplacian-variance sharpness score to accept a "
            "sampled frame (default: 100.0). This is a heuristic and may "
            "need tuning per camera/lens/altitude."
        ),
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional run identifier. Defaults to the output directory name.",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=95,
        help="JPEG quality (0-100) for saved frames (default: 95).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable per-frame DEBUG logging (verbose).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        config = VideoProcessingConfig(
            video_path=args.video,
            output_dir=args.output,
            target_fps=args.target_fps,
            blur_threshold=args.blur_threshold,
            run_id=args.run_id,
            jpeg_quality=args.jpeg_quality,
            log_per_frame=args.verbose,
        )
        result = process_video(config)
    except VideoIngestionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid configuration: {exc}", file=sys.stderr)
        return 1

    print(f"Done. {result.selected_count} frame(s) selected, "
          f"{result.rejected_count} rejected.")
    print(f"Frames directory: {result.frames_dir}")
    print(f"Metadata:         {result.metadata_path}")
    print(f"Manifest:         {result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
