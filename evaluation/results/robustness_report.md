# SkyTrace Step 8 Robustness Report

Generated: 2026-08-25T14:14:47.241955+00:00
Dataset: `data\evaluation`

## Dataset Structure

```json
{
  "root": "data\\evaluation",
  "scenario_directories": [
    "baseline",
    "combined_stress",
    "compression",
    "dynamic_objects",
    "gps_noise",
    "illumination",
    "limited_view",
    "metric_accuracy",
    "motion_blur",
    "no_gcp",
    "occlusion",
    "processing_time",
    "sensor_noise",
    "shadows"
  ],
  "created_directories": [],
  "created_manifests": [],
  "downloads_performed": false
}
```

## Baseline

```json
{
  "status": "TESTED",
  "run_id": "processed-demo",
  "run_dir": "outputs\\processed-demo",
  "run_status": {
    "run_id": "processed-demo",
    "state": "COMPLETED",
    "created_at": "2026-08-25T12:00:00+00:00",
    "updated_at": "2026-08-25T12:00:06+00:00",
    "video_filename": "processed-demo.mp4",
    "video_size_bytes": 1048576,
    "error": null,
    "steps": [
      {
        "step": 1,
        "name": "Frame extraction",
        "status": "COMPLETED",
        "summary": {
          "sampled_frames": 24,
          "selected_frames": 12,
          "rejected_frames": 2
        },
        "warnings": [],
        "error": null
      },
      {
        "step": 2,
        "name": "3D reconstruction",
        "status": "COMPLETED",
        "summary": {
          "input_images": 12,
          "registered_images": 10,
          "sparse_points": 9,
          "dense_status": "not_requested_for_demo"
        },
        "warnings": [
          "Processed-demo uses a compact checked-in PLY for UI integration testing."
        ],
        "error": null
      },
      {
        "step": 3,
        "name": "Georeferencing",
        "status": "COMPLETED",
        "summary": {
          "gps_observations": 3,
          "matched_poses": 3,
          "inliers": 3,
          "estimated_scale": 1.0
        },
        "warnings": [],
        "error": null
      },
      {
        "step": 4,
        "name": "Object detection",
        "status": "COMPLETED",
        "summary": {
          "frames_processed": 12,
          "detected_objects": 2,
          "tracks": 2
        },
        "warnings": [],
        "error": null
      },
      {
        "step": 5,
        "name": "3D object association",
        "status": "COMPLETED",
        "summary": {
          "tracks": 2,
          "estimated": 1,
          "low_confidence": 1,
          "unavailable": 0
        },
        "warnings": [],
        "error": null
      },
      {
        "step": 6,
        "name": "Measurement / reliability analysis",
        "status": "COMPLETED",
        "summary": {
          "points": 9,
          "cameras": 3,
          "quality_regions": 2,
          "dynamic_markers": 1
        },
        "warnings": [
          "Evidence scores are reconstruction-support heuristics, not accuracy percentages."
        ],
        "error": null
      }
    ]
  },
  "metrics": {
    "video_duration_seconds": 4.8,
    "input_frames": 24,
    "selected_frames": 12,
    "frame_rejection_rate": 0.08333333333333333,
    "registered_frames": 10,
    "registration_rate": 0.8333333333333334,
    "point_count": 9,
    "detected_objects": 2,
    "objects_3d": 2,
    "object_3d_association_rate": 1.0,
    "quality_regions": 2,
    "dynamic_marker_count": 1,
    "trajectory_rmse_metres": null,
    "total_processing_time_seconds": null,
    "processing_to_video_duration_ratio": null
  },
  "warnings": [
    "Processed-demo uses a compact checked-in PLY for UI integration testing.",
    "Evidence scores are reconstruction-support heuristics, not accuracy percentages.",
    "Processed-demo is a compact checked-in artifact for Step 7 UI integration.",
    "Evidence scores are reconstruction-support heuristics, not accuracy percentages."
  ]
}
```

## PS Requirement Scorecard

