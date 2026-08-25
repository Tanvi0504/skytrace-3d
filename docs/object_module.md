# SkyTrace — Step 4: Object Detection, Tracking & Dynamic-Object Masks

Location: `pipeline/objects/`  
Tests: `tests/objects/`

Step 4 consumes selected Step 1 images and produces 2D object evidence for a
later reconstruction-improvement or 3D-association stage. It does not change
the original frames, rerun COLMAP, change Step 2 or Step 3 artifacts, or claim
3D object locations, perfect tracking, or observed real-world motion.

## Flow

```text
selected Step 1 frames
        |
        v
pretrained detector (YOLO by default)
        |
        +--> optional existing ByteTrack IDs
        |
        v
dynamic-capable category policy
        |
        +--> per-frame binary masks
        +--> 2D detections and track summaries
        +--> future 2D-to-3D association metadata
```

## Detector and tracking backend

The default backend is a lazy wrapper around the well-supported
[Ultralytics](https://docs.ultralytics.com/) YOLO API. Its default pretrained
model name is `yolo11n.pt`; this is a lightweight baseline, not a claim that it
is the best model for every drone scene. `--model` accepts another compatible
pretrained Ultralytics model name or local model path.

`ultralytics>=8.3` is declared in `requirements.txt`. Model import and weight
loading happen only at execution time, so importing `pipeline.objects` and
running the unit suite do not download weights. A first successful YOLO run may
download the requested pretrained weights. If the package, model, device, or
weights are unavailable, the API returns a structured failure and, once its
output directory has been created, writes `object_metadata.json` describing it.

When tracking is enabled (the default), the wrapper calls Ultralytics' existing
`track(..., persist=True, tracker="bytetrack.yaml")` integration. This uses
ByteTrack rather than a project-specific tracker. The configured backend may
temporarily return no IDs when it cannot associate an object; those detections
are still retained. `--no-tracking` preserves detections but intentionally
removes track IDs from output.

The exact loaded model label and model-supported class list are saved in
`object_metadata.json`. The baseline does not promise that every animal or
object type can be recognised; only labels reported by the selected model are
available.

## Dynamic-capable categories and motion limitation

The `is_dynamic_candidate` policy includes the following common COCO labels:

```text
person, bicycle, car, motorcycle, airplane, bus, train, truck, boat,
bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe, drone
```

Each receives `motion_status: "unknown"`. This means a person, vehicle, or
animal is capable of moving and is conservatively masked; it does **not** mean
it was observed moving. Other detected classes receive
`motion_status: "not_evaluated"`, not a claim that they are static. A parked
car, standing person, vegetation, and any other category can require more
context than a detector provides.

Raw pixel displacement from a moving drone camera cannot reliably indicate
object motion. This baseline therefore does not classify world motion from a
track. A future motion stage must use camera-motion compensation with Step 2
poses/intrinsics, scene geometry, optical flow relative to static support, or
multi-view georeferenced observations. Its result should remain separate from
class and dynamic-capability labels.

## Inputs and frame identity

```text
outputs/<run_id>/frames/
├── frame_000120.jpg
└── ...

outputs/<run_id>/frame_manifest.json    # optional, read only
```

Supported image suffixes are JPG, JPEG, PNG, BMP, and WebP. Step 4 looks for
the existing sibling `frame_manifest.json` and reuses each selected frame's
`frame_index` and `timestamp_seconds`. If it is unavailable, it only recovers a
frame index from names like `frame_000120.jpg`; it never invents a timestamp or
assumes a frame ordering is a temporal correspondence.

Unreadable images and individual model-inference failures are recorded as
warnings and do not stop processing of the remaining frames. An empty or
missing input directory returns a structured failure.

## Outputs

```text
outputs/<run_id>/objects/
├── detections.json
├── tracks.json
├── masks/
│   ├── frame_000120.png
│   └── ...
└── object_metadata.json
```

- `detections.json` preserves every accepted object observation in source-image
  pixel coordinates. Each includes filename, Step 1 frame index/timestamp when
  available, class, confidence, `[x1, y1, x2, y2]` bounding box, optional
  tracker ID, dynamic-capability flag, motion status, and its mask path.
- `tracks.json` summarizes the existing tracker IDs and their source-frame
  evidence. It explicitly marks motion as unknown.
- `masks/*.png` are single-channel images: `255` covers the union of all
  dynamic-capable detection rectangles (with optional padding) and `0` covers
  the rest of the image. An empty all-zero mask is still written for each
  successfully processed frame. Masks are not applied to, or destructive of,
  original frames or Step 2 reconstruction.
- `object_metadata.json` contains the API result, model-supported labels,
  configuration, processing timing/FPS, warnings, dynamic-object policy, and
  future 3D-association contract.

The default refuses to write into a non-empty output directory. Use
`--overwrite` only when replacing a prior Step 4 output. It never writes into
the source-frame directory or one of that directory's parents.

## Step 2 / Step 3 handoff

This step stores the exact join keys needed later:

```text
detection.frame_filename       <-> Step 2 camera_poses.json image_name
detection.frame_filename       <-> Step 3 camera_trajectory_georef.csv image_name
detection.frame_index/timestamp <-> Step 1/flight metadata where available
detection.bbox_xyxy_pixels     + camera intrinsics + matched views -> future rays/geometry
```

Reliable 3D placement will additionally require calibrated intrinsics, valid
camera poses, cross-view object correspondence, and sufficient scene geometry
or ray intersection. A 2D bounding box and a georeferenced camera position are
not enough to establish an exact 3D object coordinate.

## CLI

```bash
python -m pipeline.objects \
  --frames outputs/example/frames \
  --output outputs/example/objects \
  --model yolo11n.pt \
  --confidence-threshold 0.25 \
  --iou-threshold 0.7 \
  --device cpu
```

Useful options:

| Option | Default | Meaning |
|---|---:|---|
| `--model` | `yolo11n.pt` | Compatible pretrained Ultralytics model name/path. |
| `--confidence-threshold` | `0.25` | Keep detections at or above this confidence. |
| `--iou-threshold` | `0.7` | Detector NMS IoU threshold. |
| `--classes person car` | all | Restrict retained model labels by name. |
| `--no-tracking` | off | Detect only; do not request ByteTrack IDs. |
| `--tracker-config` | `bytetrack.yaml` | Ultralytics tracker configuration. |
| `--device` | `cpu` | Ultralytics device such as `cpu`, `0`, or `mps`. |
| `--mask-padding-pixels` | `0` | Expand dynamic-candidate boxes in masks. |
| `--overwrite` | off | Replace a non-empty Step 4 output directory. |

## Python API

```python
from pipeline.objects import detect_and_track_objects

result = detect_and_track_objects(
    frames_dir="outputs/example/frames",
    output_dir="outputs/example/objects",
    model_name="yolo11n.pt",
    confidence_threshold=0.25,
    tracking=True,
    device="cpu",
)

if result.success:
    print(result.detection_count, result.track_count)
else:
    print(result.error)
```

`ObjectPipelineResult` reports success/failure, processed and failed frame
counts, detections, dynamic candidates, unique tracks, detected/supported
classes, processing time, measured frames per second, output paths, and
warnings. Detector implementations satisfy `ObjectDetector`, so a future
backend can replace YOLO without changing output schemas or callers.

## Validation

The unit suite uses synthetic frames and a lightweight injected detector. It
covers invalid and empty inputs, initialization failure, detection and tracking
schemas, mask generation, threshold/class configuration, no-detection output,
and a single-frame runtime failure while later frames continue.

Run all tests with:

```bash
python -m pytest -q
```

An opt-in smoke test can run the real pretrained model against the small
checked-in selected-frame sequence. It may download weights and is skipped by
default:

```bash
SKYTRACE_RUN_OBJECT_INTEGRATION=1 python -m pytest -q -m integration
```

Set `SKYTRACE_OBJECT_INTEGRATION_DEVICE` (for example, `mps` or `0`) only when
that device is already configured for the selected Ultralytics runtime.
