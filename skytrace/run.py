"""CLI: ``python -m skytrace.run`` executes the complete SkyTrace pipeline."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

from skytrace.configuration import load_config
from skytrace.orchestrator import PipelineOrchestrator


RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _run_id(value: str | None) -> str:
    run_id = value or uuid.uuid4().hex[:12]
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Run ID may contain only letters, numbers, underscores, and hyphens.")
    return run_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the complete SkyTrace Steps 1-6 pipeline with Step 10 observability.")
    parser.add_argument("--video", type=Path, help="Drone video. Required for a new run; optional with --resume.")
    parser.add_argument("--metadata", type=Path, default=None, help="Optional GPS/flight metadata (JSON or CSV accepted by Step 3).")
    parser.add_argument("--output", type=Path, default=Path("results"), help="Root directory that will contain <run-id> (default: results).")
    parser.add_argument("--config", type=Path, default=Path("config/default.yaml"), help="YAML configuration profile.")
    parser.add_argument("--run-id", default=None, help="Stable run ID. Required with --resume.")
    parser.add_argument("--resume", action="store_true", help="Validate checkpoints and resume from the first incomplete/invalid stage.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.resume and not args.run_id:
        print("--resume requires --run-id so the intended result package is unambiguous.", file=sys.stderr)
        return 2
    try:
        run_id = _run_id(args.run_id)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    directory = args.output / run_id
    if args.video is None:
        report = directory / "input_report.json"
        if not args.resume or not report.is_file():
            print("--video is required for a new run. A resume without --video requires an existing input_report.json.", file=sys.stderr)
            return 2
        document = json.loads(report.read_text(encoding="utf-8"))
        args.video = Path(document["video"]["path"])
        if args.metadata is None and document.get("metadata", {}).get("path"):
            args.metadata = Path(document["metadata"]["path"])
    if directory.exists() and not args.resume and any(directory.iterdir()):
        print(f"Result directory already exists: {directory}. Choose a new --run-id or use --resume.", file=sys.stderr)
        return 2
    try:
        config = load_config(args.config)
        outcome = PipelineOrchestrator(
            run_id=run_id,
            directory=directory,
            video_path=args.video,
            metadata_path=args.metadata,
            config=config,
            resume=args.resume,
        ).run()
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "run_id": outcome.run_id,
        "status": outcome.status,
        "first_failed_stage": outcome.first_failed_stage,
        "manifest": str(outcome.manifest_path) if outcome.manifest_path else None,
        "report": str(outcome.report_html_path) if outcome.report_html_path else None,
        "error": outcome.error,
    }, indent=2))
    return 0 if outcome.status != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
