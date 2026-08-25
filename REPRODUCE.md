# Reproduce SkyTrace from a clean machine

This guide intentionally distinguishes an actual live run from the checked-in pre-processed viewer backup.

## 1. Clone and create a Python environment

```bash
git clone <repository-url> skytrace-3d
cd skytrace-3d
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Python 3.10–3.12 is supported; use 3.11 for parity with Docker. The project is developed for macOS/Linux. Windows users need a COLMAP/FFmpeg installation visible on `PATH` and should use the equivalent virtual-environment activation command.

## 2. Install tools and frontend

On Debian/Ubuntu: `sudo apt-get install ffmpeg colmap`. On macOS, install equivalent approved packages and verify `ffmpeg -version` and `colmap -h`.

```bash
cd frontend
npm ci
cd ..
python -m skytrace.setup_models
python -m skytrace.system_check
```

`system_check` must print `READY` before claiming a live full pipeline is ready. CPU operation is the default. GPU/CUDA is optional; only set a GPU device in configuration after it is actually reported available.

## 3. Prepare data

Provide an authorised single-pass drone video plus GPS/flight metadata in the format accepted by `pipeline.georeferencing`. Do not use `data/test/example.mp4` as an official demo dataset: its provenance is not recorded. Keep raw production data outside Git.

## 4. Configure and run

Review `config/default.yaml`; copy it to a team-specific ignored file if a setting differs. Then run:

```bash
python -m skytrace.run \
  --video /absolute/path/to/flight.mp4 \
  --metadata /absolute/path/to/gps_metadata.json \
  --output results \
  --run-id reproduce-01 \
  --config config/default.yaml
```

Inspect `results/reproduce-01/input_report.json` before trusting downstream results. The complete package contains stage outputs, `logs/pipeline.log`, `logs/errors.log`, `logs/metrics.json`, `checkpoints/`, `pipeline_health.json`, `result_manifest.json`, and JSON/HTML reports.

To resume safely:

```bash
python -m skytrace.run --output results --run-id reproduce-01 --resume
```

The resume operation checks output metadata and required artifacts as well as each checkpoint marker; it does not skip a stage merely because a file exists.

## 5. Start and verify the UI

Terminal 1:

```bash
source .venv/bin/activate
uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`. Run `python -m skytrace.demo_check` to check the pre-processed backup and live API endpoints. The production API exposes `/health` and `/health/dependencies`.

## 6. Docker alternative

```bash
python -m skytrace.setup_models
docker compose up --build
python -m skytrace.demo_check
```

The frontend is `http://localhost:8080`; API is `http://localhost:8000`. The compose path is CPU-first. A GPU installation needs a host NVIDIA runtime, compatible CUDA/PyTorch/COLMAP stack, and a documented validation run; it is not silently selected.

## 7. Evaluation and verification

```bash
pytest
cd frontend && npm test && npm run build && cd ..
python evaluation/run_suite.py --dataset data/evaluation --processed-run outputs/processed-demo
sh scripts/test_e2e.sh
```

`scripts/test_e2e.sh` is an opt-in full live run and fails if critical result-package artifacts are missing. It requires all live prerequisites and an authorised input; it should not be used to misrepresent the test clip as a judging dataset.
