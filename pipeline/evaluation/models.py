"""Structured Step 6 ground-truth evaluation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class EvaluationResult:
    """Error metrics deliberately distinct from Step 6 evidence and Step 3 residuals."""

    success: bool
    predictions_path: Path
    ground_truth_path: Path
    output_dir: Path
    measurement_count: int = 0
    mean_absolute_error_metres: Optional[float] = None
    median_absolute_error_metres: Optional[float] = None
    rmse_metres: Optional[float] = None
    mean_percentage_error: Optional[float] = None
    worst_case_absolute_error_metres: Optional[float] = None
    processing_time_seconds: float = 0.0
    report_path: Optional[Path] = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "predictions_path": str(self.predictions_path),
            "ground_truth_path": str(self.ground_truth_path),
            "output_dir": str(self.output_dir),
            "measurement_count": self.measurement_count,
            "metrics_metres": {
                "mean_absolute_error": self.mean_absolute_error_metres,
                "median_absolute_error": self.median_absolute_error_metres,
                "rmse": self.rmse_metres,
                "worst_case_absolute_error": self.worst_case_absolute_error_metres,
            },
            "mean_percentage_error": self.mean_percentage_error,
            "processing_time_seconds": round(self.processing_time_seconds, 4),
            "report_path": str(self.report_path) if self.report_path is not None else None,
            "error": self.error,
            "warnings": self.warnings,
        }
