from statistics import mean
from sqlalchemy.orm import Session
from ..models import Detection


def save_record(db: Session, kind: str, filename: str, detections: list[dict], image_path=None, video_path=None):
    scores = [d["confidence"] for d in detections]
    row = Detection(detection_type=kind, filename=filename, pothole_count=len(detections),
                    average_confidence=mean(scores) if scores else 0.0,
                    highest_confidence=max(scores, default=0.0),
                    annotated_image_path=image_path, annotated_video_path=video_path)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
