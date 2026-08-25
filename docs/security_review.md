# Step 10 security and safety review

| Check | Current control | Status |
| --- | --- | --- |
| Hard-coded secrets/API keys | Repository text scan and configuration review; no secret mechanism introduced. | PASS (repeat before release) |
| Upload filename/path traversal | `sanitize_filename`, MP4 restriction, 1 GB cap, per-run directory. | PASS |
| Asset path traversal | `resolve_in_run` rejects paths outside the run directory; API test exists. | PASS |
| GPS metadata path traversal | Backend resolves request paths within the owning run directory. | PASS |
| CORS | Local origins only; configurable through `SKYTRACE_CORS_ORIGINS`. | PASS for local deployment |
| Arbitrary filesystem API | API exposes only safe files within a run. | PASS |
| Model downloads | Explicit `setup_models` command; orchestrated web run checks local file. | PASS |
| Debug mode | Docker/API command has no reload/debug mode. | PASS |
| Authentication | Not implemented. | ACCEPTED only for local/SIH deployment; add auth before network exposure. |

Do not place `.env`, credentials, model weights, raw videos, outputs, logs, or datasets with restricted data in Git. Rerun a secret scanner in the release environment; this review is not a substitute for organisational security policy.