| PS Requirement | SkyTrace Component | Test | Result | Status |
|---|---|---|---|---|
| Limited viewing angles | Steps 1-3 and Step 6 evidence | limited_view | No measured experiment results yet. | NOT_TESTED |
| Motion blur | Step 1 frame filtering, Step 2 reconstruction, Step 4 detection | motion_blur | No measured experiment results yet. | NOT_TESTED |
| Video compression | Steps 1, 2, and 4 | compression | No measured experiment results yet. | NOT_TESTED |
| Variable illumination | Steps 1, 2, 4, and 6 | illumination | No measured experiment results yet. | NOT_TESTED |
| Shadows | Steps 1, 2, 4, and 6 | shadows | No measured experiment results yet. | NOT_TESTED |
| Dynamic objects | Steps 4-6 | dynamic_objects | No measured experiment results yet. | NOT_TESTED |
| GPS inaccuracies | Step 3 georeferencing and Step 6 measurement separation | gps_noise | No measured experiment results yet. | NOT_TESTED |
| Sensor noise | Step 2 pose stability and Step 3 metadata use | sensor_noise | No measured experiment results yet. | NOT_TESTED |
| Real-time / near-real-time processing | Steps 1-7 timing metadata | processing_time | Metrics collected. | PARTIAL |
| Occluded surfaces | Step 6 evidence and completeness analysis | occlusion | No measured experiment results yet. | NOT_TESTED |
| Lack of Ground Control Points | Step 3 georeferencing and Step 6 metric analysis | no_gcp | No measured experiment results yet. | NOT_TESTED |
| Metric accuracy | Step 6 and pipeline.evaluation | metric_accuracy | {"reason": "Metric accuracy needs both ground_truth_measurements.json and analysis/measurements.json.", "status": "NOT_TESTED"} | NOT_TESTED |

## Challenge Comparison

| Challenge | Baseline | Degraded | Performance Change | Failure? | Notes |
|---|---|---|---|---|---|
| BASELINE | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {"detected_objects": {"absolute_change": 0, "baseline": 2, "degraded": 2, "percent_change": 0.0}, "dynamic_marker_count": {"absolute_change": 0, "baseline": 1, "degraded": 1, "percent_change": 0.0}, "frame_rejection_rate": {"absolute_change": 0.0, "baseline": 0.08333333333333333, "degraded": 0.08333333333333333, "percent_change": 0.0}, "input_frames": {"absolute_change": 0, "baseline": 24, "degraded": 24, "percent_change": 0.0}, "object_3d_association_rate": {"absolute_change": 0.0, "baseline": 1.0, "degraded": 1.0, "percent_change": 0.0}, "objects_3d": {"absolute_change": 0, "baseline": 2, "degraded": 2, "percent_change": 0.0}, "point_count": {"absolute_change": 0, "baseline": 9, "degraded": 9, "percent_change": 0.0}, "quality_regions": {"absolute_change": 0, "baseline": 2, "degraded": 2, "percent_change": 0.0}, "registered_frames": {"absolute_change": 0, "baseline": 10, "degraded": 10, "percent_change": 0.0}, "registration_rate": {"absolute_change": 0.0, "baseline": 0.8333333333333334, "degraded": 0.8333333333333334, "percent_change": 0.0}, "selected_frames": {"absolute_change": 0, "baseline": 12, "degraded": 12, "percent_change": 0.0}, "video_duration_seconds": {"absolute_change": 0.0, "baseline": 4.8, "degraded": 4.8, "percent_change": 0.0}} | None | ["Baseline collected from existing processed run; no rerun was required."] |
| MOTION BLUR | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| COMPRESSION | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| VARIABLE ILLUMINATION | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| SHADOWS | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| DYNAMIC OBJECTS | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| GPS NOISE | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| SENSOR NOISE | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| LIMITED VIEW | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| OCCLUSION | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| NO-GCP | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| METRIC ACCURACY | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |
| PROCESSING TIME | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "real_time_assessment": "Processing time was not recorded; no real-time claim is supported.", "real_time_claim_supported": false, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {"detected_objects": {"absolute_change": 0, "baseline": 2, "degraded": 2, "percent_change": 0.0}, "dynamic_marker_count": {"absolute_change": 0, "baseline": 1, "degraded": 1, "percent_change": 0.0}, "frame_rejection_rate": {"absolute_change": 0.0, "baseline": 0.08333333333333333, "degraded": 0.08333333333333333, "percent_change": 0.0}, "input_frames": {"absolute_change": 0, "baseline": 24, "degraded": 24, "percent_change": 0.0}, "object_3d_association_rate": {"absolute_change": 0.0, "baseline": 1.0, "degraded": 1.0, "percent_change": 0.0}, "objects_3d": {"absolute_change": 0, "baseline": 2, "degraded": 2, "percent_change": 0.0}, "point_count": {"absolute_change": 0, "baseline": 9, "degraded": 9, "percent_change": 0.0}, "quality_regions": {"absolute_change": 0, "baseline": 2, "degraded": 2, "percent_change": 0.0}, "registered_frames": {"absolute_change": 0, "baseline": 10, "degraded": 10, "percent_change": 0.0}, "registration_rate": {"absolute_change": 0.0, "baseline": 0.8333333333333334, "degraded": 0.8333333333333334, "percent_change": 0.0}, "selected_frames": {"absolute_change": 0, "baseline": 12, "degraded": 12, "percent_change": 0.0}, "video_duration_seconds": {"absolute_change": 0.0, "baseline": 4.8, "degraded": 4.8, "percent_change": 0.0}} | None | [] |
| COMBINED STRESS | {"detected_objects": 2, "dynamic_marker_count": 1, "frame_rejection_rate": 0.08333333333333333, "input_frames": 24, "object_3d_association_rate": 1.0, "objects_3d": 2, "point_count": 9, "processing_to_video_duration_ratio": null, "quality_regions": 2, "registered_frames": 10, "registration_rate": 0.8333333333333334, "selected_frames": 12, "total_processing_time_seconds": null, "trajectory_rmse_metres": null, "video_duration_seconds": 4.8} | {} | {} | None | ["Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.", "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."] |

