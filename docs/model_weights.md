# Model and weight management

SkyTrace uses one optional learned component in the current pipeline: the Ultralytics YOLO11 nano detector in Step 4. Reconstruction is performed by COLMAP; it is an external executable, not a model-weight download managed by this repository.

| Component | Version/configuration | Source | Expected local path | Approx. size | License note |
| --- | --- | --- | --- | --- | --- |
| YOLO11n object detector | `yolo11n.pt` | Ultralytics release asset, downloaded only by `python -m skytrace.setup_models` | `models/yolo11n.pt` | ~5.4 MB | Review Ultralytics' current AGPL-3.0 / Enterprise licensing terms before deployment. |
| COLMAP reconstruction | System package / executable | [COLMAP releases](https://github.com/colmap/colmap/releases) | `colmap` on `PATH` | Varies by OS | BSD-3-Clause (check the installed release). |

The application never downloads model weights at server start. A missing local file causes Step 4 to fail with its exact required path; this is intentional for offline and demo-safe operation.

Online setup:

```bash
python -m skytrace.setup_models
```

Offline setup: download the exact `yolo11n.pt` release asset on an approved connected machine, verify its checksum according to your team policy, and copy it to `models/yolo11n.pt`. Then run `python -m skytrace.system_check`.
