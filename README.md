# SKYTRACE — Single-Pass Drone Video to 3D Model Generation

SkyTrace processes one drone-video flight through frame selection, COLMAP reconstruction, optional GPS georeferencing, object detection, conservative 3D association, measurement/evidence analysis, and a browser viewer. Step 10 adds the production integration layer: one CLI, validated checkpoints, per-run logs, reports, health checks, Docker files, and a transparent demo fallback.

## What the current implementation does

```
video → validation → frames → reconstruction → georeferencing
      → object detection → 3D association → evidence/measurement → report + viewer
```

The processing modules are deliberately conservative. GPS alignment residuals and evidence scores are not survey-accuracy claims; occluded areas and insufficiently supported object positions are marked unavailable or low confidence.

## Requirements

- Python 3.10–3.12 (3.11 is the tested Docker base)
- Node 20–22 for the frontend
- FFmpeg and COLMAP on `PATH` for live reconstruction
- 10 GB free storage minimum; more is needed for real dense reconstructions
- CPU-only operation is supported by default. NVIDIA CUDA is optional and is not required for the shipped configuration.

## Quick start

```bash
git clone <repository-url> skytrace-3d
cd skytrace-3d
./scripts/setup.sh
./scripts/start.sh
```

`setup.sh` selects a native Python/Node setup when Python 3.11 and Node are available; otherwise it uses a running Docker Desktop/Engine. Use `SKYTRACE_SETUP_MODE=native` or `docker` to choose explicitly. Native setup requires FFmpeg and COLMAP on `PATH`; the Docker image installs both. Copy `.env.example` to `.env` before changing browser origins or the public API URL. See [REPRODUCE.md](REPRODUCE.md) and [the dependency reference](docs/dependencies.md) for complete environment details.

## Run one complete pipeline

Use a real, authorised drone video and compatible GPS metadata:

```bash
python -m skytrace.run \
  --video /path/to/flight.mp4 \
  --metadata /path/to/gps_metadata.json \
  --output results \
  --run-id field-demo-01 \
  --config config/default.yaml
```

Results are in `results/field-demo-01/`, including `result_manifest.json`, `pipeline_health.json`, `logs/`, checkpoints, and `skytrace_report.html`. To recover a stopped run, validate existing artifacts and continue from the first incomplete stage:

```bash
python -m skytrace.run --run-id field-demo-01 --output results --resume
```

The run fails early for a bad video, resource limit, missing COLMAP, or missing object-model file. If GPS is absent or unusable, the local reconstruction and object stages can continue, but metric georeferencing and Step 6 measurement/evidence are explicitly skipped.

## Web application and deterministic backup demo

Start both services locally:

```bash
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
cd frontend && npm run dev
```

Open `http://127.0.0.1:5173/viewer/processed-demo`. It is visibly labelled **PRE-PROCESSED DEMO RESULT**. It is a backup viewer result, not a claim of live processing.

```bash
python -m skytrace.demo_check
python -m skytrace.demo --open
```

## Docker

CPU-first containers are supplied for backend and frontend:

```bash
docker compose up --build
```

Open `http://localhost:8080/viewer/processed-demo`; backend health is at `http://localhost:8000/health`. Put approved weights at `models/yolo11n.pt` before a live object-detection run. Docker's default image has FFmpeg/COLMAP but uses CPU; an NVIDIA/CUDA deployment needs a compatible host runtime and a separately tested GPU image/configuration.

## Configuration, evaluation, and tests

`config/default.yaml` centralises every Step 10-operated input, frame, reconstruction, georeference, object, evidence, visualization, and resource setting. `config/demo.yaml` is a faster live-demo profile and `config/evaluation.yaml` retains conservative CPU/sparse settings.

```bash
pytest
cd frontend && npm test && npm run build
cd .. && python evaluation/run_suite.py --dataset data/evaluation --processed-run outputs/processed-demo
sh scripts/test_e2e.sh                 # requires COLMAP, weights, and an authorised input
```

The checked-in `data/test/example.mp4` has no recorded source/licence provenance. It is engineering-test material, not an official SIH demo dataset; see [data/demo_dataset.md](data/demo_dataset.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Reproduction guide](REPRODUCE.md)
- [Model weights](docs/model_weights.md)
- [PS 26158 compliance matrix](docs/ps26158_compliance.md)
- [Requirement traceability](docs/requirement_traceability.md)
- [Demo script](docs/demo_script.md), [judge questions](docs/judge_questions.md), and [go/no-go](docs/final_go_no_go.md)

## Contribution guidance

Do not commit weights, raw videos, dense point clouds, logs, generated reports, secrets, or caches. Keep algorithm changes within their owning Step 1–9 module; route operational configuration through `config/` and preserve the run manifest/checkpoint contract.
