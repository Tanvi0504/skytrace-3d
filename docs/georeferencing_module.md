# SkyTrace — Step 3: GPS Georeferencing & Metric Scaling

Location: `pipeline/georeferencing/`  
Tests: `tests/georeferencing/`

Step 3 reads a completed Step 2 model and external GPS/flight metadata, then
writes a separate local-metric georeferenced output. It does not modify Step 1
or Step 2, access the original video, run reconstruction, or implement
measurements, object detection, confidence mapping, IMU fusion, RTK/PPK, or UI.

## Simple flow

1. Read Step 2 camera centers and PLY point cloud.
2. Read valid GPS observations from CSV or JSON.
3. Convert GPS latitude/longitude/altitude to local East-North-Up (ENU) metres.
4. Match cameras to GPS by image name, frame index, then timestamp.
5. Robustly fit a rotation, translation, and—when Step 2 has arbitrary
   scale—a global scale factor.
6. Apply that transform to the full point cloud and camera trajectory.
7. Record transform parameters, rejected outliers, diagnostics, and warnings.

## Input interfaces

### Step 2 reconstruction

```text
outputs/<run_id>/reconstruction/
├── camera_poses.json
├── dense/fused.ply                 # preferred automatically when present
└── sparse/sparse.ply               # otherwise selected automatically
```

Step 3 uses the existing Step 2 `camera_poses.json` format: each pose needs an
`image_name` and a `camera_center_world`. It reads all camera centers and
transforms every one, even when a particular camera has no GPS match.

For timestamp matching only, it looks beside `reconstruction/` for the existing
Step 1 `frame_manifest.json`. That manifest maps selected filenames to
`timestamp_seconds`; Step 3 reads it but never changes it. If the manifest is
missing, image-name and frame-index matching still work.

### GPS / flight metadata

Pass a `.json` or `.csv` file. Each usable record must contain latitude,
longitude, and altitude because a 3D alignment cannot safely be derived without
the vertical coordinate.

| Meaning | Accepted fields |
|---|---|
| Latitude | `latitude`, `lat`, `gps_latitude` |
| Longitude | `longitude`, `lon`, `lng`, `gps_longitude` |
| Altitude | `altitude`, `altitude_m`, `altitude_metres`, `altitude_meters`, `height`, `gps_altitude`, `relative_altitude` |
| Timestamp | `timestamp`, `timestamp_seconds`, `time`, `time_seconds` |
| Frame ID | `frame_index`, `frame_number`, `frame`, `image_id` |
| Image name | `image_name`, `filename`, `frame_filename`, `image`, `file` |

Canonical JSON example:

```json
{
  "coordinate_system": "WGS 84 geographic latitude/longitude",
  "altitude_reference": "ellipsoidal height",
  "observations": [
    {
      "image_name": "frame_000120.jpg",
      "frame_index": 120,
      "timestamp_seconds": 4.0,
      "latitude": 17.3850,
      "longitude": 78.4867,
      "altitude": 120.4
    }
  ]
}
```

The JSON may instead be a bare array, or use `gps`/`records` in place of
`observations`. CSV uses the same field names in its header. Timestamps may be
numeric seconds or ISO-8601 values with an explicit timezone. Step 1 frame
indices are zero-based source-video indices, so `frame_000120.jpg` matches
`frame_index: 120` exactly.

Malformed records are omitted and listed in warnings. No valid records, fewer
than three matches, or a degenerate trajectory returns a clear failure rather
than fake georeferenced coordinates.

## Coordinate systems

GPS data defaults to WGS-84 latitude/longitude if metadata does not declare a
CRS. Step 3 first converts WGS-84 geographic coordinates to Earth-Centered
Earth-Fixed (ECEF), then to a local ENU tangent plane at the median valid GPS
observation. The target axes are:

```text
X = East (metres)
Y = North (metres)
Z = Up (metres)
```

ENU is suitable for this compact, local-scene baseline because it produces
physical local coordinates in metres while avoiding the invalid treatment of
latitude/longitude degrees as Cartesian X/Y. The exact origin is stored in
`transform.json`, making the conversion reproducible. The source altitude
reference is copied from metadata; if absent, it is explicitly marked as
undeclared. A constant vertical-datum offset does not change relative ENU
height differences, but it limits interpretation of absolute height.

