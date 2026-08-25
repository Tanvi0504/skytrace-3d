"""Failure taxonomy for robustness experiments."""

from __future__ import annotations

from typing import Any


FAILURE_TAXONOMY: dict[str, dict[str, str]] = {
    "FRAME_QUALITY_FAILURE": {
        "stage": "STEP_1",
        "severity": "high",
        "possible_mitigation": "Increase image quality, lower blur, or adjust frame-selection threshold.",
    },
    "INSUFFICIENT_FEATURE_MATCHES": {
        "stage": "STEP_2",
        "severity": "high",
        "possible_mitigation": "Improve overlap, reduce blur/compression, or use more textured views.",
    },
    "CAMERA_POSE_FAILURE": {
        "stage": "STEP_2",
        "severity": "critical",
        "possible_mitigation": "Collect a smoother single pass with stronger overlap and more stable exposure.",
    },
    "RECONSTRUCTION_SPARSE": {
        "stage": "STEP_2",
        "severity": "medium",
        "possible_mitigation": "Increase usable frames or improve feature support before dense reconstruction.",
    },
    "GEOREFERENCE_FAILURE": {
        "stage": "STEP_3",
        "severity": "high",
        "possible_mitigation": "Provide usable GPS metadata or better timestamp correspondence.",
    },
    "OBJECT_DETECTION_FAILURE": {
        "stage": "STEP_4",
        "severity": "medium",
        "possible_mitigation": "Check detector model/classes and image quality.",
    },
    "OBJECT_3D_ASSOCIATION_FAILURE": {
        "stage": "STEP_5",
        "severity": "medium",
        "possible_mitigation": "Improve calibrated multi-view support for tracked objects.",
    },
    "INSUFFICIENT_GEOMETRY": {
        "stage": "STEP_6",
        "severity": "high",
        "possible_mitigation": "Avoid measuring weakly reconstructed or unseen regions.",
    },
    "MEASUREMENT_LOW_EVIDENCE": {
        "stage": "STEP_6",
        "severity": "medium",
        "possible_mitigation": "Use endpoints with higher reconstruction support or collect better views.",
    },
    "DYNAMIC_OBJECT_CONTAMINATION": {
        "stage": "STEP_4_STEP_6",
        "severity": "medium",
        "possible_mitigation": "Mask dynamic candidates and compare raw vs dynamic-aware reconstruction.",
    },
    "OCCLUSION": {
        "stage": "DATASET",
        "severity": "medium",
        "possible_mitigation": "Report occluded surfaces as low evidence; do not infer hidden geometry.",
    },
    "PROCESSING_TIMEOUT": {
        "stage": "PIPELINE",
        "severity": "high",
        "possible_mitigation": "Profile stages, downsample for evaluation, or set explicit time budgets.",
    },
    "UNKNOWN": {
        "stage": "UNKNOWN",
        "severity": "unknown",
        "possible_mitigation": "Inspect logs and add a more specific classifier rule.",
    },
}


def classify_failure(run_status: dict[str, Any] | None, metrics: dict[str, Any] | None = None) -> dict[str, str] | None:
    """Classify a failed/degraded run without hiding the raw reason."""
    metrics = metrics or {}
    if metrics.get("timeout"):
        return _payload("PROCESSING_TIMEOUT", "Processing exceeded the configured time budget.")
    if not run_status:
        return None

    failed_step = next((step for step in run_status.get("steps", []) if step.get("status") == "FAILED"), None)
    if failed_step:
        step = int(failed_step.get("step", 0))
        reason = str(failed_step.get("error") or "Pipeline step failed.")
        mapping = {
            1: "FRAME_QUALITY_FAILURE",
            2: "CAMERA_POSE_FAILURE" if "pose" in reason.lower() else "INSUFFICIENT_FEATURE_MATCHES",
            3: "GEOREFERENCE_FAILURE",
            4: "OBJECT_DETECTION_FAILURE",
            5: "OBJECT_3D_ASSOCIATION_FAILURE",
            6: "INSUFFICIENT_GEOMETRY",
        }
        return _payload(mapping.get(step, "UNKNOWN"), reason)

    if metrics.get("evidence_level") in {"LOW", "INSUFFICIENT"}:
        return _payload("MEASUREMENT_LOW_EVIDENCE", "Measurement evidence is low or insufficient.")
    if metrics.get("dynamic_marker_count", 0):
        return _payload("DYNAMIC_OBJECT_CONTAMINATION", "Dynamic markers were present near evaluated geometry.")
    return None


def _payload(failure_type: str, description: str) -> dict[str, str]:
    template = FAILURE_TAXONOMY[failure_type]
    return {
        "failure_type": failure_type,
        "stage": template["stage"],
        "description": description,
        "severity": template["severity"],
        "possible_mitigation": template["possible_mitigation"],
    }
