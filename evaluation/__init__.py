"""SkyTrace Step 8 robustness and PS-challenge evaluation framework."""

from evaluation.failure import FAILURE_TAXONOMY, classify_failure
from evaluation.metrics import (
    aggregate_numeric,
    compare_against_baseline,
    completeness_metrics,
    evidence_score_validation,
    measurement_error_metrics,
    object_detection_metrics,
    object_localization_metrics,
)
from evaluation.reports import build_report, write_reports

__all__ = [
    "FAILURE_TAXONOMY",
    "classify_failure",
    "aggregate_numeric",
    "compare_against_baseline",
    "completeness_metrics",
    "evidence_score_validation",
    "measurement_error_metrics",
    "object_detection_metrics",
    "object_localization_metrics",
    "build_report",
    "write_reports",
]
