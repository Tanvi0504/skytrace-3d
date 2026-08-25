# Requirement traceability

| ID | Requirement | Module | Input → output | Test / evidence | Limitation |
| --- | --- | --- | --- | --- | --- |
| R01 | One video ingestion | `pipeline.video` | video → frames, manifest | `tests/video/*` | Test clip provenance not recorded. |
| R02 | Frame quality | `pipeline.video.sharpness` | decoded frame → sharpness decision | `tests/video/test_sharpness.py` | Blur score is not a full reconstruction guarantee. |
| R03 | Reconstruction | `pipeline.reconstruction` | selected frames → COLMAP PLY/poses | `tests/reconstruction/*` | Requires COLMAP; local scale until Step 3. |
| R04 | Georeference | `pipeline.georeferencing` | poses + GPS → ENU PLY/transform | `tests/georeferencing/*` | Residual is not survey accuracy. |
| R05 | Object detection/tracking | `pipeline.objects` | frames + local model → detections/tracks/masks | `tests/objects/*` | Needs explicit model file; no motion claim from ID. |
| R06 | 3D object association | `pipeline.scene_objects` | 2D tracks + calibrated views → 3D records | `tests/scene_objects/*` | Insufficient views are unavailable/low confidence. |
| R07 | Measurement | `pipeline.analysis.measurements` | ENU points → distance | `tests/analysis/*` | Requires valid Step 3 coordinate system. |
| R08 | Evidence | `pipeline.analysis.evidence` | scene support → evidence grid | `tests/analysis/*` | Reliability signal, not numeric accuracy. |
| R09 | Web visualization | `frontend/src/viewer` | API scene/object/evidence → browser view | `frontend/src/components/Panels.test.tsx` | Large-scene field benchmark pending. |
| R10 | API safety | `backend/api`, `backend/services/paths` | upload/path → safe run files | `tests/backend/test_api.py` | Local deployment only; no auth. |
| R11 | Unified execution | `skytrace.run`, `skytrace.orchestrator` | video/config → result package | `scripts/test_e2e.sh` | Full execution needs external tools/data. |
| R12 | Input/resource report | `skytrace.validation` | input → `input_report.json` | CLI/system check | Does not estimate unmeasured peak RAM. |
| R13 | Checkpoint/resume | `skytrace.observability`, `skytrace.orchestrator` | stage artifacts → validated resume | `checkpoints/step<N>.done.json` | Requires retained outputs. |
| R14 | Logging/health | `skytrace.observability` | stage events → logs/health/metrics | `logs/*`, `pipeline_health.json` | Legacy pre-Step-10 runs are not retroactively packaged. |
| R15 | Result/report package | `skytrace.orchestrator` | actual outputs → manifest + HTML/JSON | `result_manifest.json` | Contains only produced artifacts; no fabricated metrics. |
| R16 | Dependency readiness | `skytrace.system_check` | host → READY/NOT READY | `python -m skytrace.system_check` | Does not install missing dependencies. |
| R17 | Model management | `skytrace.setup_models` | explicit URL/offline file → `models/yolo11n.pt` | `docs/model_weights.md` | Licence/checksum review remains team responsibility. |
| R18 | Demo readiness | `skytrace.demo_check` | services + fixture → DEMO READY/NOT READY | `/health`, API endpoints | Fixture is pre-processed, not live output. |
| R19 | Deployment | Dockerfiles / compose | repository → local services | `docker compose up --build` | Fresh build still needs execution evidence. |
| R20 | Robustness evaluation | `evaluation/`, `pipeline.evaluation` | scenario manifests → reports | `tests/evaluation*` | Several scenarios lack labelled ground truth. |
