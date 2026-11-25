from contextlib import asynccontextmanager
import logging
from pathlib import Path
from uuid import uuid4
import asyncio
import base64
import cv2
import numpy as np
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session
from .config import OUTPUT_DIR, UPLOAD_DIR, settings
from .database import Base, engine, get_db, SessionLocal
from . import models
from .schemas import DetectionOut
from .services.detection_service import save_record
from .services.yolo_service import yolo_service, encode_jpeg


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    try:
        yolo_service.load()
    except Exception as exc:
        yolo_service.error = str(exc)
        logging.getLogger("potholeai").exception("YOLO checkpoint could not be verified or loaded")
    yield


app = FastAPI(title="PotholeAI API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
MAX_BYTES = settings.max_upload_mb * 1024 * 1024
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
VIDEO_TYPES = {"video/mp4", "video/x-msvideo", "video/quicktime", "video/x-matroska", "application/octet-stream"}


async def read_upload(file: UploadFile, allowed: set[str]) -> bytes:
    if file.content_type not in allowed:
        raise HTTPException(415, "Unsupported file type")
    data = await file.read(MAX_BYTES + 1)
    if not data:
        raise HTTPException(400, "Uploaded file is empty")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit")
    return data


def public_path(path: Path):
    return "/outputs/" + path.name


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    try:
        db.query(func.count(models.Detection.id)).scalar()
        db_status = "ok"
    except Exception:
        db_status = "error"
    return {"success": True, "status": "ok" if yolo_service.model else "degraded", "model_loaded": yolo_service.model is not None, "database": db_status}


@app.get("/api/model-info")
def model_info():
    return {"success": True, **yolo_service.info()}


@app.post("/api/detect/image")
async def detect_image(file: UploadFile = File(...), confidence: float | None = None, db: Session = Depends(get_db)):
    data = await read_upload(file, IMAGE_TYPES)
    arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise HTTPException(400, "Invalid or unreadable image")
    if arr.shape[0] * arr.shape[1] > 40_000_000:
        raise HTTPException(413, "Image dimensions exceed the 40 megapixel limit")
    annotated, detections = await asyncio.to_thread(yolo_service.predict, arr, confidence)
    name = f"image_{uuid4().hex}.jpg"
    out = OUTPUT_DIR / name
    if not cv2.imwrite(str(out), annotated):
        raise HTTPException(500, "Could not save annotated image")
    row = save_record(db, "image", Path(file.filename or "upload").name[:255], detections, image_path=public_path(out))
    return {"success": True, "id": row.id, "pothole_count": len(detections), "detections": detections,
            "average_confidence": row.average_confidence, "highest_confidence": row.highest_confidence,
            "annotated_image_url": public_path(out)}


@app.post("/api/detect/video")
async def detect_video(file: UploadFile = File(...), confidence: float | None = None, db: Session = Depends(get_db)):
    if file.content_type not in VIDEO_TYPES:
        raise HTTPException(415, "Unsupported video type")
    data = await file.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(413 if data else 400, "Empty video or upload size limit exceeded")
    ext = Path(file.filename or "video.mp4").suffix.lower()
    if ext not in {".mp4", ".avi", ".mov", ".mkv", ".webm"}:
        ext = ".mp4"
    source = UPLOAD_DIR / f"src_{uuid4().hex}{ext}"
    target = OUTPUT_DIR / f"video_{uuid4().hex}.mp4"
    source.write_bytes(data)
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        source.unlink(missing_ok=True)
        raise HTTPException(400, "Could not decode video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*"mp4v"), min(max(fps, 1), 60), (width, height))
    if not writer.isOpened():
        cap.release(); source.unlink(missing_ok=True)
        raise HTTPException(500, "Video encoder unavailable")
    all_detections, frame_count, last = [], 0, []
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            annotated, detections = await asyncio.to_thread(yolo_service.predict, frame, confidence)
            writer.write(annotated)
            frame_count += 1
            last = detections
            all_detections.extend(detections)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        cap.release(); writer.release(); source.unlink(missing_ok=True)
    if frame_count == 0:
        target.unlink(missing_ok=True)
        raise HTTPException(400, "Video contains no decodable frames")
    row = save_record(db, "video", Path(file.filename or "video").name[:255], all_detections, video_path=public_path(target))
    return {"success": True, "id": row.id, "frame_count": frame_count, "pothole_count": row.pothole_count,
            "average_confidence": row.average_confidence, "highest_confidence": row.highest_confidence,
            "detections": last, "annotated_video_url": public_path(target)}


@app.get("/api/detections", response_model=list[DetectionOut])
def list_detections(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    return db.query(models.Detection).order_by(models.Detection.created_at.desc()).offset(max(0, offset)).limit(min(max(limit, 1), 500)).all()


@app.get("/api/detections/{record_id}", response_model=DetectionOut)
def get_detection(record_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Detection, record_id)
    if not row: raise HTTPException(404, "Detection record not found")
    return row


@app.delete("/api/detections/{record_id}")
def delete_detection(record_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Detection, record_id)
    if not row: raise HTTPException(404, "Detection record not found")
    for value in (row.annotated_image_path, row.annotated_video_path):
        if value:
            candidate = (OUTPUT_DIR / Path(value).name).resolve()
            if candidate.parent == OUTPUT_DIR.resolve(): candidate.unlink(missing_ok=True)
    db.delete(row); db.commit()
    return {"success": True, "deleted_id": record_id}


@app.get("/api/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    rows = db.query(models.Detection).all()
    counts = {k: sum(1 for x in rows if x.detection_type == k) for k in ("image", "video", "live")}
    return {"success": True, "total_sessions": len(rows), "total_potholes": sum(r.pothole_count for r in rows),
            "average_confidence": sum(r.average_confidence for r in rows) / len(rows) if rows else 0,
            "by_type": counts, "recent": [DetectionOut.model_validate(r).model_dump(mode="json") for r in rows[:8]]}


@app.websocket("/ws/live-detection")
async def live_detection(ws: WebSocket):
    await ws.accept()
    try:
        live_confidence = float(ws.query_params.get("confidence", settings.confidence_threshold))
    except ValueError:
        live_confidence = settings.confidence_threshold
    session_detections = []
    try:
        while True:
            raw = await ws.receive_bytes()
            if len(raw) > 5 * 1024 * 1024:
                await ws.send_json({"error": "Frame exceeds 5 MB"}); continue
            frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                await ws.send_json({"error": "Invalid frame"}); continue
            h, w = frame.shape[:2]
            scale = min(1.0, settings.live_image_size / max(h, w))
            if scale < 1:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            t0 = asyncio.get_running_loop().time()
            annotated, detections = await asyncio.to_thread(yolo_service.predict, frame, live_confidence, settings.live_image_size)
            session_detections.extend(detections)
            elapsed = max(asyncio.get_running_loop().time() - t0, 1e-6)
            await ws.send_json({"detections": detections, "pothole_count": len(detections), "fps": round(1 / elapsed, 1),
                                "frame": base64.b64encode(encode_jpeg(annotated)).decode("ascii")})
    except WebSocketDisconnect:
        if session_detections:
            db = SessionLocal()
            try:
                save_record(db, "live", "Live camera session", session_detections)
            finally:
                db.close()
