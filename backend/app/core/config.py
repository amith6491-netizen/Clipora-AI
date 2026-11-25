from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Clipora AI"
    app_version: str = "1.0.0"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "clipora_ai"
    storage_dir: Path = Path("./storage")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Upload duration bounds (up to 20 minutes)
    min_video_duration_seconds: float = 10.0
    max_video_duration_seconds: float = 1200.0
    max_upload_size_mb: int = 2048

    # Authentication (JWT)
    auth_secret_key: str = "clipora-dev-secret-change-in-production"
    auth_token_expire_hours: int = 72

    # AI / ML configuration
    whisper_model_size: str = "base"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"
    nlp_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Shorts generation configuration
    min_shorts_count: int = 5
    max_shorts_count: int = 15
    min_clip_duration_seconds: float = 10.0
    max_clip_duration_seconds: float = 20.0

    # Optional explicit binary overrides
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_storage_dir(self) -> Path:
        return self.storage_dir.resolve()

    @property
    def uploads_dir(self) -> Path:
        return self.resolved_storage_dir / "uploads"

    @property
    def audio_dir(self) -> Path:
        return self.resolved_storage_dir / "audio"

    @property
    def thumbs_dir(self) -> Path:
        return self.resolved_storage_dir / "thumbs"

    @property
    def subtitles_dir(self) -> Path:
        return self.resolved_storage_dir / "subtitles"

    @property
    def renders_dir(self) -> Path:
        return self.resolved_storage_dir / "renders"

    @property
    def exports_dir(self) -> Path:
        return self.resolved_storage_dir / "exports"

    def ensure_dirs(self) -> None:
        for directory in (
            self.resolved_storage_dir,
            self.uploads_dir,
            self.audio_dir,
            self.thumbs_dir,
            self.subtitles_dir,
            self.renders_dir,
            self.exports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
