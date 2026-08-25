# SkyTrace Innovation Notes

This document records only Step 9 claims supported by the checked-in Step 8 report and the current code.

## Implemented and Supported

- Evidence-aware measurement reliability: Step 6 now emits explicit measurement availability states instead of presenting weak-evidence distances as ordinary estimates.
- Processing-time observability: future backend runs preserve per-stage timing in Step 1-6 run summaries so near-real-time claims can be tested instead of assumed.
- Failure-preserving robustness reporting: Step 9 generates failure priorities, before/after comparison rows, and a PS challenge scorecard without converting missing tests into successes.

## Not Claimed

- Survey-grade accuracy is not claimed.
- Real-time or near-real-time performance is not claimed until a rerun records total processing time.
- Occluded or unseen surfaces are not hallucinated as observed geometry.
- Synthetic stress videos are not described as real-world validation.

## Experimental Support

- processing_time_observability: Step 8 could not support a real-time claim because total_processing_time_seconds was null.
- measurement_reliability_status: Step 8 emphasized not returning confident measurements where evidence is weak.

## Remaining Evidence Gaps

- gps_noise: Run controlled GPS perturbation cases and compare absolute georeferencing vs relative geometry.
- limited_view: Add surface-completeness ground truth; improve evidence propagation before geometry inference.
- metric_accuracy: Collect ground_truth_measurements.json and keep low-evidence measurements visibly unreliable.
- compression: Supply the missing Step 8 dataset/ground truth before tuning algorithms.
- dynamic_objects: Add object labels and compare raw vs dynamic-aware reconstruction only when both runs exist.
- illumination: Supply the missing Step 8 dataset/ground truth before tuning algorithms.
- motion_blur: Supply the missing Step 8 dataset/ground truth before tuning algorithms.
- no_gcp: Supply the missing Step 8 dataset/ground truth before tuning algorithms.
- occlusion: Supply occlusion/completeness annotations and preserve observed vs uncertain geometry labels.
- sensor_noise: Supply the missing Step 8 dataset/ground truth before tuning algorithms.
- shadows: Supply the missing Step 8 dataset/ground truth before tuning algorithms.

## PS Scorecard Summary

| PS Challenge | Before | After | Remaining Weakness |
|---|---|---|---|
| Limited viewing angles | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| Motion blur | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| Video compression | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| Variable illumination | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| Shadows | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| Dynamic objects | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| GPS inaccuracies | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| Sensor noise | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| Real-time / near-real-time processing | PARTIAL | PARTIAL | Existing processed-demo lacks measured timings; real-time still cannot be claimed. |
| Occluded surfaces | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| Lack of Ground Control Points | NOT_TESTED | NOT_TESTED | No measured experiment results yet. |
| Metric accuracy | NOT_TESTED | NOT_TESTED | Ground-truth measurements are still required for metric accuracy. |
