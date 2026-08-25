"""Report assembly for PS 26158 robustness evaluation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.failure import FAILURE_TAXONOMY
from evaluation.metrics import compare_against_baseline


PS_CHALLENGES: dict[str, dict[str, str]] = {
    "limited_view": {"requirement": "Limited viewing angles", "component": "Steps 1-3 and Step 6 evidence", "test": "limited_view"},
    "motion_blur": {"requirement": "Motion blur", "component": "Step 1 frame filtering, Step 2 reconstruction, Step 4 detection", "test": "motion_blur"},
    "compression": {"requirement": "Video compression", "component": "Steps 1, 2, and 4", "test": "compression"},
    "illumination": {"requirement": "Variable illumination", "component": "Steps 1, 2, 4, and 6", "test": "illumination"},
    "shadows": {"requirement": "Shadows", "component": "Steps 1, 2, 4, and 6", "test": "shadows"},
    "dynamic_objects": {"requirement": "Dynamic objects", "component": "Steps 4-6", "test": "dynamic_objects"},
    "gps_noise": {"requirement": "GPS inaccuracies", "component": "Step 3 georeferencing and Step 6 measurement separation", "test": "gps_noise"},
    "sensor_noise": {"requirement": "Sensor noise", "component": "Step 2 pose stability and Step 3 metadata use", "test": "sensor_noise"},
    "processing_time": {"requirement": "Real-time / near-real-time processing", "component": "Steps 1-7 timing metadata", "test": "processing_time"},
    "occlusion": {"requirement": "Occluded surfaces", "component": "Step 6 evidence and completeness analysis", "test": "occlusion"},
    "no_gcp": {"requirement": "Lack of Ground Control Points", "component": "Step 3 georeferencing and Step 6 metric analysis", "test": "no_gcp"},
    "metric_accuracy": {"requirement": "Metric accuracy", "component": "Step 6 and pipeline.evaluation", "test": "metric_accuracy"},
}


def build_report(
    *,
    dataset_dir: Path,
    dataset_structure: dict[str, Any] | None = None,
    scenarios: list[dict[str, Any]],
    baseline: dict[str, Any] | None,
    metric_accuracy: dict[str, Any],
    object_detection: dict[str, Any] | None = None,
    object_localization: dict[str, Any] | None = None,
    completeness: dict[str, Any] | None = None,
    evidence_validation: dict[str, Any],
) -> dict[str, Any]:
    """Create the machine-readable robustness report payload."""
    scenario_by_name = {item["scenario"]: item for item in scenarios}
    scorecard = []
    for key, spec in PS_CHALLENGES.items():
        result = scenario_by_name.get(spec["test"])
        status = _score_status(key, result, metric_accuracy, evidence_validation)
        scorecard.append(
            {
                "ps_requirement": spec["requirement"],
                "skytrace_component": spec["component"],
                "test": spec["test"],
                "result": _score_result(key, result, metric_accuracy, evidence_validation),
                "status": status,
            }
        )

    comparison_table = []
    baseline_metrics = (baseline or {}).get("metrics", {})
    for item in scenarios:
        comparison = compare_against_baseline(baseline_metrics, item.get("metrics", {})) if baseline_metrics else {}
        comparison_table.append(
            {
                "challenge": item["label"],
                "baseline": baseline_metrics or "not_available",
                "degraded": item.get("metrics", {}),
                "performance_change": comparison,
                "failure": item.get("failure"),
                "notes": item.get("notes", []),
            }
        )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_dir": str(dataset_dir),
        "dataset_structure": dataset_structure or {"root": str(dataset_dir), "downloads_performed": False},
        "scientific_rules": [
            "No fabricated ground truth or accuracy.",
            "Relative geometry accuracy is separate from absolute georeferencing accuracy.",
            "Point density is not surface completeness or metric accuracy.",
            "Failed and untested cases remain visible.",
        ],
        "baseline": baseline or {"status": "NOT_TESTED", "reason": "No baseline processed run was available."},
        "scenarios": scenarios,
        "metric_accuracy": metric_accuracy,
        "object_detection_performance": object_detection or {"status": "NOT_TESTED"},
        "object_3d_localization": object_localization or {"status": "NOT_TESTED"},
        "three_d_completeness": completeness or {"status": "NOT_TESTED"},
        "evidence_score_validation": evidence_validation,
        "comparison_table": comparison_table,
        "ps_requirement_scorecard": scorecard,
        "failure_taxonomy": FAILURE_TAXONOMY,
        "visual_outputs": _visual_outputs(scenarios),
        "online_offline_analysis": {
            "online_candidates": ["frame extraction", "frame quality scoring", "object detection on decoded frames"],
            "offline_required": ["global reconstruction", "final georeferencing", "final metric/evidence analysis"],
            "note": "This is an architectural assessment only; no streaming rewrite was performed in Step 8.",
        },
    }


def write_reports(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "robustness_report.json"
    md_path = output / "robustness_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _score_status(
    key: str,
    scenario: dict[str, Any] | None,
    metric_accuracy: dict[str, Any],
    evidence_validation: dict[str, Any],
) -> str:
    if key == "metric_accuracy":
        return "PARTIAL" if metric_accuracy.get("status") == "TESTED" else "NOT_TESTED"
    if key == "processing_time":
        return "PARTIAL" if scenario and scenario.get("status") != "NOT_TESTED" else "NOT_TESTED"
    if key == "limited_view" and evidence_validation.get("status") == "TESTED":
        return "PARTIAL"
    if not scenario or scenario.get("status") != "TESTED":
        return "NOT_TESTED"
    if scenario.get("failure"):
        return "FAIL"
    return "PARTIAL"


def _score_result(
    key: str,
    scenario: dict[str, Any] | None,
    metric_accuracy: dict[str, Any],
    evidence_validation: dict[str, Any],
) -> str:
    if key == "metric_accuracy":
        return json.dumps(metric_accuracy.get("metrics", metric_accuracy), sort_keys=True)
    if key == "limited_view" and evidence_validation.get("status") == "TESTED":
        return evidence_validation.get("conclusion", "Evidence grouped by actual error.")
    if not scenario:
        return "No scenario data available."
    if scenario.get("failure"):
        return scenario["failure"]["description"]
    return scenario.get("summary", "Scenario collected without ground-truth pass/fail threshold.")


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SkyTrace Step 8 Robustness Report",
        "",
        f"Generated: {report['generated_at']}",
        f"Dataset: `{report['dataset_dir']}`",
        "",
        "## Dataset Structure",
        "",
        "```json",
        json.dumps(report["dataset_structure"], indent=2),
        "```",
        "",
        "## Baseline",
        "",
        "```json",
        json.dumps(report["baseline"], indent=2),
        "```",
        "",
        "## PS Requirement Scorecard",
        "",
        "| PS Requirement | SkyTrace Component | Test | Result | Status |",
        "|---|---|---|---|---|",
    ]
    for row in report["ps_requirement_scorecard"]:
        lines.append(
            f"| {row['ps_requirement']} | {row['skytrace_component']} | {row['test']} | "
            f"{_cell(row['result'])} | {row['status']} |"
        )
    lines.extend(["", "## Challenge Comparison", "", "| Challenge | Baseline | Degraded | Performance Change | Failure? | Notes |", "|---|---|---|---|---|---|"])
    for row in report["comparison_table"]:
        lines.append(
            f"| {row['challenge']} | {_cell(row['baseline'])} | {_cell(row['degraded'])} | "
            f"{_cell(row['performance_change'])} | {_cell(row['failure'])} | {_cell(row['notes'])} |"
        )
    lines.extend(
        [
            "",
            "## Scenario Results",
            "",
        ]
    )
    for scenario in report["scenarios"]:
        lines.extend(
            [
                f"### {scenario['label']}",
                "",
                "```json",
                json.dumps(scenario, indent=2),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Object Detection Performance",
            "",
            "```json",
            json.dumps(report["object_detection_performance"], indent=2),
            "```",
            "",
            "## 3D Object Localization",
            "",
            "```json",
            json.dumps(report["object_3d_localization"], indent=2),
            "```",
            "",
            "## 3D Completeness",
            "",
            "```json",
            json.dumps(report["three_d_completeness"], indent=2),
            "```",
            "",
            "## Metric Accuracy",
            "",
            "```json",
            json.dumps(report["metric_accuracy"], indent=2),
            "```",
            "",
            "## Evidence Score Validation",
            "",
            "```json",
            json.dumps(report["evidence_score_validation"], indent=2),
            "```",
            "",
            "## Failure Analysis",
            "",
            "```json",
            json.dumps(report["failure_taxonomy"], indent=2),
            "```",
            "",
            "## Visual Outputs",
            "",
            "```json",
            json.dumps(report["visual_outputs"], indent=2),
            "```",
            "",
            "## Online vs Offline",
            "",
            "```json",
            json.dumps(report["online_offline_analysis"], indent=2),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _cell(value: Any) -> str:
    if value is None:
        return "None"
    text = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _visual_outputs(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for scenario in scenarios:
        artifacts = scenario.get("generated_artifacts") or []
        for artifact in artifacts:
            if isinstance(artifact, dict) and artifact.get("output"):
                outputs.append(
                    {
                        "scenario": scenario["scenario"],
                        "type": "degraded_video",
                        "path": artifact["output"],
                        "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim.",
                    }
                )
    required = [
        "original_vs_degraded_frame",
        "original_vs_degraded_reconstruction",
        "object_detection_comparison",
        "evidence_map",
        "ground_truth_vs_estimated_measurement",
        "gps_perturbation_vs_georeferencing_error",
        "performance_degradation_curves",
    ]
    existing_types = {item["type"] for item in outputs}
    for item in required:
        if item not in existing_types:
            outputs.append({"type": item, "status": "NOT_GENERATED", "reason": "Requires measured degraded runs or ground truth artifacts."})
    return outputs
