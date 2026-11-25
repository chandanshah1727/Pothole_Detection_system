from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    detection_type: str
    filename: str
    pothole_count: int
    average_confidence: float
    highest_confidence: float
    annotated_image_path: str | None
    annotated_video_path: str | None
    created_at: datetime
