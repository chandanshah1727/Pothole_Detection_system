from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    model_path: Path = ROOT / "models" / "yolov8n.pt"
    database_url: str = f"sqlite:///{(ROOT / 'backend' / 'potholeai.db').as_posix()}"
    confidence_threshold: float = 0.25
    max_upload_mb: int = 200
    frontend_origin: str = "http://localhost:5173"
    live_image_size: int = 640


settings = Settings()
UPLOAD_DIR = ROOT / "uploads"
OUTPUT_DIR = ROOT / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
