#!/usr/bin/env sh
# Set up a complete local development/runtime environment from a clean clone.
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

SETUP_MODE=${SKYTRACE_SETUP_MODE:-auto}
PYTHON_BIN=${PYTHON_BIN:-python3.11}

if [ "$SETUP_MODE" = "auto" ]; then
  if command -v "$PYTHON_BIN" >/dev/null 2>&1 && command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    SETUP_MODE=native
  elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    SETUP_MODE=docker
  else
    echo "No supported setup runtime was found. Install Python 3.10-3.12 plus Node.js 20-22, or start Docker Desktop and rerun." >&2
    exit 1
  fi
fi

mkdir -p outputs models

if [ "$SETUP_MODE" = "docker" ]; then
  if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    echo "Docker setup requires Docker Desktop/Engine to be installed and running." >&2
    exit 1
  fi
  docker compose build backend frontend
  if [ "${SKYTRACE_DOWNLOAD_MODELS:-1}" = "1" ]; then
    docker run --rm -v "$ROOT_DIR/models:/app/models" --entrypoint python skytrace-3d-backend -m skytrace.setup_models
  else
    echo "Skipping model download (SKYTRACE_DOWNLOAD_MODELS=0). Put vetted weights at models/yolo11n.pt before a live run."
  fi
  docker run --rm -v "$ROOT_DIR/outputs:/app/outputs" -v "$ROOT_DIR/models:/app/models:ro" --entrypoint python skytrace-3d-backend -m skytrace.system_check --backend-only --config config/default.yaml
  echo "Docker setup complete. Start SkyTrace with ./scripts/start.sh"
  exit 0
fi

if [ "$SETUP_MODE" != "native" ]; then
  echo "Unsupported SKYTRACE_SETUP_MODE=$SETUP_MODE. Use auto, native, or docker." >&2
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Missing Python 3.11. Install Python 3.10-3.12, or set PYTHON_BIN to its executable." >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY'
import sys
if not (sys.version_info >= (3, 10) and sys.version_info < (3, 13)):
    raise SystemExit(f"Python {sys.version.split()[0]} is unsupported; SkyTrace requires Python 3.10-3.12.")
PY

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Missing Node.js/npm. Install Node.js 20-22 before running setup." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e .

npm --prefix frontend ci

if [ "${SKYTRACE_DOWNLOAD_MODELS:-1}" = "1" ]; then
  .venv/bin/python -m skytrace.setup_models
else
  echo "Skipping model download (SKYTRACE_DOWNLOAD_MODELS=0). Put vetted weights at models/yolo11n.pt before a live run."
fi

.venv/bin/python -m skytrace.system_check --config config/default.yaml
