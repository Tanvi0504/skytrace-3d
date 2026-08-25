# SkyTrace — Step 6: 3D Measurement & Reconstruction Reliability

Location: `pipeline/analysis/` and `pipeline/evaluation/`  
Tests: `tests/analysis/` and `tests/evaluation/`

Step 6 measures only in the metre-valued coordinate system published by Step 3
and attaches transparent reconstruction-support evidence to every result. It
does not modify Steps 1–5, re-estimate georeferencing, alter the point cloud,
claim survey accuracy, or use its evidence score as an accuracy percentage.

## Flow

```text
Step 3 ENU point cloud + camera trajectory + optional Step 5 dynamic markers
                                  |
                                  v
              local evidence grid and endpoint/segment checks
                                  |
user-supplied ENU coordinates ---> 3D / horizontal / vertical measurement
                                  |
                                  v
                 value + evidence level + explicit limitations
```

## Inputs

```text
outputs/<run_id>/georeferenced/
├── point_cloud_georef.ply
├── camera_trajectory_georef.csv
└── transform.json

outputs/<run_id>/scene_objects/     # optional
└── objects_3d.json
```

`transform.json` must declare metre units. The current Step 3 output is local
East-North-Up (ENU), metres, so it provides meaningful horizontal East/North
axes and an Up coordinate. Without a metre declaration, Step 6 declines metric
analysis. Missing camera trajectory or Step 5 data is handled as unavailable
evidence with a warning; it does not invent a replacement signal.

The PLY reader supports the existing Step 3 ASCII and little-endian binary PLY
formats and reads coordinates without copying the point cloud. Step 6 does not
assume the PLY has per-point tracks, frame visibility, feature matches, or
reprojection errors because Step 2/3 do not currently export those fields.

## Measurement methodology

For points `A = (x1, y1, z1)` and `B = (x2, y2, z2)`, calculations stay in
metres internally:

```text
3D distance         = √((x2-x1)² + (y2-y1)² + (z2-z1)²)
horizontal distance = √((x2-x1)² + (y2-y1)²)
vertical difference = |z2-z1|
```

The three values are deliberately separate. `m`, `cm`, and `km` are display
conversions only, so conversion does not reduce calculation precision. A
non-ENU target can still return a 3D metric distance, but horizontal and
vertical values are unavailable rather than assumed.

Vertical values use Step 3's local ENU Up coordinate. They inherit the
limitations of its reconstruction-to-GPS alignment and GPS altitude reference;
they are not survey-grade heights or a claim about a vertical datum.

## Evidence methodology

`calculate_evidence(point, scene, config)` uses only these available signals:

| Signal | Normalisation | Default weight | Limitation |
|---|---|---:|---|
| Local reconstruction density | PLY vertices within 3 m, capped at 20 | 0.50 | Dense points do not prove accuracy. |
| Nearby camera support | Step 3 camera centres within 80 m, capped at 4 | 0.25 | Camera proximity does not verify surface visibility. |
| Nearby camera diversity | Largest pairwise candidate-camera angle, capped at 30° | 0.25 | Does not know orientation, occlusion, or per-point observation. |
| Dynamic contamination | Step 5 dynamic marker count within 3 m, capped at 1 | bounded 0.25 penalty | It reduces support; it does not declare the region invalid. |

The three positive weights are normalised to sum to one. The transparent score
is:

```text
weighted_sum(density, nearby camera support, nearby camera diversity)
× (1 - dynamic_penalty × normalized_dynamic_contamination)
```

The defaults are configurable engineering heuristics, not scientifically
validated weights. `quality_metadata.json` writes the exact effective
normalisation, weights, thresholds, and unavailable signals for each run.

Signals intentionally not fabricated are: source-frame observation count,
feature-match density, per-point reprojection error, depth consistency,
occlusion, supporting image quality, and direct-vs-inferred surface state.
Consequently, every local result has `direct_observation_status: "UNKNOWN"`.
Future Step 2 visibility-track exports can populate this independently without
changing distance calculations.

### Evidence levels

The default configurable levels are:

| Score | Level |
|---:|---|
| ≥ 0.75 | `HIGH` |
| ≥ 0.50 | `MEDIUM` |
| ≥ 0.25 | `LOW` |
| < 0.25 | `INSUFFICIENT` |

A scene measurement uses the lower endpoint score, never the higher one. If
intermediate points have sufficient local PLY support, the segment's minimum
score also bounds the result. If intermediate geometry is absent (for example,
the distance crosses open air), endpoint evidence remains usable but the output
states that the segment was not independently supported. `INSUFFICIENT` emits
the calculated number only with `measurement_status:
"INSUFFICIENT_EVIDENCE"` and a `not recommended` warning.

