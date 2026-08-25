# Judge questions — evidence-based answers

| Question | Current answer |
| --- | --- |
| Why single-pass? | The pipeline accepts one chronological flight video and uses sequential reconstruction. This reduces field capture requirements but cannot remove the fundamental limited-view/occlusion constraint. |
| Why not ordinary photogrammetry? | COLMAP remains the reconstruction core. SkyTrace adds video intake, GPS handoff, object/evidence layers, a UI, and run-level traceability; it does not claim to replace photogrammetry. |
| What if the drone is destroyed? | Captured video and flight metadata are the pipeline inputs; processing can begin after recovery. Lost viewpoints cannot be recreated. |
| How accurate is it? | No universal numeric accuracy is claimed. A ground-truth measurement evaluation is required; current evaluation records metric accuracy as not tested where ground truth is absent. |
| How do you know accuracy? | Use matched survey/ground-truth measurements and report MAE/RMSE/median/max through the evaluation tooling. GPS-fit residuals alone are not measurement accuracy. |
| How is GPS noise handled? | Step 3 estimates a robust trajectory-to-GPS alignment and reports residuals/inliers. It does not make GPS error disappear. |
| Dynamic objects? | Step 4 detects/tracks dynamic-capable classes and writes masks. Step 5 warns when triangulation assumptions are weak; it does not infer world motion from tracker IDs alone. |
| Behind buildings / occlusion? | They are not confirmed geometry. The report/evidence layer must mark insufficient observation instead of filling in unseen surfaces. |
| Motion blur / compression / light / shadows? | Step 1 quality filters blur; Steps 8–9 contain controlled robustness scenarios. Full measured degradation evidence is still incomplete where scenario labels/ground truth are absent. |
| How is distance measured? | Between two stored Step 3 ENU points, then Step 6 attaches endpoint and segment support evidence. It is skipped without valid metre-valued georeferencing. |
| What makes a measurement unreliable? | Low point density, weak camera support/diversity, dynamic contamination, and unsupported segments lower the evidence level and generate warnings. |
| What is AI? | The pretrained YOLO detector in Step 4. Frame sharpness, COLMAP reconstruction, GPS alignment, triangulation, and measurement/evidence calculations are classical CV/geometry/statistics. |
| USP? | Single-pass operational packaging with explicit evidence and failure/limitation reporting around an existing photogrammetry workflow. |
| No GCP? | The system can align to available GPS, but no-GCP output is not claimed survey-grade; use external control/ground truth for quantified accuracy. |
| How long does it take? | Use the run's `logs/metrics.json` from the actual target hardware. No current universal or near-real-time claim is made. |
| Edge hardware? | CPU-first operation is configured, but edge suitability is not benchmarked yet. It needs a measured deployment profile. |
| Current limitations? | Demo-video provenance, fresh-machine validation, end-to-end benchmark, and ground-truth accuracy validation remain open; see go/no-go. |
| Government deployment? | Package approved data/weights offline, maintain model/licence and run manifests, deploy a controlled API/storage environment, validate against local survey requirements, and retain human review for low-evidence results. |