## Scenario Results

### BASELINE

```json
{
  "run_id": "baseline-20260825T141442Z",
  "scenario": "baseline",
  "label": "BASELINE",
  "status": "TESTED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "baseline",
    "timestamp": "2026-08-25T14:14:42.707750+00:00",
    "source_video": "../../test/example.mp4",
    "video_duration_seconds": 4.8,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": null,
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {
      "video_duration_seconds": 4.8,
      "input_frames": 24,
      "selected_frames": 12,
      "frame_rejection_rate": 0.08333333333333333,
      "registered_frames": 10,
      "registration_rate": 0.8333333333333334,
      "point_count": 9,
      "detected_objects": 2,
      "objects_3d": 2,
      "object_3d_association_rate": 1.0,
      "quality_regions": 2,
      "dynamic_marker_count": 1,
      "trajectory_rmse_metres": null,
      "total_processing_time_seconds": null,
      "processing_to_video_duration_ratio": null
    }
  },
  "manifest": {
    "scenario": "baseline",
    "single_pass": true,
    "source_video": "../../test/example.mp4",
    "processed_run": "../../../outputs/processed-demo",
    "notes": [
      "Baseline collection can use an existing processed run for reproducible Step 8 reporting.",
      "Full reconstruction reruns are intentionally not automatic unless a user executes the pipeline separately."
    ]
  },
  "metrics": {
    "video_duration_seconds": 4.8,
    "input_frames": 24,
    "selected_frames": 12,
    "frame_rejection_rate": 0.08333333333333333,
    "registered_frames": 10,
    "registration_rate": 0.8333333333333334,
    "point_count": 9,
    "detected_objects": 2,
    "objects_3d": 2,
    "object_3d_association_rate": 1.0,
    "quality_regions": 2,
    "dynamic_marker_count": 1,
    "trajectory_rmse_metres": null,
    "total_processing_time_seconds": null,
    "processing_to_video_duration_ratio": null
  },
  "failure": null,
  "generated_artifacts": [],
  "summary": "Metrics collected.",
  "notes": [
    "Baseline collected from existing processed run; no rerun was required."
  ],
  "evaluation_time_seconds": 0.0574
}
```

### MOTION BLUR

```json
{
  "run_id": "motion_blur-20260825T141443Z",
  "scenario": "motion_blur",
  "label": "MOTION BLUR",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "motion_blur",
    "timestamp": "2026-08-25T14:14:43.499082+00:00",
    "source_video": "../baseline/../../test/example.mp4",
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": [
      {
        "type": "motion_blur",
        "level": 0
      },
      {
        "type": "motion_blur",
        "level": 1
      },
      {
        "type": "motion_blur",
        "level": 2
      },
      {
        "type": "motion_blur",
        "level": 3
      }
    ],
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "motion_blur",
    "single_pass": true,
    "source_video": "../baseline/../../test/example.mp4",
    "degradations": [
      {
        "type": "motion_blur",
        "level": 0
      },
      {
        "type": "motion_blur",
        "level": 1
      },
      {
        "type": "motion_blur",
        "level": 2
      },
      {
        "type": "motion_blur",
        "level": 3
      }
    ],
    "notes": [
      "Controlled blur levels are relative stress cases, not universal thresholds."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "degradation": "motion_blur",
      "level": 0,
      "source": "data\\evaluation\\motion_blur\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\motion_blur\\motion_blur_level_0.mp4"
    },
    {
      "degradation": "motion_blur",
      "level": 1,
      "source": "data\\evaluation\\motion_blur\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\motion_blur\\motion_blur_level_1.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    },
    {
      "degradation": "motion_blur",
      "level": 2,
      "source": "data\\evaluation\\motion_blur\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\motion_blur\\motion_blur_level_2.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    },
    {
      "degradation": "motion_blur",
      "level": 3,
      "source": "data\\evaluation\\motion_blur\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\motion_blur\\motion_blur_level_3.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.7823
}
```

