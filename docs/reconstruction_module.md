# SkyTrace — Step 2: Baseline 3D Reconstruction

Location: `pipeline/reconstruction/`  
Tests: `tests/reconstruction/`

This is the standalone Step 2 baseline. It consumes only the selected image
directory produced by Step 1 and does not open the original video, sample
frames, or apply blur filtering.

## Input contract

Pass Step 1's existing output directory directly:

```text
outputs/<run_id>/frames/
    frame_000000.jpg
    frame_000006.jpg
    ...
```

Step 1's `metadata.json`, `frame_manifest.json`, and all files under
`pipeline/video/` are intentionally untouched. Step 2 reads only decodable
image files from the supplied `frames/` directory.

## Install COLMAP

COLMAP is an external system dependency, not a Python package in
`requirements.txt`. The `colmap` executable must be available on `PATH`, or
its path can be supplied with `--colmap-executable`.

On macOS with Homebrew:

```bash
brew install colmap
```

On Debian/Ubuntu systems where the distribution package is suitable:

```bash
sudo apt update
sudo apt install colmap
```

If your Linux distribution does not provide a recent compatible package, build
from the official COLMAP instructions. Confirm the installation before a run:

```bash
colmap -h
```

Sparse feature extraction and matching use the CPU by default so the baseline
can run on machines without CUDA. Pass `--use-gpu` only when your COLMAP build
has compatible GPU support. COLMAP's PatchMatch dense stage commonly requires
CUDA; its failure is reported separately and does not discard sparse output.

## Run from the command line

```bash
python -m pipeline.reconstruction \
    --frames outputs/example/frames \
    --output outputs/example/reconstruction
```

Use `python3` instead of `python` on systems where that is the Python command.

Important options:

| Flag | Default | Description |
|---|---:|---|
| `--backend` | `colmap` | Reconstruction backend. The interface allows future backends without coupling callers to COLMAP. |
| `--no-dense` | off | Skip the optional dense MVS pass and generate sparse output only. |
| `--matcher` | `sequential` | Match chronological video frames sequentially; use `exhaustive` for smaller, non-sequential image sets. |
| `--colmap-executable` | `colmap` | Executable name on `PATH` or an absolute executable path. |
| `--use-gpu` | off | Enable GPU SIFT extraction/matching if supported by COLMAP. |
| `--max-image-size` | `2000` | Dense-undistortion image size cap. |
| `--per-image-camera` | off | Do not assume one shared camera model across all video frames. |
| `--overwrite` | off | Delete and recreate a non-empty reconstruction output directory. |

The program exits with `1` if the input or required COLMAP executable is
invalid. If sparse SfM completes but dense MVS fails, it exits successfully,
warns on stderr, and preserves the sparse artifacts.

## Python API

```python
from pipeline.reconstruction import run_reconstruction

result = run_reconstruction(
    frames_dir="outputs/example/frames",
    output_dir="outputs/example/reconstruction",
    backend="colmap",
    dense=True,
)

if result.success:
    print(result.registered_image_count)
    print(result.sparse_point_cloud_path)
else:
    print(result.error)
```

`ReconstructionResult` includes the backend, input and registered-image counts,
sparse-point count, dense status, processing time, output locations, warnings,
and error information. Its `success` field means sparse reconstruction
succeeded. Inspect `dense_status` (`completed`, `failed`, `not_requested`) to
determine the separate dense outcome.

## Output layout

```text
outputs/<run_id>/reconstruction/
├── database.db                         # COLMAP feature/match database
├── sparse/
│   ├── models/0/                       # native COLMAP sparse model
│   ├── text/0/                          # cameras.txt, images.txt, points3D.txt
│   └── sparse.ply                       # standard sparse point cloud
├── camera_poses.json                   # COLMAP image poses and camera centers
├── dense/
│   └── fused.ply                        # present only after dense success
├── logs/
│   └── <colmap-stage>.log               # command, stdout, stderr, exit code
└── reconstruction_metadata.json         # result and artifact locations
```

If COLMAP creates more than one sparse model, Step 2 exports each to text,
then selects the model with the most registered images (using point count as a
tie-breaker) for `sparse.ply`, `camera_poses.json`, and any dense attempt.

The `.ply` outputs are standard point clouds suitable for later Open3D or web
viewer integration. The `camera_poses.json` records COLMAP's local coordinate
convention. Neither sparse nor dense output is georeferenced, and scale is
arbitrary: this baseline does not claim metric accuracy.

## Pipeline stages

The COLMAP backend runs these actual COLMAP commands:

1. `feature_extractor`
2. `sequential_matcher` (or `exhaustive_matcher`)
3. `mapper` for Structure-from-Motion
4. `model_converter` to export the sparse TXT model and PLY point cloud
5. When enabled, `image_undistorter`, `patch_match_stereo`, and `stereo_fusion`

Every command receives a separate persistent log. A failure in stages 1–4 is a
failed reconstruction. A failure in stage 5 is a dense-only failure, with all
successful sparse artifacts preserved.

## Tests

```bash
pytest
```

The unit tests do not execute a costly real COLMAP run. They cover missing and
empty frame directories, invalid images, output workspace creation, generated
COLMAP commands, COLMAP text-result parsing, command failures, and dense
failure preservation. A full COLMAP reconstruction is intentionally a manual
or optional integration test because it requires COLMAP and suitable imagery.
