# PotholeAI — Intelligent Road Pothole Detection

A local CSE471 project with a FastAPI/SQLite backend, an existing Ultralytics YOLO checkpoint, and a React/Vite dashboard. The model is loaded once at backend startup. The backend verifies that its class metadata contains `Pothole` (case-insensitive) and refuses inference if it does not.

## Project layout

```text
Pothole-Detection-system/
├── models/yolov8n.pt
├── backend/app/             # API, SQLAlchemy models, inference service
├── frontend/src/            # React dashboard
├── uploads/                 # temporary video inputs
├── outputs/                 # annotated media
├── .env.example
└── run_app.bat
```

## Requirements

- Windows 10/11, Python 3.10 or newer, and Node.js 20 or newer with npm.
- The supplied `models/yolov8n.pt` checkpoint.
- Python packages in `backend/requirements.txt`. Installing Ultralytics also installs its PyTorch runtime dependencies. For CUDA acceleration, install the PyTorch build that matches your CUDA environment before installing the remaining requirements.

## Setup and run

1. Copy `.env.example` to `.env`. Keep `MODEL_PATH=models/yolov8n.pt` for this folder layout. The default confidence threshold is `0.25`.
2. Run `run_app.bat`, or start the services separately from the project root:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r backend\requirements.txt
   python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
   ```

   In another terminal:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

3. Open `http://localhost:5173`. The API docs are at `http://127.0.0.1:8000/docs`.

The first backend run can take time while PyTorch/Ultralytics dependencies install. The model checkpoint itself is not downloaded or replaced.

## Features

- Dashboard statistics and activity chart are derived from the local SQLite detection records.
- Image uploads return an annotated image, class/confidence/bounding-box list, and a saved record.
- Video uploads are processed frame by frame; the annotated MP4 and session summary are saved. OpenCV must have a usable MP4 encoder.
- Live detection requests browser camera permission, streams JPEG frames to `/ws/live-detection`, and displays annotated frames, measured inference FPS, detections, and confidence. Disconnecting a session with detections saves one aggregate session record; frames are not individually persisted.
- History lists saved sessions, links to generated media, and supports deletion.
- Settings show backend/database/model connectivity and the verified checkpoint class names.

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `MODEL_PATH` | `models/yolov8n.pt` | Existing YOLO checkpoint path |
| `DATABASE_URL` | SQLite file in `backend/` | SQLAlchemy database URL |
| `CONFIDENCE_THRESHOLD` | `0.25` | Minimum prediction confidence |
| `MAX_UPLOAD_MB` | `200` | Maximum image/video request size |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Allowed dashboard origin |
| `LIVE_IMAGE_SIZE` | `640` | Maximum live frame dimension and inference image size |

The image/video detection requests may override the threshold with the `confidence` query parameter. Live detection sends the selected threshold when its WebSocket session starts.

## API

- `GET /api/health` — service, model, and database status
- `GET /api/model-info` — checkpoint path, class names, verification and threshold
- `POST /api/detect/image` — multipart image field `file`, optional `confidence`
- `POST /api/detect/video` — multipart video field `file`, optional `confidence`
- `GET /api/detections` — saved history (`limit`, `offset`)
- `GET /api/detections/{id}` — one history record
- `DELETE /api/detections/{id}` — remove a record and its generated output
- `GET /api/analytics/summary` — totals, type counts and recent records
- `WS /ws/live-detection` — binary JPEG input frames; JSON output includes detections, measured FPS, and annotated frame bytes encoded as base64
- `/outputs/{filename}` — generated annotated files

## Database

SQLite table `detections`: `id`, `detection_type`, `filename`, `pothole_count`, `average_confidence`, `highest_confidence`, `annotated_image_path`, `annotated_video_path`, and `created_at`. Live sessions create at most one aggregate row when the client disconnects and only if potholes were observed.

## Troubleshooting

- **Model unavailable / backend degraded:** check `models/yolov8n.pt`, dependency installation, and `/api/model-info`. The backend logs the load error and does not fall back to a generic model.
- **Class verification fails:** check that the checkpoint class names include `Pothole`; this project will not relabel an unrelated class.
- **Camera unavailable:** use `localhost` or HTTPS, allow browser camera access, and confirm no other app has locked the camera.
- **WebSocket fails:** keep the API at `127.0.0.1:8000`; ensure the firewall or browser extensions are not blocking local connections.
- **Video output cannot open:** install an OpenCV build with MP4V encoding support, or try AVI input.
- **Large upload rejected:** adjust `MAX_UPLOAD_MB` in `.env` and restart the API.

## Verification notes

The supplied checkpoint was inspected in this workspace as a PyTorch zip checkpoint without unpickling it. Its metadata declares one class, `Pothole` (Ultralytics version recorded in checkpoint: 8.4.18). The current environment does not have PyTorch, Ultralytics, FastAPI, SQLAlchemy, Node.js, or npm installed, so inference, API execution, browser camera, and frontend build could not be run here. Install the requirements and use the API/dashboard checks above before presenting a runtime demo. Do not report accuracy or throughput unless measured on your target machine.
