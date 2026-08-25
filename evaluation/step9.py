"""Step 9 data-driven robustness improvement reporting.

This module intentionally separates measured improvements from engineering
readiness improvements. Step 8 did not provide ground truth for most PS 26158
challenges, so Step 9 must not invent accuracy gains.
"""

from __future__ import annotations

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def load_report(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_failure_priorities(step8_report: dict[str, Any]) -> list[dict[str, Any]]:
    """Rank Step 8 failures and NOT_TESTED gaps using only report evidence."""
    rows: list[dict[str, Any]] = []
    scorecard = step8_report.get("ps_requirement_scorecard", [])
    scenarios = {item.get("scenario"): item for item in step8_report.get("scenarios", [])}

    for row in scorecard:
        status = row.get("status")
        test_name = row.get("test")
        scenario = scenarios.get(test_name, {})
        if status == "PASS":
            continue
        severity = _severity_for(row, scenario, step8_report)
        rows.append(
            {
                "failure": test_name,
                "ps_requirement": row.get("ps_requirement"),
                "severity": severity,
                "observed_impact": _observed_impact(row, scenario, step8_report),
                "affected_stage": _affected_stage(row.get("skytrace_component", "")),
                "evidence": _evidence(row, scenario, step8_report),
                "technically_addressable": _technically_addressable(test_name, status),
                "requires_more_data": status == "NOT_TESTED",
                "mvp_realism": _mvp_realism(test_name, status),
                "recommended_action": _recommended_action(test_name, status),
            }
        )

    return sorted(rows, key=lambda item: (SEVERITY_ORDER[item["severity"]], item["failure"]))


def build_step9_comparison(
    before_report: dict[str, Any],
    after_report: dict[str, Any],
    *,
    implemented_improvements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create before/after metric rows without manufacturing positive deltas."""
    before_baseline = before_report.get("baseline", {}).get("metrics", {})
    after_baseline = after_report.get("baseline", {}).get("metrics", {})
    rows = []
    for metric in (
        "registered_frames",
        "registration_rate",
        "point_count",
        "detected_objects",
        "objects_3d",
        "object_3d_association_rate",
        "total_processing_time_seconds",
        "processing_to_video_duration_ratio",
    ):
        rows.append(
            {
                "scenario": "baseline",
                "metric": metric,
                "before": before_baseline.get(metric),
                "after": after_baseline.get(metric),
                "change": _numeric_change(before_baseline.get(metric), after_baseline.get(metric)),
                "improved": None,
                "reason": "No measured Step 9 pipeline rerun with changed algorithm output was available.",
            }
        )
    for item in implemented_improvements:
        rows.append(
            {
                "scenario": item["scenario"],
                "metric": item["metric"],
                "before": item["before"],
                "after": item["after"],
                "change": item["change"],
                "improved": item["improved"],
                "reason": item["reason"],
            }
        )
    return rows


def build_step9_scorecard(before_report: dict[str, Any], comparison_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    improvements = {row["metric"]: row for row in comparison_rows if row.get("improved") is not None}
    output = []
    for row in before_report.get("ps_requirement_scorecard", []):
        challenge = row.get("ps_requirement")
        before = row.get("status")
        after = before
        improvement = "No measured accuracy/status improvement."
        remaining = row.get("result")
        if row.get("test") == "processing_time" and "processing_time_observability" in improvements:
            after = "PARTIAL"
            improvement = "Future run_state summaries now preserve per-stage processing_time_seconds."
            remaining = "Existing processed-demo lacks measured timings; real-time still cannot be claimed."
        if row.get("test") == "metric_accuracy" and "measurement_reliability_status" in improvements:
            improvement = "Low/insufficient evidence now produces explicit reliability statuses."
            remaining = "Ground-truth measurements are still required for metric accuracy."
        output.append(
            {
                "ps_challenge": challenge,
                "before": before,
                "after": after,
                "improvement": improvement,
                "remaining_weakness": remaining,
            }
        )
    return output


def write_step9_outputs(
    *,
    before_report_path: str | Path,
    after_report_path: str | Path,
    output_dir: str | Path,
    baseline_config_path: str | Path | None = None,
    improved_config_path: str | Path | None = None,
    dataset_dir: str | Path | None = None,
    innovation_path: str | Path = "docs/skytrace_innovation.md",
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    before_report = load_report(before_report_path)
    after_report = load_report(after_report_path)
    implemented = [
        {
            "scenario": "processing_time",
            "metric": "processing_time_observability",
            "before": "future backend runs did not include per-stage processing_time_seconds in run_state summaries",
            "after": "future backend runs include per-stage processing_time_seconds for Steps 1-6",
            "change": "instrumentation added",
            "improved": True,
            "reason": "Step 8 could not support a real-time claim because total_processing_time_seconds was null.",
        },
        {
            "scenario": "metric_accuracy",
            "metric": "measurement_reliability_status",
            "before": "measurements used ESTIMATED or INSUFFICIENT_EVIDENCE",
            "after": "measurements use MEASUREMENT_AVAILABLE, MEASUREMENT_AVAILABLE_WITH_WARNING, or MEASUREMENT_NOT_RELIABLE",
            "change": "status contract strengthened",
            "improved": True,
            "reason": "Step 8 emphasized not returning confident measurements where evidence is weak.",
        },
    ]
    priorities = build_failure_priorities(before_report)
    comparison = build_step9_comparison(before_report, after_report, implemented_improvements=implemented)
    scorecard = build_step9_scorecard(before_report, comparison)
    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "step8_report": str(before_report_path),
        "after_report": str(after_report_path),
        "dataset_dir": str(dataset_dir) if dataset_dir else before_report.get("dataset_dir"),
        "baseline_config": str(baseline_config_path) if baseline_config_path else None,
        "improved_config": str(improved_config_path) if improved_config_path else None,
        "scientific_note": "Accuracy improvements are NOT_TESTED unless Step 8/9 reports contain ground truth.",
        "failure_priorities": priorities,
        "implemented_improvements": implemented,
        "step9_comparison": comparison,
        "step9_scorecard": scorecard,
        "ablation_results": [
            {
                "ablation": "baseline vs timing instrumentation",
                "status": "PARTIAL",
                "result": "Instrumentation improves observability; no reconstruction metric is expected to change.",
            },
            {
                "ablation": "baseline vs measurement reliability status contract",
                "status": "PARTIAL",
                "result": "Reliability wording improves failure preservation; metric accuracy remains NOT_TESTED without ground truth.",
            },
        ],
        "regression_tests": {"status": "RUN_SEPARATELY", "command": "python -m pytest -q --basetemp .pytest-tmp-all"},
    }
    files = {
        "failure_priorities": output / "failure_priorities.json",
        "comparison": output / "step9_comparison.json",
        "scorecard_json": output / "step9_scorecard.json",
        "scorecard_md": output / "step9_scorecard.md",
        "innovation": Path(innovation_path),
        "summary": output / "step9_summary.json",
    }
    files["failure_priorities"].write_text(json.dumps(priorities, indent=2), encoding="utf-8")
    files["comparison"].write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    files["scorecard_json"].write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    files["scorecard_md"].write_text(_scorecard_markdown(scorecard), encoding="utf-8")
    files["innovation"].parent.mkdir(parents=True, exist_ok=True)
    files["innovation"].write_text(
        _innovation_markdown(priorities, implemented, scorecard),
        encoding="utf-8",
    )
    files["summary"].write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {key: str(value) for key, value in files.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate SkyTrace Step 9 data-driven robustness deliverables."
    )
    parser.add_argument(
        "--baseline-report",
        default="evaluation/results/robustness_report.json",
        help="Step 8 report before robustness changes.",
    )
    parser.add_argument(
        "--after-report",
        default="evaluation/results/robustness_report.json",
        help="Step 8/9 report after changes. Reuse baseline if no rerun exists.",
    )
    parser.add_argument("--dataset", default="data/evaluation", help="Evaluation dataset root.")
    parser.add_argument("--baseline-config", default="config/baseline.yaml")
    parser.add_argument("--improved-config", default="config/robustness.yaml")
    parser.add_argument("--output", default="evaluation/step9", help="Step 9 output directory.")
    args = parser.parse_args(argv)

    paths = write_step9_outputs(
        before_report_path=args.baseline_report,
        after_report_path=args.after_report,
        output_dir=args.output,
        baseline_config_path=args.baseline_config,
        improved_config_path=args.improved_config,
        dataset_dir=args.dataset,
    )
    print(json.dumps({"step9_paths": paths}, indent=2))
    return 0


def _severity_for(row: dict[str, Any], scenario: dict[str, Any], report: dict[str, Any]) -> str:
    if row.get("status") == "FAIL":
        return "critical"
    if row.get("test") in {"metric_accuracy", "processing_time", "limited_view", "gps_noise"}:
        return "high"
    if scenario.get("generated_artifacts") and not scenario.get("metrics"):
        return "medium"
    return "medium" if row.get("status") == "NOT_TESTED" else "low"


def _observed_impact(row: dict[str, Any], scenario: dict[str, Any], report: dict[str, Any]) -> str:
    if row.get("test") == "processing_time":
        return "Step 8 baseline has video_duration_seconds=4.8 but total_processing_time_seconds is null."
    if row.get("status") == "NOT_TESTED":
        return f"{row.get('ps_requirement')} could not be measured from available Step 8 artifacts."
    return str(row.get("result"))


def _affected_stage(component: str) -> str:
    if "Step 1" in component:
        return "frame_ingestion"
    if "Step 2" in component:
        return "reconstruction"
    if "Step 3" in component:
        return "georeferencing"
    if "Step 4" in component:
        return "object_detection"
    if "Step 5" in component:
        return "object_3d_association"
    if "Step 6" in component:
        return "measurement_evidence"
    return "evaluation"


def _evidence(row: dict[str, Any], scenario: dict[str, Any], report: dict[str, Any]) -> str:
    if row.get("test") == "processing_time":
        return "robustness_report.json baseline.metrics.total_processing_time_seconds == null."
    if scenario.get("generated_artifacts"):
        return "Controlled degraded videos exist, but scenario metrics remain empty because they were not run through the full pipeline."
    return str(row.get("result") or "No measured result in Step 8 report.")


def _technically_addressable(test_name: str, status: str) -> bool:
    return test_name in {"processing_time", "metric_accuracy", "limited_view", "occlusion", "dynamic_objects"} or status == "FAIL"


def _mvp_realism(test_name: str, status: str) -> str:
    if status == "NOT_TESTED":
        return "Needs more evaluation data before algorithmic tuning is scientifically justified."
    if test_name == "processing_time":
        return "Instrumentation is realistic in the MVP; real-time optimization needs measured timings first."
    return "Addressable after measured degradation is available."


def _recommended_action(test_name: str, status: str) -> str:
    actions = {
        "processing_time": "Add per-stage timing to future run_state summaries and rerun Step 8.",
        "metric_accuracy": "Collect ground_truth_measurements.json and keep low-evidence measurements visibly unreliable.",
        "limited_view": "Add surface-completeness ground truth; improve evidence propagation before geometry inference.",
        "gps_noise": "Run controlled GPS perturbation cases and compare absolute georeferencing vs relative geometry.",
        "dynamic_objects": "Add object labels and compare raw vs dynamic-aware reconstruction only when both runs exist.",
        "occlusion": "Supply occlusion/completeness annotations and preserve observed vs uncertain geometry labels.",
    }
    return actions.get(test_name, "Supply the missing Step 8 dataset/ground truth before tuning algorithms.")


def _numeric_change(before: Any, after: Any) -> float | None:
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return float(after) - float(before)
    return None


def _scorecard_markdown(scorecard: list[dict[str, Any]]) -> str:
    lines = [
        "# SkyTrace Step 9 Scorecard",
        "",
        "| PS Challenge | Before | After | Improvement | Remaining Weakness |",
        "|---|---|---|---|---|",
    ]
    for row in scorecard:
        lines.append(
            f"| {row['ps_challenge']} | {row['before']} | {row['after']} | "
            f"{_cell(row['improvement'])} | {_cell(row['remaining_weakness'])} |"
        )
    return "\n".join(lines) + "\n"


def _innovation_markdown(
    priorities: list[dict[str, Any]],
    implemented: list[dict[str, Any]],
    scorecard: list[dict[str, Any]],
) -> str:
    not_tested = [item for item in priorities if item.get("requires_more_data")]
    lines = [
        "# SkyTrace Innovation Notes",
        "",
        "This document records only Step 9 claims supported by the checked-in Step 8 report and the current code.",
        "",
        "## Implemented and Supported",
        "",
        "- Evidence-aware measurement reliability: Step 6 now emits explicit measurement availability states instead of presenting weak-evidence distances as ordinary estimates.",
        "- Processing-time observability: future backend runs preserve per-stage timing in Step 1-6 run summaries so near-real-time claims can be tested instead of assumed.",
        "- Failure-preserving robustness reporting: Step 9 generates failure priorities, before/after comparison rows, and a PS challenge scorecard without converting missing tests into successes.",
        "",
        "## Not Claimed",
        "",
        "- Survey-grade accuracy is not claimed.",
        "- Real-time or near-real-time performance is not claimed until a rerun records total processing time.",
        "- Occluded or unseen surfaces are not hallucinated as observed geometry.",
        "- Synthetic stress videos are not described as real-world validation.",
        "",
        "## Experimental Support",
        "",
    ]
    for item in implemented:
        lines.append(f"- {item['metric']}: {item['reason']}")
    lines.extend(
        [
            "",
            "## Remaining Evidence Gaps",
            "",
        ]
    )
    for item in not_tested:
        lines.append(f"- {item['failure']}: {item['recommended_action']}")
    lines.extend(
        [
            "",
            "## PS Scorecard Summary",
            "",
            "| PS Challenge | Before | After | Remaining Weakness |",
            "|---|---|---|---|",
        ]
    )
    for row in scorecard:
        lines.append(
            f"| {_cell(row['ps_challenge'])} | {row['before']} | {row['after']} | {_cell(row['remaining_weakness'])} |"
        )
    return "\n".join(lines) + "\n"


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
