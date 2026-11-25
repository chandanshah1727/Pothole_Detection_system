from pathlib import Path
from threading import Lock
import cv2
from ultralytics import YOLO
from ..config import settings


class YOLOService:
    def __init__(self):
        self.model = None
        self.lock = Lock()
        self.names = {}
        self.device = "unknown"
        self.error = None

    def load(self):
        if not settings.model_path.is_file():
            raise FileNotFoundError(f"YOLO checkpoint not found: {settings.model_path}")
        self.model = YOLO(str(settings.model_path))
        names = self.model.names
        self.names = {int(k): str(v) for k, v in names.items()} if isinstance(names, dict) else dict(enumerate(map(str, names)))
        if not any(name.strip().lower() == "pothole" for name in self.names.values()):
            self.model = None
            raise RuntimeError(f"Checkpoint does not contain a pothole class. Found: {self.names}")
        self.device = str(getattr(self.model, "device", "auto"))

    def info(self):
        return {"loaded": self.model is not None, "model_path": str(settings.model_path), "class_names": self.names,
                "pothole_class_verified": any(n.strip().lower() == "pothole" for n in self.names.values()),
                "confidence_threshold": settings.confidence_threshold, "device": self.device, "error": self.error}

    def predict(self, frame, confidence=None, imgsz=None):
        if self.model is None:
            raise RuntimeError("YOLO model is not loaded")
        threshold = settings.confidence_threshold if confidence is None else max(0.01, min(float(confidence), 0.99))
        with self.lock:
            result = self.model.predict(frame, conf=threshold, imgsz=imgsz or settings.live_image_size, verbose=False)[0]
        items = []
        for box in result.boxes:
            cls = int(box.cls.item())
            name = self.names.get(cls, str(cls))
            if name.strip().lower() != "pothole":
                continue
            coords = [round(float(v), 2) for v in box.xyxy[0].tolist()]
            items.append({"class_name": name, "confidence": round(float(box.conf.item()), 4), "bbox": coords})
        annotated = result.plot()
        return annotated, items


yolo_service = YOLOService()


def encode_jpeg(frame):
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        raise RuntimeError("Could not encode annotated image")
    return buf.tobytes()
