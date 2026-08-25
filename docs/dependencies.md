# Runtime dependency reference

`requirements.txt` and `frontend/package-lock.json` are the installation sources. The Python direct-dependency ranges keep supported security and patch updates available; record the resolved versions from a release image (`python -m pip freeze`) with each production deployment. Docker uses Python 3.11 and Node 22; native environments are supported on Python 3.10-3.12 and Node 20-22.

| Dependency | Supported version | Purpose | Installation | System requirements |
| --- | --- | --- | --- | --- |
| Python | 3.10-3.12 (3.11 in Docker) | Runs API, pipeline and CLI | `scripts/setup.sh` or Docker image | macOS/Linux; Python build supported by its platform |
| Node.js/npm | 20-22 | Builds the React/Three.js frontend | `npm --prefix frontend ci` or frontend Docker image | Node runtime; no GPU requirement |
| OpenCV | `>=4.8,<5` | Video decode, sampling and frame quality filtering | `requirements.txt` | Platform OpenCV wheel or its documented system libraries |
| NumPy | `>=1.24,<3` | Geometry, reconstruction-adjacent and analysis maths | `requirements.txt` | CPU architecture supported by NumPy |
| PyYAML | `>=6,<7` | Pipeline configuration | `requirements.txt` | None beyond Python |
| Ultralytics + PyTorch | Ultralytics `>=8.3,<9`; PyTorch `2.5.1` | YOLO11n Step 4 detection and tracking | `requirements.txt`; Docker pulls the official CPU wheel; weights via `python -m skytrace.setup_models` | CPU is supported; CUDA is optional and must be validated separately |
| FastAPI/Pydantic/Uvicorn | FastAPI `>=0.115,<1`, Pydantic `>=2,<3`, Uvicorn `>=0.30,<1` | HTTP API and validation | `requirements.txt` | Python 3.10-3.12 |
| python-multipart | `>=0.0.9,<1` | Streaming MP4 upload handling | `requirements.txt` | None beyond Python |
| FFmpeg | System package | Reliable video codec support | `apt-get install ffmpeg` in Docker; platform package manager natively | Must be on `PATH` for a live native readiness check |
| COLMAP | System package | Sparse/dense photogrammetry reconstruction | `apt-get install colmap` in Docker; platform package manager natively | Must be on `PATH`; CPU works, CUDA is optional |
| YOLO11n weights | `yolo11n.pt` release asset | Pretrained detector used in Step 4 | Explicit `skytrace.setup_models` command | ~5.4 MB; review its license before deployment |

Run `python -m skytrace.system_check` after a native setup, or let `./scripts/setup.sh` run it as part of Docker setup. It reports each missing item, the reason it is needed, and the exact remediation.