## Outputs

```text
outputs/<run_id>/analysis/
├── measurements.json
├── evidence_map/
│   └── quality_grid.json
└── quality_metadata.json
```

- `measurements.json` contains each requested 3D/horizontal/vertical value in
  its selected display unit and raw metres, endpoint evidence, optional segment
  evidence, status, and warnings.
- `evidence_map/quality_grid.json` is a compact voxel-region summary pointing
  to the source PLY; it does not duplicate vertices. Its requested 5 m cell
  size automatically grows only if needed to stay below the configured 10,000
  region bound, and records the effective size.
- `quality_metadata.json` records the inputs, timing, exact configuration,
  score formula, signal limitations, and vertical-reference limitation.

### `measurements.json` request schema

```json
{
  "measurements": [
    {
      "measurement_id": "road_width_1",
      "point_a": [100.0, 200.0, 5.0],
      "point_b": [108.2, 200.1, 5.1],
      "unit": "m"
    }
  ]
}
```

## CLI

Analyse a scene and one inline measurement:

```bash
python3 -m pipeline.analysis \
  --scene outputs/example/georeferenced \
  --objects outputs/example/scene_objects \
  --output outputs/example/analysis \
  --point-a 100.0 200.0 5.0 \
  --point-b 108.2 200.1 5.1 \
  --unit m
```

Use `--measurements data/test/measurement_requests.json` for a batch. All
normalisation values, weights, thresholds, grid size, and segment sample count
are CLI controls; run `python3 -m pipeline.analysis --help` for the exact list.
The output directory is isolated and requires `--overwrite` to replace a
non-empty previous run.

## Python API

```python
import numpy as np
from pathlib import Path

from pipeline.analysis import (
    EvidenceConfig,
    MeasurementRequest,
    analyze_georeferenced_scene,
    calculate_evidence,
    load_scene_context,
    measure_distance,
)

# Pure calculation; no scene or evidence is implied.
raw = measure_distance([0, 0, 0], [3, 4, 0], unit="m")
assert raw.distance_3d_metres == 5.0

# Reusable local-evidence query.
scene = load_scene_context(
    Path("outputs/example/georeferenced"), None, EvidenceConfig()
)
evidence = calculate_evidence(np.array([100.0, 200.0, 5.0]), scene)

# Scene-aware measurement and evidence map.
result = analyze_georeferenced_scene(
    scene_dir="outputs/example/georeferenced",
    scene_objects_dir="outputs/example/scene_objects",
    output_dir="outputs/example/analysis",
    measurements=[
        MeasurementRequest(
            "road_width_1",
            np.array([100.0, 200.0, 5.0]),
            np.array([108.2, 200.1, 5.1]),
            "m",
        )
    ],
    evidence_config=EvidenceConfig(),
)
```

## Ground-truth measurement evaluation

Evidence support, measured error, and Step 3 GPS alignment residual are kept
separate. The evaluation command compares `measurements.json` with known
distances by `measurement_id`:

```json
{
  "measurements": [
    {
      "measurement_id": "road_width_1",
      "distance_m": 8.2
    }
  ]
}
```

Ground truth can instead provide `point_a` and `point_b`; their Euclidean
distance is calculated in metres. Run:

```bash
python3 -m pipeline.evaluation \
  --predictions outputs/example/analysis/measurements.json \
  --ground-truth data/test/ground_truth.json \
  --output outputs/example/analysis_evaluation
```

`evaluation.json` records each matched comparison and mean absolute error,
median absolute error, RMSE, mean percentage error (excluding zero-valued
ground truth), and worst-case absolute error. These are validation metrics,
not an evidence score or a GPS/georeferencing error.

## Dependencies and validation

No dependencies were added. Step 6 uses the existing NumPy requirement and
the Python standard library.

Synthetic tests cover 3D/horizontal/vertical distance, units, invalid inputs,
evidence normalisation and levels, sparse endpoint rejection, dynamic-marker
penalty, output schema, missing PLY/georeferencing, and ground-truth MAE,
median, RMSE, percentage, and malformed predictions.

```bash
python3 -m pytest -q tests/analysis tests/evaluation
```

## Next-step interface

A future viewer consumes the existing Step 3 PLY plus
`analysis/evidence_map/quality_grid.json` for region colouring and
`analysis/measurements.json` for labels/statuses. It must render
`direct_observation_status`, `evidence_level`, and warnings alongside numeric
measurements; it must not present `evidence_score` as accuracy or suppress an
`INSUFFICIENT_EVIDENCE` status.
