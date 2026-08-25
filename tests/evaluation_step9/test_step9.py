from __future__ import annotations

import json
from pathlib import Path

from evaluation.step9 import build_failure_priorities, write_step9_outputs


def _minimal_step8_report() -> dict:
    return {
        "dataset_dir": "data/evaluation",
        "baseline": {
            "metrics": {
                "video_duration_seconds": 4.8,
                "registered_frames": 10,
                "registration_rate": 0.8333,
                "point_count": 9,
                "detected_objects": 2,
                "objects_3d": 2,
                "object_3d_association_rate": 1.0,
                "total_processing_time_seconds": None,
                "processing_to_video_duration_ratio": None,
            }
        },
        "scenarios": [
            {"scenario": "processing_time", "status": "TESTED", "metrics": {"total_processing_time_seconds": None}},
            {"scenario": "motion_blur", "status": "REGISTERED", "generated_artifacts": [{"path": "blur.mp4"}]},
        ],
        "ps_requirement_scorecard": [
            {
                "ps_requirement": "Motion blur",
                "skytrace_component": "Step 1 frame filtering, Step 2 reconstruction",
                "test": "motion_blur",
                "result": "No measured experiment results yet.",
                "status": "NOT_TESTED",
            },
            {
                "ps_requirement": "Real-time / near-real-time processing",
                "skytrace_component": "Steps 1-7 timing metadata",
                "test": "processing_time",
                "result": "Metrics collected.",
                "status": "PARTIAL",
            },
        ],
    }


def test_failure_priorities_preserve_not_tested_gaps() -> None:
    priorities = build_failure_priorities(_minimal_step8_report())

    assert priorities[0]["failure"] == "processing_time"
    motion_blur = next(item for item in priorities if item["failure"] == "motion_blur")
    assert motion_blur["requires_more_data"] is True
    assert "Controlled degraded videos exist" in motion_blur["evidence"]


def test_write_step9_outputs_creates_required_artifacts(tmp_path: Path) -> None:
    report = tmp_path / "step8.json"
    report.write_text(json.dumps(_minimal_step8_report()), encoding="utf-8")

    paths = write_step9_outputs(
        before_report_path=report,
        after_report_path=report,
        output_dir=tmp_path / "step9",
        baseline_config_path="config/baseline.yaml",
        improved_config_path="config/robustness.yaml",
        dataset_dir="data/evaluation",
        innovation_path=tmp_path / "docs" / "skytrace_innovation.md",
    )

    assert Path(paths["failure_priorities"]).is_file()
    assert Path(paths["comparison"]).is_file()
    assert Path(paths["scorecard_json"]).is_file()
    assert Path(paths["scorecard_md"]).is_file()
    assert Path(paths["summary"]).is_file()
    summary = json.loads(Path(paths["summary"]).read_text(encoding="utf-8"))
    assert summary["scientific_note"].startswith("Accuracy improvements are NOT_TESTED")
    scorecard = json.loads(Path(paths["scorecard_json"]).read_text(encoding="utf-8"))
    assert any(row["after"] == "PARTIAL" for row in scorecard)
