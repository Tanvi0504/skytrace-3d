#!/usr/bin/env sh
set -eu

RUN_ID="${SKYTRACE_E2E_RUN_ID:-e2e-$(date +%Y%m%d%H%M%S)}"
python -m skytrace.run \
  --video data/test/example.mp4 \
  --output results \
  --run-id "$RUN_ID" \
  --config config/evaluation.yaml
python -m skytrace.e2e_check --run "results/$RUN_ID"
