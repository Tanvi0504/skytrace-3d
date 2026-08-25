"""Per-run structured logging, checkpoints, manifests, and reports."""

from __future__ import annotations

import html
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGE_NAMES = {
    1: "Frame extraction and quality filtering",
    2: "3D reconstruction",
    3: "Georeferencing",
    4: "Object detection and tracking",
    5: "3D object association",
    6: "Measurement and evidence analysis",
    7: "Result packaging and visualization hand-off",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunObserver:
    """Keeps auditable stage records without changing processing algorithms."""

    def __init__(self, run_id: str, directory: Path) -> None:
        self.run_id = run_id
        self.directory = directory
        self.logs_dir = directory / "logs"
        self.checkpoints_dir = directory / "checkpoints"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_path = self.logs_dir / "metrics.json"
        self.pipeline_log_path = self.logs_dir / "pipeline.log"
        self.errors_log_path = self.logs_dir / "errors.log"
        self.started_monotonic = time.monotonic()
        self.started_at = utc_now()
        self.stages: dict[str, dict[str, Any]] = {}
        self.logger = logging.getLogger(f"skytrace.run.{run_id}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            formatter = logging.Formatter("%(asctime)s %(levelname)s run=%(run_id)s stage=%(stage)s %(message)s")
            pipeline_handler = logging.FileHandler(self.pipeline_log_path, encoding="utf-8")
            pipeline_handler.setFormatter(formatter)
            self.logger.addHandler(pipeline_handler)
            error_handler = logging.FileHandler(self.errors_log_path, encoding="utf-8")
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            self.logger.addHandler(error_handler)
        self._write_metrics()

    def _log(self, level: int, stage: int, message: str) -> None:
        self.logger.log(level, message, extra={"run_id": self.run_id, "stage": stage})

    def start(self, stage: int) -> float:
        self._log(logging.INFO, stage, "started")
        self.stages[str(stage)] = {
            "stage": stage,
            "name": STAGE_NAMES[stage],
            "status": "RUNNING",
            "started_at": utc_now(),
            "duration_seconds": None,
            "summary": {},
            "warnings": [],
            "error": None,
        }
        self._write_metrics()
        return time.monotonic()

    def finish(
        self,
        stage: int,
        started: float,
        *,
        status: str = "OK",
        summary: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        record = self.stages.get(str(stage), {"stage": stage, "name": STAGE_NAMES[stage], "started_at": utc_now()})
        record.update(
            {
                "status": status,
                "finished_at": utc_now(),
                "duration_seconds": round(time.monotonic() - started, 4),
                "summary": summary or {},
                "warnings": list(dict.fromkeys(warnings or [])),
                "error": error,
            }
        )
        self.stages[str(stage)] = record
        level = logging.ERROR if status == "FAILED" else logging.WARNING if status in {"WARNING", "SKIPPED"} else logging.INFO
        message = f"{status.lower()} in {record['duration_seconds']:.2f}s"
        if error:
            message = f"{message}: {error}"
        self._log(level, stage, message)
        self._write_metrics()
        return record

    def checkpoint(self, stage: int, artifacts: list[Path]) -> None:
        document = {
            "schema_version": 1,
            "run_id": self.run_id,
            "stage": stage,
            "name": STAGE_NAMES[stage],
            "completed_at": utc_now(),
            "artifacts": [str(path.relative_to(self.directory)) for path in artifacts],
        }
        (self.checkpoints_dir / f"step{stage}.done.json").write_text(json.dumps(document, indent=2), encoding="utf-8")

    def invalidate_checkpoint(self, stage: int, reason: str) -> None:
        path = self.checkpoints_dir / f"step{stage}.done.json"
        path.unlink(missing_ok=True)
        self._log(logging.WARNING, stage, f"checkpoint invalid: {reason}")

    def checkpoint_document(self, stage: int) -> dict[str, Any] | None:
        path = self.checkpoints_dir / f"step{stage}.done.json"
        if not path.is_file():
            return None
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.invalidate_checkpoint(stage, "checkpoint file is unreadable")
            return None
        return document if isinstance(document, dict) else None

    def _write_metrics(self) -> None:
        document = {
            "schema_version": 1,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "updated_at": utc_now(),
            "elapsed_seconds": round(time.monotonic() - self.started_monotonic, 4),
            "stages": list(self.stages.values()),
        }
        self.metrics_path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    def close(self) -> None:
        self._write_metrics()


def write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


def all_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.is_file())


def write_report(directory: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    """Produce compact JSON and HTML reports from actual manifest values only."""
    report_json = directory / "skytrace_report.json"
    report_html = directory / "skytrace_report.html"
    write_json(report_json, manifest)
    rows = []
    for stage in manifest["pipeline"]["stages"]:
        rows.append(
            "<tr>"
            f"<td>{stage['stage']}</td><td>{html.escape(stage['name'])}</td>"
            f"<td>{html.escape(stage['status'])}</td><td>{stage.get('duration_seconds', '')}</td>"
            f"<td>{html.escape('; '.join(stage.get('warnings', [])))}</td>"
            f"<td>{html.escape(stage.get('error') or '')}</td>"
            "</tr>"
        )
    warnings = "".join(f"<li>{html.escape(item)}</li>" for item in manifest.get("warnings", [])) or "<li>None</li>"
    limitations = "".join(f"<li>{html.escape(item)}</li>" for item in manifest.get("limitations", [])) or "<li>None recorded</li>"
    report_html.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>SkyTrace report</title>"
        "<style>body{font-family:system-ui;margin:2rem;color:#152238}table{border-collapse:collapse;width:100%}th,td{border:1px solid #cbd5e1;padding:.5rem;text-align:left;vertical-align:top}th{background:#e2e8f0}.badge{font-weight:bold}</style>"
        "</head><body>"
        f"<h1>SkyTrace report — {html.escape(manifest['run_id'])}</h1>"
        f"<p class='badge'>Pipeline status: {html.escape(manifest['pipeline']['status'])}</p>"
        f"<p>Generated at: {html.escape(manifest['generated_at'])}</p>"
        "<h2>Pipeline health</h2><table><thead><tr><th>#</th><th>Stage</th><th>Status</th><th>Seconds</th><th>Warnings</th><th>Failure</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        + "<h2>Warnings</h2><ul>" + warnings + "</ul>"
        + "<h2>Limitations</h2><ul>" + limitations + "</ul>"
        + "<p>Evidence levels describe reconstruction support; they are not accuracy percentages. No accuracy claim is made unless a separate ground-truth evaluation is supplied.</p>"
        + "</body></html>",
        encoding="utf-8",
    )
    return report_json, report_html
