# SkyTrace — Step 1: Video Ingestion, Frame Extraction & Blur Filtering

Location: `pipeline/video/`
Tests: `tests/video/`

This module is the first stage of the SkyTrace pipeline. It takes a
single-pass drone video and produces a directory of good-quality,
chronologically-ordered frames plus JSON metadata describing the run.
It is standalone: it does not import from, or know about, any other
pipeline stage (reconstruction, georeferencing, objects, measurement,
confidence).

## What it does

1. Validates the input video exists, is readable, and can be decoded.
2. Reads container metadata (resolution, FPS, frame count, duration).
3. Samples frames at a configurable target FPS (never upsamples beyond
   the source FPS).
4. Scores every sampled frame's sharpness using Laplacian variance.
5. Rejects frames scoring below a configurable blur threshold.
6. Saves selected frames as zero-padded, chronologically-named JPEGs.
7. Writes `metadata.json`, `frame_manifest.json`, and
   `rejected_frames.json` describing the run.

## Installing dependencies

```bash
pip install -r requirements.txt
```

## Running the CLI

```bash
python -m pipeline.video \
    --video data/test/example.mp4 \
    --output outputs/example \
    --target-fps 5 \
    --blur-threshold 100
```

Arguments:

| Flag                | Required | Default | Description                                              |
|----------------------|----------|---------|------------------------------------------------------------|
| `--video`            | yes      | —       | Path to the input video file.                              |
| `--output`           | yes      | —       | Run output directory (e.g. `outputs/example`).              |
| `--target-fps`       | no       | `5.0`   | Target sampling rate, in frames/sec, of the output frames.  |
| `--blur-threshold`   | no       | `100.0` | Minimum Laplacian-variance score to keep a sampled frame.   |
| `--run-id`           | no       | dir name| Identifier stored in the JSON outputs.                      |
| `--jpeg-quality`     | no       | `95`    | JPEG quality (0–100) for saved frames.                       |
| `-v`, `--verbose`    | no       | off     | Per-frame DEBUG logging.                                     |

Exit code is `0` on success, `1` on any validation or ingestion error
(message printed to stderr).

### Using it from Python

```python
from pipeline.video import VideoProcessingConfig, process_video

config = VideoProcessingConfig(
    video_path="data/test/example.mp4",
    output_dir="outputs/example",
    target_fps=5.0,
    blur_threshold=100.0,
)
result = process_video(config)

print(result.selected_count, "frames selected")
print(result.frames_dir)
```

## Running tests

```bash
pytest
```

Tests generate small synthetic MP4s on the fly (via OpenCV) — no large
real drone footage is required. Coverage includes: missing/invalid video
files, metadata extraction, frame sampling rate, sharpness scoring,
threshold filtering, output file generation, and metadata/manifest JSON
schema.

## Example output directory

```
outputs/example/
├── frames/
│   ├── frame_000000.jpg
│   ├── frame_000006.jpg
│   ├── frame_000012.jpg
│   └── ...
├── metadata.json
├── frame_manifest.json
└── rejected_frames.json
```

Frame filenames use the *original source frame index* (not a sequential
counter), so `frame_000120.jpg` was the 120th frame of the source video.
This preserves an unambiguous mapping back to the source timeline.

## Example `metadata.json`

```json
{
  "run_id": "example",
  "source_video": {
    "filename": "example.mp4",
    "width": 320,
    "height": 240,
    "fps": 30.0,
    "frame_count": 90,
    "duration_seconds": 3.0
  },
  "sampling_fps": 5.0,
  "blur_threshold": 100.0,
  "sampled_frame_count": 15,
  "selected_frame_count": 15,
  "rejected_frame_count": 0,
  "processing_time_seconds": 0.0406,
  "frames_dir": "outputs/example/frames"
}
```

## Example `frame_manifest.json` entry

```json
{
  "frame_index": 120,
  "timestamp_seconds": 4.0,
  "sharpness_score": 143.2,
  "selected": true,
  "filename": "frame_000120.jpg"
}
```

Rejected frames appear in the manifest too (with `"selected": false` and
`"filename": null`), and are additionally mirrored into
`rejected_frames.json` for convenience.

## Integration contract for Step 2 (reconstruction)

The reconstruction stage should depend **only on the filesystem output**,
not on any Python class from this module:

- **Input to Step 2:** `outputs/<run_id>/frames/` — a directory of
  chronologically-named JPEGs.
- Optionally, Step 2 can read `outputs/<run_id>/frame_manifest.json` for
  per-frame timestamps and sharpness scores if useful (e.g. to weight
  frames), but this is not required to consume the frames themselves.

```python
selected_frames_dir = "outputs/<run_id>/frames/"
```

## Known limitations

- **Blur detection is a heuristic, not a guarantee.** Laplacian variance
  is a cheap, widely-used proxy for sharpness. It can be fooled by
  low-texture scenes (e.g. plain sky, uniform rooftops) and does not
  specifically model motion blur vs. defocus blur vs. sensor noise. The
  `--blur-threshold` will likely need tuning per camera/lens/altitude.
- **Container frame counts can be unreliable.** Some codecs/containers
  report an approximate or missing `frame_count`/`duration`; this module
  falls back to `null` in metadata when that happens, and always relies
  on frames actually decoded (not the header count) for sampling.
- **No GPS/flight metadata handling.** This module only looks at the
  video stream itself. Associating frames with GPS/flight-log data is
  out of scope for Step 1.
- **No parallelism.** Frames are read and scored sequentially; this is
  fine for typical single-pass drone clips but is not optimized for very
  long videos.
