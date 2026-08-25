# SkyTrace Evaluation Dataset Layout

Place PS 26158 robustness inputs under this directory. The runner never
downloads large datasets automatically.

Expected scenario folders:

- `baseline/`
- `motion_blur/`
- `compression/`
- `illumination/`
- `shadows/`
- `dynamic_objects/`
- `gps_noise/`
- `sensor_noise/`
- `limited_view/`
- `occlusion/`
- `no_gcp/`
- `metric_accuracy/`
- `processing_time/`
- `combined_stress/`

Each scenario can include a `manifest.json` with:

```json
{
  "scenario": "motion_blur",
  "single_pass": true,
  "source_video": "../baseline/source.mp4",
  "degradations": [
    {"type": "motion_blur", "level": 1},
    {"type": "motion_blur", "level": 2},
    {"type": "motion_blur", "level": 3}
  ],
  "ground_truth": null,
  "notes": ["Controlled perturbation experiment, not a universal threshold."]
}
```

Metric accuracy needs `ground_truth_measurements.json` at the dataset root and
`analysis/measurements.json` in the processed run.
