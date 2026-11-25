from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Detection(Base):
    __tablename__ = "detections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    detection_type: Mapped[str] = mapped_column(String(16), index=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    pothole_count: Mapped[int] = mapped_column(Integer, default=0)
    average_confidence: Mapped[float] = mapped_column(Float, default=0)
    highest_confidence: Mapped[float] = mapped_column(Float, default=0)
    annotated_image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    annotated_video_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
