# Performance benchmark status

No full live benchmark is checked in yet. SkyTrace deliberately does not claim near-real-time or universal throughput without a run-specific measurement.

For each judged machine, retain `results/<run-id>/logs/metrics.json`, `input_report.json`, and `result_manifest.json`, then record:

| Metric | Source |
| --- | --- |
| Hardware / OS / CPU / GPU / CUDA | `python -m skytrace.system_check --json` |
| Video duration, resolution, decoded/selected frames | `input_report.json`, Step 1 summary |
| Reconstruction, detection, association, measurement, total time | `logs/metrics.json` |
| Peak RAM / VRAM | External host monitor captured during the same run (not currently implemented as a fabricated estimate) |
| Output size | `du -sh results/<run-id>` or platform equivalent |

Current status: **NOT MEASURED**. The current environment lacks a configured project Python environment and COLMAP, so it cannot produce a credible live benchmark. Resolve `system_check` blockers, use an authorised real input, run the complete pipeline, and update this document with the manifest/run ID rather than a generalised number.
