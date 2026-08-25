# Runtime dependency reference

`requirements.txt` is the fully resolved Python lock used by Docker and native setup; `frontend/package-lock.json` locks the browser bundle. The backend Dockerfile also pins its Python, Node, and Nginx base-image digests, PyTorch CPU wheel, and direct FFmpeg/COLMAP package versions. Docker uses Python 3.11 and Node 22; native environments are supported on Python 3.10-3.12 and Node 20-22.

| Dependency | Supported version | Purpose | Installation | System requirements |
| --- | --- | --- | --- | --- |
| Python | 3.10-3.12 (3.11 in Docker) | Runs API, pipeline and CLI | `scripts/setup.sh` or Docker image | macOS/Linux; Python build supported by its platform |
| Node.js/npm | 20-22 | Builds the React/Three.js frontend | `npm --prefix frontend ci` or frontend Docker image | Node runtime; no GPU requirement |
| OpenCV | `4.14.0.94` | Video decode, sampling and frame quality filtering | `requirements.txt` | Platform OpenCV wheel or its documented system libraries |
| NumPy | `2.4.6` | Geometry, reconstruction-adjacent and analysis maths | `requirements.txt` | CPU architecture supported by NumPy |
| PyYAML | `6.0.3` | Pipeline configuration | `requirements.txt` | None beyond Python |
| Ultralytics + PyTorch | Ultralytics `8.4.128`; PyTorch `2.5.1` CPU | YOLO11n Step 4 detection and tracking | `requirements.txt`; Docker pulls the official CPU wheel first; weights via `python -m skytrace.setup_models` | CPU is supported; CUDA is optional and must be validated separately |
| FastAPI/Pydantic/Uvicorn | FastAPI `0.141.1`, Pydantic `2.13.4`, Uvicorn `0.52.4` | HTTP API and validation | `requirements.txt` | Python 3.10-3.12 |
| python-multipart | `0.0.32` | Streaming MP4 upload handling | `requirements.txt` | None beyond Python |
| FFmpeg | System package | Reliable video codec support | `apt-get install ffmpeg` in Docker; platform package manager natively | Must be on `PATH` for a live native readiness check |
| COLMAP | System package | Sparse/dense photogrammetry reconstruction | `apt-get install colmap` in Docker; platform package manager natively | Must be on `PATH`; CPU works, CUDA is optional |
| YOLO11n weights | `yolo11n.pt` release asset | Pretrained detector used in Step 4 | Explicit `skytrace.setup_models` command | ~5.4 MB; review its license before deployment |

Run `python -m skytrace.system_check` after a native setup, or let `./scripts/setup.sh` run it as part of Docker setup. It reports each missing item, the reason it is needed, and the exact remediation.
