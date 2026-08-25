#!/usr/bin/env sh
# Start the supported local Docker deployment. Use scripts/setup.sh first for
# a native environment, model preparation, and dependency diagnostics.
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Desktop/Engine, or follow REPRODUCE.md for native development." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but its daemon is not running. Start Docker Desktop/Engine and retry." >&2
  exit 1
fi

exec docker compose up --build "$@"
