# Final test-suite record

| Suite | Command | Current result |
| --- | --- | --- |
| Python unit/API/evaluation tests | `pytest` | Pending Step 10 execution in the configured Python environment. |
| Frontend tests | `cd frontend && npm test` | Pending execution. |
| Frontend production build | `cd frontend && npm run build` | Pending execution. |
| System check | `python -m skytrace.system_check` | Pending execution. |
| Demo check | `python -m skytrace.demo_check` | Pending live services; offline fixture check can run independently. |
| Full pipeline E2E | `sh scripts/test_e2e.sh` | Not run: requires COLMAP, model weights, and authorised live input. |
| Evaluation suite | `python evaluation/run_suite.py --processed-run outputs/processed-demo` | Pending execution. |

Update this record with PASSED / FAILED / SKIPPED and exact environment/run IDs after executing the commands. Do not convert missing prerequisites into passes.
