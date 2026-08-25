"""Command-line interface for Step 4 object intelligence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.objects.api import detect_and_track_objects


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the stable Step 4 CLI parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.objects",
        description=(
            "Detect objects in selected frames, associate them with ByteTrack when "
            "enabled, and write conservative dynamic-candidate masks."
        ),
    )
    parser.add_argument("--frames", required=True, type=Path, help="Selected Step 1 frames directory.")
    parser.add_argument("--output", required=True, type=Path, help="New Step 4 output directory.")
    parser.add_argument(
        "--model",
        default="yolo11n.pt",
        help="Ultralytics pretrained model name/path (default: yolo11n.pt).",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.25,
        help="Minimum detection confidence in [0, 1] (default: 0.25).",
    )
    parser.add_argument(
        "--iou-threshold",
        type=float,
        default=0.7,
        help="YOLO NMS IoU threshold in [0, 1] (default: 0.7).",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        default=None,
        help="Optional model class names to retain, e.g. person car truck.",
    )
    parser.add_argument(
        "--no-tracking",
        action="store_true",
        help="Disable the model's existing ByteTrack integration.",
    )
    parser.add_argument(
        "--tracker-config",
        default="bytetrack.yaml",
        help="Ultralytics tracker configuration when tracking is enabled.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Inference device accepted by Ultralytics, e.g. cpu, 0, or mps.",
    )
    parser.add_argument(
        "--mask-padding-pixels",
        type=int,
        default=0,
        help="Pixels to expand each dynamic-candidate box in masks (default: 0).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and recreate a non-empty Step 4 output directory.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute Step 4 and return a shell-friendly status code."""
    args = build_arg_parser().parse_args(argv)
    result = detect_and_track_objects(
        frames_dir=args.frames,
        output_dir=args.output,
        model_name=args.model,
        confidence_threshold=args.confidence_threshold,
        iou_threshold=args.iou_threshold,
        classes=args.classes,
        tracking=not args.no_tracking,
        tracker_config=args.tracker_config,
        device=args.device,
        mask_padding_pixels=args.mask_padding_pixels,
        overwrite=args.overwrite,
    )
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1
    print("Object detection completed.")
    print(f"Frames processed: {result.frames_processed}")
    print(f"Detections:       {result.detection_count}")
    print(f"Tracks:           {result.track_count}")
    print(f"Throughput:       {result.frames_per_second:.2f} frames/s")
    print(f"Detections:       {result.detections_path}")
    print(f"Tracks:           {result.tracks_path}")
    print(f"Masks:            {result.masks_dir}")
    print(f"Metadata:         {result.metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