### COMPRESSION

```json
{
  "run_id": "compression-20260825T141443Z",
  "scenario": "compression",
  "label": "COMPRESSION",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "compression",
    "timestamp": "2026-08-25T14:14:43.878618+00:00",
    "source_video": "../baseline/../../test/example.mp4",
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": [
      {
        "type": "compression",
        "level": 0,
        "jpeg_quality": 95
      },
      {
        "type": "compression",
        "level": 1,
        "jpeg_quality": 85
      },
      {
        "type": "compression",
        "level": 2,
        "jpeg_quality": 55
      },
      {
        "type": "compression",
        "level": 3,
        "jpeg_quality": 30
      }
    ],
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "compression",
    "single_pass": true,
    "source_video": "../baseline/../../test/example.mp4",
    "degradations": [
      {
        "type": "compression",
        "level": 0,
        "jpeg_quality": 95
      },
      {
        "type": "compression",
        "level": 1,
        "jpeg_quality": 85
      },
      {
        "type": "compression",
        "level": 2,
        "jpeg_quality": 55
      },
      {
        "type": "compression",
        "level": 3,
        "jpeg_quality": 30
      }
    ],
    "notes": [
      "Records codec, resolution, and JPEG quality used for the controlled copy."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "degradation": "compression",
      "level": 0,
      "source": "data\\evaluation\\compression\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\compression\\compression_level_0.mp4"
    },
    {
      "degradation": "compression",
      "level": 1,
      "source": "data\\evaluation\\compression\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\compression\\compression_level_1.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": 85
    },
    {
      "degradation": "compression",
      "level": 2,
      "source": "data\\evaluation\\compression\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\compression\\compression_level_2.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": 55
    },
    {
      "degradation": "compression",
      "level": 3,
      "source": "data\\evaluation\\compression\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\compression\\compression_level_3.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": 30
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.3789
}
```

### VARIABLE ILLUMINATION

```json
{
  "run_id": "illumination-20260825T141445Z",
  "scenario": "illumination",
  "label": "VARIABLE ILLUMINATION",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "illumination",
    "timestamp": "2026-08-25T14:14:45.148278+00:00",
    "source_video": "../baseline/../../test/example.mp4",
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": [
      {
        "type": "dark",
        "level": 1
      },
      {
        "type": "dark",
        "level": 3
      },
      {
        "type": "bright",
        "level": 1
      },
      {
        "type": "contrast",
        "level": 2
      }
    ],
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "illumination",
    "single_pass": true,
    "source_video": "../baseline/../../test/example.mp4",
    "degradations": [
      {
        "type": "dark",
        "level": 1
      },
      {
        "type": "dark",
        "level": 3
      },
      {
        "type": "bright",
        "level": 1
      },
      {
        "type": "contrast",
        "level": 2
      }
    ],
    "notes": [
      "No image enhancement is applied before scoring unless it is part of SkyTrace itself."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "degradation": "dark",
      "level": 1,
      "source": "data\\evaluation\\illumination\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\illumination\\dark_level_1.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    },
    {
      "degradation": "dark",
      "level": 3,
      "source": "data\\evaluation\\illumination\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\illumination\\dark_level_3.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    },
    {
      "degradation": "bright",
      "level": 1,
      "source": "data\\evaluation\\illumination\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\illumination\\bright_level_1.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    },
    {
      "degradation": "contrast",
      "level": 2,
      "source": "data\\evaluation\\illumination\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\illumination\\contrast_level_2.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 1.2718
}
```

### SHADOWS