This follows the standard ECEF-to-topocentric conversion described by
[PROJ](https://proj.org/en/stable/operations/conversions/topocentric.html).

## Correspondence, alignment, and scale

Matching priority is intentionally explicit:

1. Exact image filename.
2. Step 1 source frame index parsed from `frame_000120.jpg`.
3. Timestamp. When a frame timestamp lies between two GPS timestamps, Step 3
   linearly interpolates the already-local-ENU positions only when both GPS
   samples are within `--timestamp-tolerance-seconds`.

The transform is:

```text
ENU_target = scale × rotation × COLMAP_source + translation
```

Step 2's current `camera_poses.json` declares its coordinates arbitrary, so
Step 3 estimates a global similarity transform (Sim(3)). Its scale comes from
the full configuration and distances of accepted camera/GPS trajectory pairs,
using the least-squares Umeyama method—not an arbitrary constant.

RANSAC forms three-point candidate transforms, rejects trajectory correspondences
whose residual exceeds `--ransac-threshold-metres`, and refits the final Sim(3)
with the remaining inliers. Rejected pairs, their residuals, and rejection
reason are retained in `correspondences.json`; no evidence is silently deleted.
The threshold is an inlier-consistency setting in ENU metres, not an accuracy
claim. At least three non-collinear pairs are required: a straight-line flight
does not constrain the full 3D scene orientation and is rejected clearly.

For a future Step 2 backend that explicitly declares metric scale,
`--source-scale-mode auto` fixes scale to `1.0` and fits only a rigid transform.
This avoids an arbitrary second rescale. Use `--source-scale-mode arbitrary` or
`metric` only to override a known source-scale declaration.

The current Step 2 exporter declares scale with its existing `scale` text. A
future backend may instead set a top-level `scale_is_metric` or `metric_scale`
boolean, or use `"scale": {"is_metric": true, "units": "metres"}`. The
output transform records both what the source declared and how this run treated
the scale, so an explicit CLI override remains auditable.

COLMAP defines camera poses as world-to-camera projections and camera center as
`-RᵀT`; Step 2 already exports this center, so Step 3 aligns
`camera_center_world`, not the raw COLMAP translation. See the
[COLMAP output format](https://colmap.github.io/format.html) for that convention.

## Command line

```bash
python -m pipeline.georeferencing \
  --reconstruction outputs/example/reconstruction \
  --gps outputs/example/metadata/gps.json \
  --output outputs/example/georeferenced
```

Use `python3` where that is the system Python command.

| Option | Default | Meaning |
|---|---:|---|
| `--point-cloud PATH` | auto | Use this Step 2 PLY instead of automatic dense/sparse selection. |
| `--timestamp-tolerance-seconds` | `1.0` | Maximum gap from frame time to each bracketing GPS sample. |
| `--ransac-threshold-metres` | `10.0` | ENU inlier tolerance; not an accuracy number. |
| `--ransac-iterations` | `300` | Maximum deterministic RANSAC samples. |
| `--source-scale-mode` | `auto` | `auto`, `arbitrary`, or `metric`. |
| `--overwrite` | off | Delete and recreate a non-empty Step 3 output directory. |

## Python API

```python
from pipeline.georeferencing import georeference_reconstruction

result = georeference_reconstruction(
    reconstruction_dir="outputs/example/reconstruction",
    gps_metadata_path="outputs/example/metadata/gps.json",
    output_dir="outputs/example/georeferenced",
)

if result.success:
    print(result.estimated_scale)
    print(result.point_cloud_path)
else:
    print(result.error)
```

`GeoreferencingResult` contains success/failure, GPS count, matched-pose count,
RANSAC inliers, method, scale, inlier trajectory residual statistics, output
paths, warnings, and processing time.

## Output interface

```text
outputs/<run_id>/georeferenced/
├── point_cloud_georef.ply
├── camera_trajectory_georef.csv
├── transform.json
├── correspondences.json
├── validation.json
└── georef_metadata.json
```

- `point_cloud_georef.ply` is the selected full PLY in local ENU metres. ASCII
  and binary-little-endian PLY with scalar floating `x`, `y`, and `z` vertex
  properties are supported.
- `camera_trajectory_georef.csv` has all camera centers in ENU plus matching,
  residual, and inlier columns when a GPS correspondence exists.
- `transform.json` includes source/target systems, ENU origin, scale, rotation,
  translation, a reproducible 4×4 source-to-ENU matrix, and separate fields for
  the source's scale declaration, selected scale mode, and whether scale was
  estimated.
- `correspondences.json` preserves all matched pairs and documented outliers.
- `validation.json` contains match rate, threshold, support assessment, and
  residual scope/statistics.
- `georef_metadata.json` contains the structured API result and is written for
  failures that occur after the output workspace is created.

The next measurement module must consume `point_cloud_georef.ply`,
`camera_trajectory_georef.csv`, `transform.json`, and `validation.json` as its
exact interface. All positions share the local ENU metre coordinate system.

## Validation and limitations

The tests create a spatially diverse synthetic camera trajectory, apply a known
rotation, scale, and translation, and recover it. They also add noise and a
large GPS-like outlier to verify RANSAC rejection. Additional tests cover GPS
CSV aliases, invalid and missing GPS, ENU conversion, timestamp interpolation,
metric-source scale preservation, output metadata, and insufficient matches.

Run tests:

```bash
pytest
```

The reported residuals are **camera-trajectory-to-GPS fit residuals**, not
independent 3D geometry error, measurement error, survey accuracy, or proof of
centimetre-level positioning. Ordinary GPS may be noisy, incorrectly timed,
have an unknown vertical datum, and represent the GNSS antenna rather than the
camera. Local ENU is unsuitable for city-scale/long-range projects. More
diverse matched frames, RTK/PPK, camera-to-GNSS lever-arm calibration, and
well-defined altitude references are needed before stronger claims are possible.

Future IMU orientation, barometric altitude, RTK/PPK, and lever-arm support
belong in new sensor-observation adapters before correspondence/alignment. They
must remain separate from ordinary GPS unless their coordinate frame and
uncertainty model are explicitly defined.
