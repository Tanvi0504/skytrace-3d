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

Optional ground-truth files unlock additional measured sections:

- `object_labels.json` for object detection precision, recall, and F1.
- `object_positions_3d.json` for Step 5 3D object localization error.
- `surface_completeness.json` for observed/missing surface percentages.

If any of these files are missing, the framework reports `NOT_TESTED`. It does
not fabricate labels, positions, surface areas, or accuracy values.

Run the full Step 8 suite with:

```powershell
python -m evaluation.run_suite --dataset data/evaluation --output evaluation/results --scenario all
```

Generate controlled degraded videos only when you want local artifacts for
manual review or follow-up pipeline runs:

```powershell
python -m evaluation.run_suite --dataset data/evaluation --output evaluation/results --scenario motion_blur --generate-perturbations
```