```json
{
  "run_id": "shadows-20260825T141446Z",
  "scenario": "shadows",
  "label": "SHADOWS",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "shadows",
    "timestamp": "2026-08-25T14:14:46.491884+00:00",
    "source_video": "../baseline/../../test/example.mp4",
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": [
      {
        "type": "shadow",
        "level": 1
      },
      {
        "type": "shadow",
        "level": 2
      },
      {
        "type": "shadow",
        "level": 3
      }
    ],
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "shadows",
    "single_pass": true,
    "source_video": "../baseline/../../test/example.mp4",
    "degradations": [
      {
        "type": "shadow",
        "level": 1
      },
      {
        "type": "shadow",
        "level": 2
      },
      {
        "type": "shadow",
        "level": 3
      }
    ],
    "notes": [
      "Synthetic shadows mark a controlled occluding illumination stress, not a physical lighting model."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "degradation": "shadow",
      "level": 1,
      "source": "data\\evaluation\\shadows\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\shadows\\shadow_level_1.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    },
    {
      "degradation": "shadow",
      "level": 2,
      "source": "data\\evaluation\\shadows\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\shadows\\shadow_level_2.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    },
    {
      "degradation": "shadow",
      "level": 3,
      "source": "data\\evaluation\\shadows\\..\\baseline\\..\\..\\test\\example.mp4",
      "output": "evaluation\\results\\shadows\\shadow_level_3.mp4",
      "frames_written": 90,
      "codec": "mp4v",
      "fps": 30.0,
      "resolution": [
        320,
        240
      ],
      "jpeg_quality": null
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 1.3446
}
```

### DYNAMIC OBJECTS

```json
{
  "run_id": "dynamic_objects-20260825T141446Z",
  "scenario": "dynamic_objects",
  "label": "DYNAMIC OBJECTS",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "dynamic_objects",
    "timestamp": "2026-08-25T14:14:46.543365+00:00",
    "source_video": null,
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": null,
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "dynamic_objects",
    "single_pass": true,
    "required_scene_content": [
      "people",
      "cars",
      "trucks",
      "animals",
      "moving objects"
    ],
    "comparisons": [
      "raw_reconstruction",
      "dynamic_object_aware_reconstruction"
    ],
    "notes": [
      "Precision/recall remain NOT_TESTED until object labels are supplied."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "error": "source_video not found: data\\evaluation\\dynamic_objects"
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.0705
}
```

### GPS NOISE

```json
{
  "run_id": "gps_noise-20260825T141446Z",
  "scenario": "gps_noise",
  "label": "GPS NOISE",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "gps_noise",
    "timestamp": "2026-08-25T14:14:46.613488+00:00",
    "source_video": null,
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": [
      0,
      1,
      5,
      10,
      20,
      50
    ],
    "gps_perturbation": [
      0,
      1,
      5,
      10,
      20,
      50
    ],
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "gps_noise",
    "single_pass": true,
    "gps_noise_levels_metres": [
      0,
      1,
      5,
      10,
      20,
      50
    ],
    "notes": [
      "Controlled perturbations are not real GPS distributions; relative and absolute accuracy are separate."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "error": "source_video not found: data\\evaluation\\gps_noise"
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.0841
}
```

### SENSOR NOISE

```json
{
  "run_id": "sensor_noise-20260825T141446Z",
  "scenario": "sensor_noise",
  "label": "SENSOR NOISE",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "sensor_noise",
    "timestamp": "2026-08-25T14:14:46.697914+00:00",
    "source_video": null,
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": null,
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "sensor_noise",
    "single_pass": true,
    "imu_required": false,
    "notes": [
      "If IMU metadata is unavailable, the report must say NOT_TESTED instead of fabricating sensor data."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "error": "source_video not found: data\\evaluation\\sensor_noise"
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.0803
}
```

### LIMITED VIEW

```json
{
  "run_id": "limited_view-20260825T141446Z",
  "scenario": "limited_view",
  "label": "LIMITED VIEW",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "limited_view",
    "timestamp": "2026-08-25T14:14:46.778178+00:00",
    "source_video": null,
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": null,
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "limited_view",
    "single_pass": true,
    "view_rule": "one_continuous_flight_path_only",
    "surface_classes": [
      "directly_observed",
      "weakly_observed",
      "unseen"
    ],
    "notes": [
      "Unseen geometry must not receive the same confidence as directly observed surfaces."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "error": "source_video not found: data\\evaluation\\limited_view"
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.0784
}
```

### OCCLUSION

