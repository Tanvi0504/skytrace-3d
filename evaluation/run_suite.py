"""Command-line runner for SkyTrace Step 8 robustness evaluation."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.evaluation import evaluate_measurements

from evaluation.failure import classify_failure
from evaluation.metrics import (
    completeness_metrics,
    evidence_score_validation,
    measurement_error_metrics,
    object_detection_metrics,
    object_localization_metrics,
)
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

DEFAULT_SCENARIO_MANIFESTS: dict[str, dict[str, Any]] = {
    "baseline": {
        "scenario": "baseline",
        "single_pass": True,
        "source_video": "../../test/example.mp4",
        "ground_truth": None,
        "notes": [
            "Baseline is the reference run before artificial degradation.",
            "Accuracy is NOT_TESTED unless external ground truth is supplied.",
        ],
    },
    "motion_blur": {
        "scenario": "motion_blur",
        "single_pass": True,
        "source_video": "../baseline/../../test/example.mp4",
        "degradations": [{"type": "motion_blur", "level": level} for level in (0, 1, 2, 3)],
        "notes": ["Controlled blur levels are relative stress cases, not universal thresholds."],
    },
    "compression": {
        "scenario": "compression",
        "single_pass": True,
        "source_video": "../baseline/../../test/example.mp4",
        "degradations": [
            {"type": "compression", "level": 0, "jpeg_quality": 95},
            {"type": "compression", "level": 1, "jpeg_quality": 85},
            {"type": "compression", "level": 2, "jpeg_quality": 55},
            {"type": "compression", "level": 3, "jpeg_quality": 30},
        ],
        "notes": ["Records codec, resolution, and compression parameters for reproducibility."],
    },
    "illumination": {
        "scenario": "illumination",
        "single_pass": True,
        "source_video": "../baseline/../../test/example.mp4",
        "degradations": [
            {"type": "dark", "level": 1},
            {"type": "dark", "level": 3},
            {"type": "bright", "level": 1},
            {"type": "contrast", "level": 2},
        ],
        "notes": ["No image enhancement is applied before scoring unless it is part of SkyTrace itself."],
    },
    "shadows": {
        "scenario": "shadows",
        "single_pass": True,
        "source_video": "../baseline/../../test/example.mp4",
        "degradations": [{"type": "shadow", "level": level} for level in (1, 2, 3)],
        "notes": ["Synthetic shadows mark a controlled occluding illumination stress, not a physical lighting model."],
    },
    "dynamic_objects": {
        "scenario": "dynamic_objects",
        "single_pass": True,
        "required_scene_content": ["people", "cars", "trucks", "animals", "moving objects"],
        "comparisons": ["raw_reconstruction", "dynamic_object_aware_reconstruction"],
        "notes": ["Precision/recall remain NOT_TESTED until object labels are supplied."],
    },
    "gps_noise": {
        "scenario": "gps_noise",
        "single_pass": True,
        "gps_noise_levels_metres": [0, 1, 5, 10, 20, 50],
        "notes": ["Controlled perturbations are not real GPS distributions; relative and absolute accuracy are separate."],
    },
    "sensor_noise": {
        "scenario": "sensor_noise",
        "single_pass": True,
        "imu_required": False,
        "notes": ["If IMU metadata is unavailable, the report must say NOT_TESTED instead of fabricating sensor data."],
    },
    "limited_view": {
        "scenario": "limited_view",
        "single_pass": True,
        "view_rule": "one_continuous_flight_path_only",
        "surface_classes": ["directly_observed", "weakly_observed", "unseen"],
        "notes": ["Unseen geometry must not receive the same confidence as directly observed surfaces."],
    },
    "occlusion": {
        "scenario": "occlusion",
        "single_pass": True,
        "occluders": ["trees", "vehicles", "structures", "partially hidden objects"],
        "notes": ["Observed surfaces must remain separate from inferred or uncertain regions."],
    },
    "no_gcp": {
        "scenario": "no_gcp",
        "single_pass": True,
        "cases": ["no_gcp", "minimal_control_if_available", "higher_quality_reference_if_available"],
        "notes": ["Zero-GCP reconstruction is quantified, not described as survey-grade."],
    },
    "metric_accuracy": {
        "scenario": "metric_accuracy",
        "single_pass": True,
        "requires": ["ground_truth_measurements.json", "processed_run/analysis/measurements.json"],
        "notes": ["Reports MAE, RMSE, median, maximum, absolute, and relative errors across matched measurements."],
    },
    "processing_time": {
        "scenario": "processing_time",
        "single_pass": True,
        "stages": [
            "frame_extraction",
            "reconstruction",
            "georeferencing",
            "object_detection",
            "object_3d_association",
            "analysis",
            "total",
        ],
        "notes": ["Real-time is supported only when measured processing time is not longer than video duration."],
    },
    "combined_stress": {
        "scenario": "combined_stress",
        "single_pass": True,
        "scenarios": [
            ["motion_blur", "compression"],
            ["motion_blur", "gps_noise"],
            ["occlusion", "dynamic_objects"],
            ["illumination", "compression"],
            ["motion_blur", "gps_noise", "dynamic_objects", "occlusion"],
        ],
        "notes": ["Combined stress exists to expose break points, not to manufacture success."],
    },
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
    dataset_structure = ensure_dataset_structure(dataset_dir)
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
    object_detection = evaluate_object_detection(dataset_dir, processed_run)
    object_localization = evaluate_object_localization(dataset_dir, processed_run)
    completeness = evaluate_completeness(dataset_dir)
    evidence_validation = evaluate_evidence(processed_run, metric_accuracy)
    return build_report(
        dataset_dir=dataset_dir,
        dataset_structure=dataset_structure,
        scenarios=scenarios,
        baseline=baseline,
        metric_accuracy=metric_accuracy,
        object_detection=object_detection,
        object_localization=object_localization,
        completeness=completeness,
        evidence_validation=evidence_validation,
    )


def ensure_dataset_structure(dataset_dir: Path) -> dict[str, Any]:
    """Create a lightweight, reproducible Step 8 dataset layout without downloading data."""
    created_dirs: list[str] = []
    created_manifests: list[str] = []
    for name, manifest in DEFAULT_SCENARIO_MANIFESTS.items():
        scenario_dir = dataset_dir / name
        if not scenario_dir.exists():
            scenario_dir.mkdir(parents=True)
            created_dirs.append(str(scenario_dir))
        manifest_path = scenario_dir / "manifest.json"
        if not manifest_path.exists():
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            created_manifests.append(str(manifest_path))
    return {
        "root": str(dataset_dir),
        "scenario_directories": sorted(DEFAULT_SCENARIO_MANIFESTS),
        "created_directories": created_dirs,
        "created_manifests": created_manifests,
        "downloads_performed": False,
    }


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
        "run_id": f"{name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "scenario": name,
        "label": SCENARIOS[name],
        "status": status,
        "single_pass": bool(manifest.get("single_pass", True)) if manifest else None,
        "reproducibility": _reproducibility_metadata(name, manifest, processed_run, metrics),
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
    sampled_frames = _nested(video_meta, ["source_video", "frame_count"]) or video_meta.get("sampled_frame_count") or _step_summary(steps, 1, "sampled_frames")
    selected_frames = video_meta.get("selected_frame_count") or _step_summary(steps, 1, "selected_frames")
    rejected_frames = _step_summary(steps, 1, "rejected_frames")
    registered_frames = reconstruction.get("registered_image_count") or _step_summary(steps, 2, "registered_images")
    detected_objects = _step_summary(steps, 4, "detected_objects")
    metrics = {
        "video_duration_seconds": video_duration,
        "input_frames": sampled_frames,
        "selected_frames": selected_frames,
        "frame_rejection_rate": (rejected_frames / sampled_frames if sampled_frames and rejected_frames is not None else None),
        "registered_frames": registered_frames,
        "registration_rate": (registered_frames / selected_frames if registered_frames is not None and selected_frames else None),
        "point_count": ply_count or analysis.get("point_count") or reconstruction.get("sparse_point_count"),
        "detected_objects": detected_objects,
        "objects_3d": len(objects),
        "object_3d_association_rate": (len(objects) / detected_objects if detected_objects else None),
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


def evaluate_object_detection(dataset_dir: Path, processed_run: Path) -> dict[str, Any]:
    ground_truth = dataset_dir / "object_labels.json"
    predictions = processed_run / "scene_objects" / "objects_3d.json"
    if not ground_truth.is_file() or not predictions.is_file():
        return {"status": "NOT_TESTED", "reason": "Object detection needs object_labels.json and scene_objects/objects_3d.json."}
    return object_detection_metrics(_load_json(predictions), _load_json(ground_truth))


def evaluate_object_localization(dataset_dir: Path, processed_run: Path) -> dict[str, Any]:
    ground_truth = dataset_dir / "object_positions_3d.json"
    predictions = processed_run / "scene_objects" / "objects_3d.json"
    if not ground_truth.is_file() or not predictions.is_file():
        return {"status": "NOT_TESTED", "reason": "3D object localization needs object_positions_3d.json and scene_objects/objects_3d.json."}
    return object_localization_metrics(_load_json(predictions), _load_json(ground_truth))


def evaluate_completeness(dataset_dir: Path) -> dict[str, Any]:
    ground_truth = dataset_dir / "surface_completeness.json"
    if not ground_truth.is_file():
        return {"status": "NOT_TESTED", "reason": "3D completeness needs surface_completeness.json with observed/reference surface areas."}
    return completeness_metrics(_load_json(ground_truth))


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
    metrics["real_time_assessment"] = (
        "Processing time was not recorded; no real-time claim is supported."
        if ratio is None
        else "Processing was no slower than video duration." if ratio <= 1.0
        else "Processing took longer than video duration; near-real-time is not demonstrated."
    )
    return metrics


def _reproducibility_metadata(name: str, manifest: dict[str, Any], processed_run: Path, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario": name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_video": manifest.get("source_video"),
        "video_duration_seconds": metrics.get("video_duration_seconds"),
        "resolution": manifest.get("resolution"),
        "frame_rate": manifest.get("frame_rate"),
        "degradation_parameters": manifest.get("degradations") or manifest.get("gps_noise_levels_metres") or manifest.get("scenarios"),
        "gps_perturbation": manifest.get("gps_noise_levels_metres"),
        "processing_configuration": {"processed_run": str(processed_run)},
        "software_version": {"python": platform.python_version(), "git_commit": _git_commit()},
        "output_metrics": metrics,
    }


def _git_commit() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=False, capture_output=True, text=True)
    except OSError:
        return None
    return result.stdout.strip() or None


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
