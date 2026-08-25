"""Command-line runner for SkyTrace Step 8 robustness evaluation."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

from pipeline.evaluation import evaluate_measurements

from evaluation.failure import classify_failure
from evaluation.metrics import evidence_score_validation, measurement_error_metrics
from evaluation.perturbations import create_degraded_video
from evaluation.reports import PS_CHALLENGES, build_report, write_reports

SCENARIOS = {
    "baseline": "BASELINE",
    "motion_blur": "MOTION BLUR",
    "compression": "COMPRESSION",
    "illumination": "VARIABLE ILLUMINATION",
    "shadows": "SHADOWS",
    "dynamic_objects": "DYNAMIC OBJECTS",
    "gps_noise": "GPS NOISE",
    "sensor_noise": "SENSOR NOISE",
    "limited_view": "LIMITED VIEW",
    "occlusion": "OCCLUSION",
    "no_gcp": "NO-GCP",
    "metric_accuracy": "METRIC ACCURACY",
    "processing_time": "PROCESSING TIME",
    "combined_stress": "COMBINED STRESS",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SkyTrace Step 8 robustness evaluation.")
    parser.add_argument("--dataset", default="data/evaluation", help="Evaluation dataset root.")
    parser.add_argument("--output", default="evaluation/results", help="Report output directory.")
    parser.add_argument("--scenario", default="all", choices=["all", *SCENARIOS.keys()])
    parser.add_argument("--processed-run", default="outputs/processed-demo", help="Existing processed run for baseline collection.")
    parser.add_argument("--generate-perturbations", action="store_true", help="Create controlled degraded video copies from scenario manifests.")
    args = parser.parse_args(argv)

    dataset = Path(args.dataset)
    output = Path(args.output)
    selected = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    report = run_suite(dataset, output, selected, Path(args.processed_run), args.generate_perturbations)
    paths = write_reports(report, output)
    print(json.dumps({"report_paths": paths, "scenario_count": len(report["scenarios"])}, indent=2))
    return 0


def run_suite(
    dataset_dir: Path,
    output_dir: Path,
    selected_scenarios: list[str],
    processed_run: Path,
    generate_perturbations: bool = False,
) -> dict[str, Any]:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline = collect_processed_run(processed_run) if processed_run.is_dir() else None
    scenarios = []
    for name in selected_scenarios:
        scenarios.append(
            evaluate_scenario(
                name,
                dataset_dir / name,
                output_dir / name,
                baseline,
                processed_run,
                generate_perturbations,
            )
        )

    metric_accuracy = evaluate_metric_accuracy(dataset_dir, output_dir, processed_run)
    evidence_validation = evaluate_evidence(processed_run, metric_accuracy)
    return build_report(
        dataset_dir=dataset_dir,
        scenarios=scenarios,
        baseline=baseline,
        metric_accuracy=metric_accuracy,
        evidence_validation=evidence_validation,
    )


def evaluate_scenario(
    name: str,
    scenario_dir: Path,
    output_dir: Path,
    baseline: dict[str, Any] | None,
    processed_run: Path,
    generate_perturbations: bool,
) -> dict[str, Any]:
    started = time.monotonic()
    manifest = _load_json(scenario_dir / "manifest.json")
    notes: list[str] = []
    generated: list[dict[str, Any]] = []
    status = "NOT_TESTED"
    metrics: dict[str, Any] = {}

    if name == "baseline" and baseline:
        status = "TESTED"
        metrics = baseline["metrics"]
        notes.append("Baseline collected from existing processed run; no rerun was required.")
    elif name == "processing_time" and baseline:
        status = "TESTED"
        metrics = _timing_metrics(baseline)
    elif manifest:
        status = "REGISTERED"
        notes.append("Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.")
        if generate_perturbations:
            generated = _generate_from_manifest(manifest, scenario_dir, output_dir)
            notes.append("Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy.")
    else:
        notes.append(f"No dataset manifest found for {name}; result is NOT_TESTED.")

    failure = classify_failure(baseline.get("run_status") if baseline else None, metrics) if status == "TESTED" else None
    return {
        "scenario": name,
        "label": SCENARIOS[name],
        "status": status,
        "single_pass": bool(manifest.get("single_pass", True)) if manifest else None,
        "manifest": manifest or None,
        "metrics": metrics,
        "failure": failure,
        "generated_artifacts": generated,
        "summary": "Metrics collected." if status == "TESTED" else "No measured experiment results yet.",
        "notes": notes,
        "evaluation_time_seconds": round(time.monotonic() - started, 4),
    }


def collect_processed_run(run_dir: Path) -> dict[str, Any]:
    run_status = _load_json(run_dir / "run_state.json")
    video_meta = _load_json(run_dir / "metadata.json")
    reconstruction = _load_json(run_dir / "reconstruction" / "reconstruction_metadata.json")
    georef = _load_json(run_dir / "georeferenced" / "georef_metadata.json")
    objects_doc = _load_json(run_dir / "scene_objects" / "objects_3d.json")
    analysis = _load_json(run_dir / "analysis" / "quality_metadata.json")
    quality = _load_json(run_dir / "analysis" / "evidence_map" / "quality_grid.json")
    ply_count = _ply_vertex_count(run_dir / "georeferenced" / "point_cloud_georef.ply")
    objects = objects_doc.get("objects", []) if isinstance(objects_doc.get("objects"), list) else []
    steps = run_status.get("steps", [])
    processing_seconds = sum(float(step.get("summary", {}).get("processing_time_seconds", 0.0) or 0.0) for step in steps)
    video_duration = _nested(video_meta, ["source_video", "duration_seconds"]) or _nested(video_meta, ["video", "duration_seconds"])
    metrics = {
        "video_duration_seconds": video_duration,
        "input_frames": _nested(video_meta, ["source_video", "frame_count"]),
        "selected_frames": video_meta.get("selected_frame_count"),
        "registered_frames": reconstruction.get("registered_image_count"),
        "point_count": ply_count or analysis.get("point_count") or reconstruction.get("sparse_point_count"),
        "detected_objects": _step_summary(steps, 4, "detected_objects"),
        "objects_3d": len(objects),
        "quality_regions": len(quality.get("regions", [])) if isinstance(quality.get("regions"), list) else analysis.get("quality_region_count"),
        "dynamic_marker_count": analysis.get("dynamic_marker_count"),
        "trajectory_rmse_metres": georef.get("trajectory_rmse_metres"),
        "total_processing_time_seconds": processing_seconds or None,
        "processing_to_video_duration_ratio": (processing_seconds / video_duration if processing_seconds and video_duration else None),
    }
    return {
        "status": "TESTED",
        "run_id": run_status.get("run_id", run_dir.name),
        "run_dir": str(run_dir),
        "run_status": run_status,
        "metrics": metrics,
        "warnings": _warnings(run_status, video_meta, reconstruction, georef, analysis),
    }


def evaluate_metric_accuracy(dataset_dir: Path, output_dir: Path, processed_run: Path) -> dict[str, Any]:
    ground_truth = dataset_dir / "ground_truth_measurements.json"
    predictions = processed_run / "analysis" / "measurements.json"
    if not ground_truth.is_file() or not predictions.is_file():
        return {
            "status": "NOT_TESTED",
            "reason": "Metric accuracy needs both ground_truth_measurements.json and analysis/measurements.json.",
        }
    result = evaluate_measurements(predictions, ground_truth, output_dir / "metric_accuracy", overwrite=True)
    payload = result.to_dict()
    if not result.success:
        payload["status"] = "FAIL"
        return payload
    report = _load_json(Path(result.report_path or ""))
    payload["status"] = "TESTED"
    payload["metrics"] = measurement_error_metrics(report.get("comparisons", []))
    return payload


def evaluate_evidence(processed_run: Path, metric_accuracy: dict[str, Any]) -> dict[str, Any]:
    comparisons = _nested(metric_accuracy, ["metrics", "comparisons"]) or []
    if comparisons:
        return evidence_score_validation(comparisons)
    measurements = _load_json(processed_run / "analysis" / "measurements.json")
    if not measurements:
        return {"status": "NOT_TESTED", "reason": "Evidence validation requires measurement predictions and ground truth."}
    return evidence_score_validation(measurements.get("measurements", []))


def _generate_from_manifest(manifest: dict[str, Any], scenario_dir: Path, output_dir: Path) -> list[dict[str, Any]]:
    source = Path(manifest.get("source_video", ""))
    if not source.is_absolute():
        source = scenario_dir / source
    if not source.is_file():
        return [{"error": f"source_video not found: {source}"}]
    artifacts = []
    for item in manifest.get("degradations", []):
        degradation = str(item.get("type", "copy"))
        level = int(item.get("level", 1))
        target = output_dir / f"{degradation}_level_{level}.mp4"
        artifacts.append(create_degraded_video(source, target, degradation=degradation, level=level, jpeg_quality=int(item.get("jpeg_quality", 70))))
    return artifacts


def _timing_metrics(baseline: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(baseline.get("metrics", {}))
    ratio = metrics.get("processing_to_video_duration_ratio")
    metrics["real_time_claim_supported"] = bool(ratio is not None and ratio <= 1.0)
    return metrics


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _ply_vertex_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    with path.open("rb") as source:
        for raw in source:
            line = raw.decode("ascii", errors="ignore").strip()
            if line.startswith("element vertex"):
                return int(line.split()[-1])
            if line == "end_header":
                return None
    return None


def _step_summary(steps: list[dict[str, Any]], step_number: int, key: str) -> Any:
    step = next((item for item in steps if item.get("step") == step_number), {})
    return step.get("summary", {}).get(key)


def _nested(document: dict[str, Any], keys: list[str]) -> Any:
    current: Any = document
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _warnings(*documents: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for doc in documents:
        raw = doc.get("warnings", [])
        if isinstance(raw, list):
            output.extend(str(item) for item in raw)
        for step in doc.get("steps", []) if isinstance(doc.get("steps"), list) else []:
            output.extend(str(item) for item in step.get("warnings", []))
    return output


if __name__ == "__main__":
    raise SystemExit(main())