```json
{
  "run_id": "occlusion-20260825T141446Z",
  "scenario": "occlusion",
  "label": "OCCLUSION",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "occlusion",
    "timestamp": "2026-08-25T14:14:46.856332+00:00",
    "source_video": null,
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": null,
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "occlusion",
    "single_pass": true,
    "occluders": [
      "trees",
      "vehicles",
      "structures",
      "partially hidden objects"
    ],
    "notes": [
      "Observed surfaces must remain separate from inferred or uncertain regions."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "error": "source_video not found: data\\evaluation\\occlusion"
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.0771
}
```

### NO-GCP

```json
{
  "run_id": "no_gcp-20260825T141446Z",
  "scenario": "no_gcp",
  "label": "NO-GCP",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "no_gcp",
    "timestamp": "2026-08-25T14:14:46.933823+00:00",
    "source_video": null,
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": null,
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "no_gcp",
    "single_pass": true,
    "cases": [
      "no_gcp",
      "minimal_control_if_available",
      "higher_quality_reference_if_available"
    ],
    "notes": [
      "Zero-GCP reconstruction is quantified, not described as survey-grade."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "error": "source_video not found: data\\evaluation\\no_gcp"
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.0672
}
```

### METRIC ACCURACY

```json
{
  "run_id": "metric_accuracy-20260825T141447Z",
  "scenario": "metric_accuracy",
  "label": "METRIC ACCURACY",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "metric_accuracy",
    "timestamp": "2026-08-25T14:14:47.000739+00:00",
    "source_video": null,
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": null,
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "metric_accuracy",
    "single_pass": true,
    "requires": [
      "ground_truth_measurements.json",
      "processed_run/analysis/measurements.json"
    ],
    "notes": [
      "Reports MAE, RMSE, median, maximum, absolute, and relative errors across matched measurements."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "error": "source_video not found: data\\evaluation\\metric_accuracy"
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.0813
}
```

### PROCESSING TIME

```json
{
  "run_id": "processing_time-20260825T141447Z",
  "scenario": "processing_time",
  "label": "PROCESSING TIME",
  "status": "TESTED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "processing_time",
    "timestamp": "2026-08-25T14:14:47.082240+00:00",
    "source_video": null,
    "video_duration_seconds": 4.8,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": null,
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {
      "video_duration_seconds": 4.8,
      "input_frames": 24,
      "selected_frames": 12,
      "frame_rejection_rate": 0.08333333333333333,
      "registered_frames": 10,
      "registration_rate": 0.8333333333333334,
      "point_count": 9,
      "detected_objects": 2,
      "objects_3d": 2,
      "object_3d_association_rate": 1.0,
      "quality_regions": 2,
      "dynamic_marker_count": 1,
      "trajectory_rmse_metres": null,
      "total_processing_time_seconds": null,
      "processing_to_video_duration_ratio": null,
      "real_time_claim_supported": false,
      "real_time_assessment": "Processing time was not recorded; no real-time claim is supported."
    }
  },
  "manifest": {
    "scenario": "processing_time",
    "single_pass": true,
    "stages": [
      "frame_extraction",
      "reconstruction",
      "georeferencing",
      "object_detection",
      "object_3d_association",
      "analysis",
      "total"
    ],
    "notes": [
      "Real-time is supported only when measured processing time is not longer than video duration."
    ]
  },
  "metrics": {
    "video_duration_seconds": 4.8,
    "input_frames": 24,
    "selected_frames": 12,
    "frame_rejection_rate": 0.08333333333333333,
    "registered_frames": 10,
    "registration_rate": 0.8333333333333334,
    "point_count": 9,
    "detected_objects": 2,
    "objects_3d": 2,
    "object_3d_association_rate": 1.0,
    "quality_regions": 2,
    "dynamic_marker_count": 1,
    "trajectory_rmse_metres": null,
    "total_processing_time_seconds": null,
    "processing_to_video_duration_ratio": null,
    "real_time_claim_supported": false,
    "real_time_assessment": "Processing time was not recorded; no real-time claim is supported."
  },
  "failure": null,
  "generated_artifacts": [],
  "summary": "Metrics collected.",
  "notes": [],
  "evaluation_time_seconds": 0.0786
}
```

### COMBINED STRESS

