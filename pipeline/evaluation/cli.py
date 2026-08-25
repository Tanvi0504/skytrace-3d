"""CLI for evaluating Step 6 measurements against known distances."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline.evaluation.api import evaluate_measurements


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.evaluation",
        description="Compare Step 6 metric measurements against known ground-truth distances.",
    )
    parser.add_argument("--predictions", required=True, type=Path, help="Step 6 measurements.json.")
    parser.add_argument("--ground-truth", required=True, type=Path, help="Known-distance JSON.")
    parser.add_argument("--output", required=True, type=Path, help="New evaluation output directory.")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = evaluate_measurements(
        args.predictions, args.ground_truth, args.output, overwrite=args.overwrite
    )
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1
    print("Measurement evaluation completed.")
    print(f"Matched measurements: {result.measurement_count}")
    print(f"MAE (m):             {result.mean_absolute_error_metres:.6g}")
    print(f"RMSE (m):            {result.rmse_metres:.6g}")
    print(f"Report:              {result.report_path}")
    return 0
