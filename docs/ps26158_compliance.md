# PS 26158 compliance matrix

Status reflects demonstrable repository evidence as of Step 10, not aspiration. `PARTIAL` means an implementation exists but needs a representative field demonstration/evaluation. `NOT_TESTED` is never promoted by code presence alone.

| # | PS requirement | SkyTrace implementation / evidence | Status |
| --- | --- | --- | --- |
| 1 | Single-pass drone video | Step 1 accepts one chronological video; `tests/video/*`. A documented licensed field demo clip is still absent. | PARTIAL |
| 2 | 3D terrain | COLMAP point-cloud pipeline; processed viewer fixture. | PARTIAL |
| 3 | Structures | Generic reconstruction can contain structures; no labelled field proof. | NOT_TESTED |
| 4 | Building facades | No façade-specific validation. | NOT_TESTED |
| 5 | Rooftops | No rooftop-specific validation. | NOT_TESTED |
| 6 | Roads | No road-specific segmentation/validation. | NOT_TESTED |
| 7 | Infrastructure | No infrastructure-specific detection/validation. | NOT_TESTED |
| 8 | Vegetation | Can appear in point clouds; no vegetation evaluation. | NOT_TESTED |
| 9 | Obstacles | Dynamic-capable detector classes and scene markers; obstacle coverage not measured. | PARTIAL |
| 10 | Textured meshes / point clouds | PLY point clouds are supported; dense mesh/texturing is not demonstrated in the viewer. | PARTIAL |
| 11 | Georeferencing | GPS-to-local-ENU Step 3 with tests and residual output. | PARTIAL |
| 12 | Metric measurement | Step 6 ENU measurement/evidence; no surveyed ground-truth accuracy run. | PARTIAL |
| 13 | Limited viewing angles | Single-path/limited-view evaluation scenarios; no complete field comparison. | PARTIAL |
| 14 | Motion blur | Step 1 sharpness filter and controlled Step 8 scenario. | PARTIAL |
| 15 | Video compression | Controlled Step 8 compression inputs; not full-pipeline quantified. | PARTIAL |
| 16 | Variable illumination | Controlled Step 8 scenario; not full-pipeline quantified. | PARTIAL |
| 17 | Shadows | Controlled Step 8 scenario; not full-pipeline quantified. | PARTIAL |
| 18 | Dynamic objects | YOLO/ByteTrack, masks, conservative 3D association; world motion is intentionally unknown. | PARTIAL |
| 19 | GPS inaccuracies | Robust alignment and GPS-noise scenario; no real sensor distribution benchmark. | PARTIAL |
| 20 | Sensor noise | Scenario manifest exists; no sensor-noise labelled dataset/measurement. | NOT_TESTED |
| 21 | Near-real-time considerations | Stage timings are logged; no actual hardware benchmark. | NOT_TESTED |
| 22 | Occluded surfaces | Evidence/limitations avoid confirming unseen geometry; occlusion scenario exists. | PARTIAL |
| 23 | Limited/no GCP | GPS/no-GCP scenarios and explicit non-survey claim; no quantified no-GCP field test. | PARTIAL |
| 24 | Visualization | React/Three.js viewer and processed-demo API/UI tests. | IMPLEMENTED |
| 25 | Measurement | API/UI interaction and Step 6 reliability response. | IMPLEMENTED |
| 26 | Analysis | Evidence grid, reports, and reliability metadata. | IMPLEMENTED |

Before the final SIH review, update statuses only with linked run IDs, ground truth, and fresh-machine evidence.