```json
{
  "run_id": "combined_stress-20260825T141447Z",
  "scenario": "combined_stress",
  "label": "COMBINED STRESS",
  "status": "REGISTERED",
  "single_pass": true,
  "reproducibility": {
    "scenario": "combined_stress",
    "timestamp": "2026-08-25T14:14:47.160785+00:00",
    "source_video": null,
    "video_duration_seconds": null,
    "resolution": null,
    "frame_rate": null,
    "degradation_parameters": [
      [
        "motion_blur",
        "compression"
      ],
      [
        "motion_blur",
        "gps_noise"
      ],
      [
        "occlusion",
        "dynamic_objects"
      ],
      [
        "illumination",
        "compression"
      ],
      [
        "motion_blur",
        "gps_noise",
        "dynamic_objects",
        "occlusion"
      ]
    ],
    "gps_perturbation": null,
    "processing_configuration": {
      "processed_run": "outputs\\processed-demo"
    },
    "software_version": {
      "python": "3.14.0",
      "git_commit": "4a90c16"
    },
    "output_metrics": {}
  },
  "manifest": {
    "scenario": "combined_stress",
    "single_pass": true,
    "scenarios": [
      [
        "motion_blur",
        "compression"
      ],
      [
        "motion_blur",
        "gps_noise"
      ],
      [
        "occlusion",
        "dynamic_objects"
      ],
      [
        "illumination",
        "compression"
      ],
      [
        "motion_blur",
        "gps_noise",
        "dynamic_objects",
        "occlusion"
      ]
    ],
    "notes": [
      "Combined stress exists to expose break points, not to manufacture success."
    ]
  },
  "metrics": {},
  "failure": null,
  "generated_artifacts": [
    {
      "error": "source_video not found: data\\evaluation\\combined_stress"
    }
  ],
  "summary": "No measured experiment results yet.",
  "notes": [
    "Scenario manifest found. Full pipeline execution is intentionally not automatic in Step 8 MVP.",
    "Controlled degraded videos were generated; run them through SkyTrace before interpreting accuracy."
  ],
  "evaluation_time_seconds": 0.0809
}
```

## Object Detection Performance

```json
{
  "status": "NOT_TESTED",
  "reason": "Object detection needs object_labels.json and scene_objects/objects_3d.json."
}
```

## 3D Object Localization

```json
{
  "status": "NOT_TESTED",
  "reason": "3D object localization needs object_positions_3d.json and scene_objects/objects_3d.json."
}
```

## 3D Completeness

```json
{
  "status": "NOT_TESTED",
  "reason": "3D completeness needs surface_completeness.json with observed/reference surface areas."
}
```

## Metric Accuracy

```json
{
  "status": "NOT_TESTED",
  "reason": "Metric accuracy needs both ground_truth_measurements.json and analysis/measurements.json."
}
```

## Evidence Score Validation

```json
{
  "status": "NOT_TESTED",
  "reason": "Evidence validation requires measurement predictions and ground truth."
}
```

## Failure Analysis

```json
{
  "FRAME_QUALITY_FAILURE": {
    "stage": "STEP_1",
    "severity": "high",
    "possible_mitigation": "Increase image quality, lower blur, or adjust frame-selection threshold."
  },
  "INSUFFICIENT_FEATURE_MATCHES": {
    "stage": "STEP_2",
    "severity": "high",
    "possible_mitigation": "Improve overlap, reduce blur/compression, or use more textured views."
  },
  "CAMERA_POSE_FAILURE": {
    "stage": "STEP_2",
    "severity": "critical",
    "possible_mitigation": "Collect a smoother single pass with stronger overlap and more stable exposure."
  },
  "RECONSTRUCTION_SPARSE": {
    "stage": "STEP_2",
    "severity": "medium",
    "possible_mitigation": "Increase usable frames or improve feature support before dense reconstruction."
  },
  "GEOREFERENCE_FAILURE": {
    "stage": "STEP_3",
    "severity": "high",
    "possible_mitigation": "Provide usable GPS metadata or better timestamp correspondence."
  },
  "OBJECT_DETECTION_FAILURE": {
    "stage": "STEP_4",
    "severity": "medium",
    "possible_mitigation": "Check detector model/classes and image quality."
  },
  "OBJECT_3D_ASSOCIATION_FAILURE": {
    "stage": "STEP_5",
    "severity": "medium",
    "possible_mitigation": "Improve calibrated multi-view support for tracked objects."
  },
  "INSUFFICIENT_GEOMETRY": {
    "stage": "STEP_6",
    "severity": "high",
    "possible_mitigation": "Avoid measuring weakly reconstructed or unseen regions."
  },
  "MEASUREMENT_LOW_EVIDENCE": {
    "stage": "STEP_6",
    "severity": "medium",
    "possible_mitigation": "Use endpoints with higher reconstruction support or collect better views."
  },
  "DYNAMIC_OBJECT_CONTAMINATION": {
    "stage": "STEP_4_STEP_6",
    "severity": "medium",
    "possible_mitigation": "Mask dynamic candidates and compare raw vs dynamic-aware reconstruction."
  },
  "OCCLUSION": {
    "stage": "DATASET",
    "severity": "medium",
    "possible_mitigation": "Report occluded surfaces as low evidence; do not infer hidden geometry."
  },
  "PROCESSING_TIMEOUT": {
    "stage": "PIPELINE",
    "severity": "high",
    "possible_mitigation": "Profile stages, downsample for evaluation, or set explicit time budgets."
  },
  "UNKNOWN": {
    "stage": "UNKNOWN",
    "severity": "unknown",
    "possible_mitigation": "Inspect logs and add a more specific classifier rule."
  }
}
```

