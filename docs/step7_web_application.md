# SkyTrace Step 7 Web Application

Step 7 adds a thin FastAPI API and a React/Three.js viewer around the existing
Steps 1-6 pipeline. It does not reimplement reconstruction, georeferencing,
object detection, object association, or measurement logic.

## Local Workflow

Install backend dependencies:

```bash
python -m pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

Start the backend:

```bash
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend:

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173/viewer/processed-demo` to load the checked-in
processed run without rerunning the expensive pipeline.

## API

- `GET /health`
- `GET /runs`
- `POST /runs`
- `POST /runs/{run_id}/upload`
- `POST /runs/{run_id}/process`
- `GET /runs/{run_id}/status`
- `GET /runs/{run_id}/scene`
- `GET /runs/{run_id}/objects`
- `GET /runs/{run_id}/evidence`
- `GET /runs/{run_id}/results`
- `POST /runs/{run_id}/measure`
- `GET /runs/{run_id}/assets/{relative_path}`

The typed frontend contract lives in `frontend/src/types/api.ts`, and all HTTP
calls go through `frontend/src/services/api.ts`.

## Viewer Contract

The viewer loads actual Step 2/3 assets exposed by `/runs/{run_id}/scene`.
Supported browser formats are PLY point clouds, GLTF/GLB meshes, and OBJ
meshes. If no supported asset exists, the viewer shows an explicit empty-state
message instead of rendering fabricated scene geometry.

Object annotations come from Step 5 `scene_objects/objects_3d.json`. Dynamic
object candidates use a distinct marker color, but the UI preserves the
reported `motion_status`; unknown motion is shown as unknown.

Evidence view overlays Step 6 `analysis/evidence_map/quality_grid.json`
regions. The legend text comes from the backend:

- `HIGH`: strong supporting evidence
- `MEDIUM`: moderate supporting evidence
- `LOW`: weak supporting evidence
- `INSUFFICIENT`: insufficient evidence for reliable interpretation

Interactive measurements send selected 3D coordinates to `POST
/runs/{run_id}/measure`. The backend delegates to Step 6
`measure_scene_distance`, so the browser only selects coordinates and displays
the returned distance, horizontal/vertical values, status, evidence level, and
warnings.

## Known Limitations

The MVP uses in-process background execution for local development. It does not
include authentication, cloud storage, a distributed worker queue, calibrated
survey accuracy, or guaranteed real-time processing. Large PLY files may need a
future visualization export/downsampling step for comfortable browser use.
