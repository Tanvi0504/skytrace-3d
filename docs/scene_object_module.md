# SkyTrace — Step 5: 2D Objects to 3D Scene Association

Location: `pipeline/scene_objects/`  
Tests: `tests/scene_objects/`

Step 5 conservatively links tracked Step 4 detections to the Step 2
reconstruction and, when available, Step 3's georeferenced coordinate system.
It does not alter Steps 1–4, modify COLMAP artifacts, fabricate a depth from a
single box, estimate object dimensions, or claim survey-grade localization.

## Flow

```text
Step 4 track observations + Step 2 calibrated camera poses
                         |
                         v
bottom-centre pixel anchor -> calibrated world-space rays
                         |
                         v
checked multi-view ray triangulation -> optional Step 3 transform
                         |
                         v
3D semantic scene marker, evidence score, and limitations
```

The anchor is the bounding box's bottom centre. It is a cautious proxy for a
person's foot point or a ground vehicle's contact point; it is not proof of a
scene-surface intersection. A single view is explicitly insufficient.

## Inputs and joins

```text
outputs/<run_id>/objects/detections.json
outputs/<run_id>/reconstruction/camera_poses.json
outputs/<run_id>/reconstruction/sparse/text/<model>/cameras.txt
outputs/<run_id>/georeferenced/transform.json       # optional
```

Step 5 uses the existing `track_id` and joins `frame_filename` to Step 2's
`image_name`. It reads Step 2's COLMAP world-to-camera quaternion and
translation plus the corresponding, actual `cameras.txt` model, image size,
and intrinsics. Supported models are `SIMPLE_PINHOLE`, `PINHOLE`,
`SIMPLE_RADIAL`, `RADIAL`, `OPENCV`, `FULL_OPENCV`, `OPENCV_FISHEYE`,
`SIMPLE_RADIAL_FISHEYE`, and `RADIAL_FISHEYE`. A missing, malformed, or
unsupported calibration produces no 3D coordinate for that observation.

For every track, it stores observation count, usable calibrated-observation
count, first/last Step 1 frame indices when available, minimum/mean/median/
maximum detector confidence, and majority-class consistency. Temporary detector misses,
occlusion, and entering/leaving the frame are represented by the observations
that actually exist; consecutive frames are not required.

## Association method and safeguards

For each valid observation, the module undistorts the bottom-centre pixel with
the COLMAP calibration and transforms the resulting camera ray into Step 2
reconstruction coordinates. It estimates the point that minimizes the sum of
squared perpendicular distances to all supporting rays.

The estimate is unavailable when fewer than two calibrated views exist, every
camera centre is coincident, the ray system is degenerate or ill-conditioned,
or the solved point lies behind any supporting camera. Small median parallax
or a high normalized ray residual yields `low_confidence`, never a claim of
accuracy. The reusable `intersect_ray_with_plane` helper is tested but is only
appropriate when a caller supplies a separately justified semantic plane;
Step 5 does not fit a ground plane from arbitrary sparse points.

Dynamic-capable tracks are retained with a warning: the fused triangulation
assumes a spatially consistent anchor. Since Step 4 supplies 2D tracking but
not independently validated per-frame depth, `object_trajectories.json`
explicitly reports 3D trajectories as unavailable rather than inventing a
path.

## Georeferencing

When a valid Step 3 `transform.json` is supplied, Step 5 applies its published
homogeneous source-to-target transform directly. With the current Step 3 local
East-North-Up (ENU) format and its WGS-84 origin, it also converts the result
to latitude, longitude, and altitude. Without that precise transform or ENU
origin, `world_coordinate_status` remains `unavailable` or
`estimated_transformed_coordinate_system`; latitude/longitude are never
invented.

## Evidence score

`evidence_score` is an evidence-strength indicator, not an accuracy,
probability, or ground-truth measure. For an estimate with `n` usable rays it
is calculated as:

```text
mean_detection_confidence
× (1 - 1/n)
× sin(median pairwise line angle)
× 1 / (1 + ray_RMSE / median camera baseline)
```

All terms are dimensionless. The JSON metadata repeats the formula and its
definitions. The raw ray-intersection RMSE remains in reconstruction units,
which can be arbitrary before a Step 3 scale alignment.

## Outputs

```text
outputs/<run_id>/scene_objects/
├── objects_3d.json
├── object_tracks_3d.json
├── object_trajectories.json
├── scene_annotations.json
└── association_metadata.json
```

`objects_3d.json` contains one result per Step 4 track, including unavailable
results and warnings. `scene_annotations.json` is a lightweight marker list
for a future viewer; it does not duplicate the point cloud or create object
meshes. The default refuses a non-empty output directory; `--overwrite`
replaces only the explicit Step 5 output directory.

## CLI

```bash
python3 -m pipeline.scene_objects \
  --objects outputs/example/objects \
  --reconstruction outputs/example/reconstruction \
  --georeferenced outputs/example/georeferenced \
  --output outputs/example/scene_objects
```

Useful controls are `--minimum-ray-angle-degrees` (default `1`),
`--max-normalized-ray-residual` (default `0.25`),
`--max-condition-number` (default `1e8`), and `--overwrite`.

## Python API

```python
from pipeline.scene_objects import associate_objects_with_3d_scene

result = associate_objects_with_3d_scene(
    object_dir="outputs/example/objects",
    reconstruction_dir="outputs/example/reconstruction",
    georeferenced_dir="outputs/example/georeferenced",
    output_dir="outputs/example/scene_objects",
)

if result.success:
    print(result.estimated_count, result.low_confidence_count)
else:
    print(result.error)
```

`SceneAssociationResult` reports track, estimated, low-confidence, and
unavailable counts; output paths; processing time; average time per track; and
run-level warnings.

## Validation

The synthetic unit tests cover malformed Step 4 input, missing poses, malformed
intrinsics, calibrated pixel-to-ray conversion, coordinate transformation,
ray/plane intersection, known-point multi-view triangulation, zero baseline,
behind-camera rejection, low-parallax handling, world-coordinate conversion,
and output schema.

Run the focused suite with:

```bash
python3 -m pytest -q tests/scene_objects
```