## Visual Outputs

```json
[
  {
    "scenario": "motion_blur",
    "type": "degraded_video",
    "path": "evaluation\\results\\motion_blur\\motion_blur_level_0.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "motion_blur",
    "type": "degraded_video",
    "path": "evaluation\\results\\motion_blur\\motion_blur_level_1.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "motion_blur",
    "type": "degraded_video",
    "path": "evaluation\\results\\motion_blur\\motion_blur_level_2.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "motion_blur",
    "type": "degraded_video",
    "path": "evaluation\\results\\motion_blur\\motion_blur_level_3.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "compression",
    "type": "degraded_video",
    "path": "evaluation\\results\\compression\\compression_level_0.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "compression",
    "type": "degraded_video",
    "path": "evaluation\\results\\compression\\compression_level_1.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "compression",
    "type": "degraded_video",
    "path": "evaluation\\results\\compression\\compression_level_2.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "compression",
    "type": "degraded_video",
    "path": "evaluation\\results\\compression\\compression_level_3.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "illumination",
    "type": "degraded_video",
    "path": "evaluation\\results\\illumination\\dark_level_1.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "illumination",
    "type": "degraded_video",
    "path": "evaluation\\results\\illumination\\dark_level_3.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "illumination",
    "type": "degraded_video",
    "path": "evaluation\\results\\illumination\\bright_level_1.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "illumination",
    "type": "degraded_video",
    "path": "evaluation\\results\\illumination\\contrast_level_2.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "shadows",
    "type": "degraded_video",
    "path": "evaluation\\results\\shadows\\shadow_level_1.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "shadows",
    "type": "degraded_video",
    "path": "evaluation\\results\\shadows\\shadow_level_2.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "scenario": "shadows",
    "type": "degraded_video",
    "path": "evaluation\\results\\shadows\\shadow_level_3.mp4",
    "honesty_note": "Generated artifact for side-by-side review; not an accuracy claim."
  },
  {
    "type": "original_vs_degraded_frame",
    "status": "NOT_GENERATED",
    "reason": "Requires measured degraded runs or ground truth artifacts."
  },
  {
    "type": "original_vs_degraded_reconstruction",
    "status": "NOT_GENERATED",
    "reason": "Requires measured degraded runs or ground truth artifacts."
  },
  {
    "type": "object_detection_comparison",
    "status": "NOT_GENERATED",
    "reason": "Requires measured degraded runs or ground truth artifacts."
  },
  {
    "type": "evidence_map",
    "status": "NOT_GENERATED",
    "reason": "Requires measured degraded runs or ground truth artifacts."
  },
  {
    "type": "ground_truth_vs_estimated_measurement",
    "status": "NOT_GENERATED",
    "reason": "Requires measured degraded runs or ground truth artifacts."
  },
  {
    "type": "gps_perturbation_vs_georeferencing_error",
    "status": "NOT_GENERATED",
    "reason": "Requires measured degraded runs or ground truth artifacts."
  },
  {
    "type": "performance_degradation_curves",
    "status": "NOT_GENERATED",
    "reason": "Requires measured degraded runs or ground truth artifacts."
  }
]
```

## Online vs Offline

```json
{
  "online_candidates": [
    "frame extraction",
    "frame quality scoring",
    "object detection on decoded frames"
  ],
  "offline_required": [
    "global reconstruction",
    "final georeferencing",
    "final metric/evidence analysis"
  ],
  "note": "This is an architectural assessment only; no streaming rewrite was performed in Step 8."
}
```
