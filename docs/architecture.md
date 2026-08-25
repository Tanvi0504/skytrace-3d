# SkyTrace architecture

```text
User
  ↓ upload / CLI arguments
Frontend (React + Three.js) ────────→ FastAPI API
                                      ↓
                              Step 10 orchestrator
                                      ↓
 Step 1 frames → Step 2 COLMAP → Step 3 GPS/ENU → Step 4 objects
                                      ↓                 ↓
                        Step 6 evidence ← Step 5 3D association
                                      ↓
                     Result package / reports / 3D viewer assets
```

## Responsibilities and data flow

| Layer | Input | Output | Operational contract |
| --- | --- | --- | --- |
| Frontend | MP4 upload; user measurement clicks | run ID, progress, point-cloud/object/evidence requests | Never performs scientific processing; polls real API status. |
| API | Sanitised run ID and upload | Filesystem-backed run directory | 1 GB upload cap, MP4-only UI upload, controlled CORS, path-safe assets. |
| Orchestrator | Video, optional metadata, YAML profile | Stages 1–6 + package | Validates inputs/resources, logs each stage, checkpoints validated outputs, resumes safely. |
| Step 1 | Video | selected frames + manifest | Records rejected/selected frames and actual metadata. |
| Step 2 | Frames | local COLMAP sparse/dense artifacts | Local arbitrary-scale coordinates until Step 3 succeeds. |
| Step 3 | poses + GPS metadata | local ENU metres / transform | May be skipped transparently if GPS is missing or invalid. |
| Step 4 | Frames + local weights | 2D detections, tracks, masks | Weight download is explicit; no application-start download. |
| Step 5 | 2D tracks + calibrated geometry | conservative 3D object records | Does not invent 3D locations with insufficient views. |
| Step 6 | georeferenced scene + object markers | measurement/evidence files | Not run without valid metre-valued georeferencing. |

## File and metadata flow

Every live CLI run is rooted at `results/<run-id>/`. Stage files stay in their owning directories (`frames/`, `reconstruction/`, `georeferenced/`, `objects/`, `scene_objects/`, `analysis/`) so Steps 1–9 contracts remain unchanged. Step 10 adds:

- `input_report.json`: decoded video facts, metadata presence, and resource warnings.
- `logs/pipeline.log`, `logs/errors.log`, `logs/metrics.json`: run ID, stage, timestamp, duration, warning/error records.
- `checkpoints/step<N>.done.json`: expected stage artifacts; resume additionally validates their metadata/content.
- `pipeline_health.json`: first failed stage and stage-by-stage status.
- `result_manifest.json` and `skytrace_report.{json,html}`: configuration, outputs, actual metrics, warnings, limitations.
- `scene/`, `pointcloud/`, `mesh/`, `objects/`, `measurements/`, `evidence/`, `metadata/`: lightweight indexes that point to source artifacts without duplicating scientific data.

## Measurement and evidence flow

The viewer sends two selected 3D points to `POST /runs/{run_id}/measure`. The API loads the stored Step 3/5 scene context and calls the existing Step 6 measurement routine. The response includes 3D/horizontal/vertical distances only when the coordinate system supports them, plus endpoint/segment evidence and warnings. Evidence is an interpretability/reliability signal, not a measured accuracy percentage.

## Storage

SkyTrace currently uses filesystem-backed run storage (`outputs/<run-id>` for web runs, `results/<run-id>` for CLI runs). A database is not introduced because no current workflow requires multi-user query or transactional persistence. The API reports this explicitly through `/health/dependencies`.
