"""Command-line interface for Step 6 metric measurement and evidence analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from pipeline.analysis.api import analyze_georeferenced_scene
from pipeline.analysis.errors import AnalysisError
from pipeline.analysis.inputs import load_measurement_requests
from pipeline.analysis.measurements import normalize_unit
from pipeline.analysis.models import EvidenceConfig, MeasurementRequest


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the stable Step 6 analysis command."""
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.analysis",
        description=(
            "Measure a Step 3 georeferenced scene and write transparent Step 6 "
            "reconstruction-support evidence."
        ),
    )
    parser.add_argument("--scene", required=True, type=Path, help="Step 3 georeferenced directory.")
    parser.add_argument(
        "--objects",
        type=Path,
        default=None,
        help="Optional Step 5 scene_objects directory for dynamic-marker evidence.",
    )
    parser.add_argument("--output", required=True, type=Path, help="New Step 6 analysis directory.")
    requests = parser.add_argument_group("measurement requests")
    requests.add_argument(
        "--measurements",
        type=Path,
        default=None,
        help="JSON with {'measurements': [{'measurement_id', 'point_a', 'point_b', 'unit'}]}.",
    )
    requests.add_argument("--point-a", type=float, nargs=3, metavar=("X", "Y", "Z"))
    requests.add_argument("--point-b", type=float, nargs=3, metavar=("X", "Y", "Z"))
    requests.add_argument("--measurement-id", default="measurement_1")
    requests.add_argument("--unit", default="m", help="Display unit: m, cm, or km (default: m).")
    evidence = parser.add_argument_group("transparent evidence configuration")
    evidence.add_argument("--density-radius-metres", type=float, default=3.0)
    evidence.add_argument("--density-target-points", type=int, default=20)
    evidence.add_argument("--camera-support-radius-metres", type=float, default=80.0)
    evidence.add_argument("--camera-target-count", type=int, default=4)
    evidence.add_argument("--view-diversity-target-degrees", type=float, default=30.0)
    evidence.add_argument("--density-weight", type=float, default=0.50)
    evidence.add_argument("--nearby-camera-weight", type=float, default=0.25)
    evidence.add_argument("--view-diversity-weight", type=float, default=0.25)
    evidence.add_argument("--dynamic-contamination-radius-metres", type=float, default=3.0)
    evidence.add_argument("--dynamic-contamination-penalty", type=float, default=0.25)
    evidence.add_argument("--high-threshold", type=float, default=0.75)
    evidence.add_argument("--medium-threshold", type=float, default=0.50)
    evidence.add_argument("--low-threshold", type=float, default=0.25)
    evidence.add_argument("--quality-grid-cell-size-metres", type=float, default=5.0)
    evidence.add_argument("--max-quality-regions", type=int, default=10_000)
    evidence.add_argument("--segment-samples", type=int, default=5)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and recreate a non-empty Step 6 output directory.",
    )
    return parser


def _config_from_args(args: argparse.Namespace) -> EvidenceConfig:
    return EvidenceConfig(
        density_radius_metres=args.density_radius_metres,
        density_target_points=args.density_target_points,
        camera_support_radius_metres=args.camera_support_radius_metres,
        camera_target_count=args.camera_target_count,
        view_diversity_target_degrees=args.view_diversity_target_degrees,
        density_weight=args.density_weight,
        nearby_camera_weight=args.nearby_camera_weight,
        view_diversity_weight=args.view_diversity_weight,
        dynamic_contamination_radius_metres=args.dynamic_contamination_radius_metres,
        dynamic_contamination_penalty=args.dynamic_contamination_penalty,
        high_threshold=args.high_threshold,
        medium_threshold=args.medium_threshold,
        low_threshold=args.low_threshold,
        quality_grid_cell_size_metres=args.quality_grid_cell_size_metres,
        max_quality_regions=args.max_quality_regions,
        segment_samples=args.segment_samples,
    )


def main(argv: list[str] | None = None) -> int:
    """Run analysis and print a concise machine-output handoff summary."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if (args.point_a is None) != (args.point_b is None):
        parser.error("--point-a and --point-b must be supplied together")
    if args.measurements is not None and args.point_a is not None:
        parser.error("Choose --measurements or one --point-a/--point-b request, not both")
    try:
        requests = load_measurement_requests(args.measurements) if args.measurements else []
        if args.point_a is not None:
            requests.append(
                MeasurementRequest(
                    measurement_id=str(args.measurement_id),
                    point_a=np.asarray(args.point_a, dtype=float),
                    point_b=np.asarray(args.point_b, dtype=float),
                    unit=normalize_unit(args.unit),
                )
            )
        evidence_config = _config_from_args(args)
    except (AnalysisError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    result = analyze_georeferenced_scene(
        scene_dir=args.scene,
        scene_objects_dir=args.objects,
        output_dir=args.output,
        measurements=requests,
        evidence_config=evidence_config,
        overwrite=args.overwrite,
    )
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1
    print("Step 6 analysis completed.")
    print(f"Points:             {result.point_count}")
    print(f"Quality regions:    {result.quality_region_count}")
    print(f"Measurements:       {result.measurement_count}")
    print(f"Insufficient:       {result.insufficient_measurement_count}")
    print(f"Measurements output:{result.measurements_path}")
    print(f"Evidence map:       {result.evidence_map_path}")
    print(f"Metadata:           {result.metadata_path}")
    return 0
