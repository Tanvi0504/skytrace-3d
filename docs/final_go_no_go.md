# Final go / no-go (current repository evidence)

| Category | Status | Evidence / condition |
| --- | --- | --- |
| Functionality | YELLOW | Integrated CLI/API orchestration implemented; full live run not executed in this environment. |
| Reconstruction | YELLOW | Step 2 unit tests and COLMAP integration exist; COLMAP is not installed in the current shell. |
| Georeferencing | YELLOW | Step 3 tests and metadata contracts exist; no real judging GPS run/ground truth is recorded. |
| Object detection | YELLOW | Step 4 has deterministic unit seams; required local YOLO weight is absent until explicit setup. |
| 3D object localization | YELLOW | Conservative Step 5 implementation/tests exist; needs real calibrated demonstration. |
| Measurement | YELLOW | Step 6 measurement/evidence implementation and API exist; no external accuracy validation. |
| Evidence | YELLOW | Evidence grid is functional for the processed UI fixture; it is not accuracy proof. |
| Robustness | YELLOW | Steps 8–9 scenarios/reports exist; several outcomes remain NOT_TESTED without labelled field data. |
| Performance | RED | No measured complete-pipeline benchmark on the actual target machine is checked in. |
| Deployment | YELLOW | Dockerfiles/compose and checks added; fresh Docker build has not been executed here. |
| Demo | RED | Backup viewer works from checked-in fixture, but the required licensed, documented single-pass demo dataset is not present. |
| Documentation | YELLOW | Step 10 documentation exists; update after a fresh-machine and real dataset run. |

**Decision:** do not declare final judging readiness until the RED rows are resolved and the YELLOW rows have current run evidence. The backup viewer may be used only with its visible pre-processed label.
