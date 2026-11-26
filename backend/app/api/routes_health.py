import importlib.util

from fastapi import APIRouter, Request

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.core.media_tools import resolve_media_binaries
from app.models.schemas import SystemHealthOut

router = APIRouter(tags=["health"])


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


@router.get("/health")
async def liveness_health(request: Request) -> dict[str, str]:
    """Lightweight liveness probe for container hosts (e.g. Render) so startup checks never stall on DB I/O."""
    settings: Settings = request.app.state.settings
    return {"status": "ok", "service": settings.app_name}


@router.get("/api/health", response_model=SystemHealthOut)
async def get_system_health(request: Request) -> SystemHealthOut:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings

    mongo_ok = await db.ping(timeout_sec=1.5)
    ffmpeg_ok = False
    ffprobe_ok = False
    try:
        bins = resolve_media_binaries(settings)
        ffmpeg_ok = bool(bins.ffmpeg)
        ffprobe_ok = bool(bins.ffprobe)
    except Exception:
        pass

    whisper_ok = _module_available("faster_whisper")
    scenedetect_ok = _module_available("scenedetect")
    opencv_ok = _module_available("cv2")
    nlp_ok = _module_available("sentence_transformers") and _module_available("sklearn")
    yt_dlp_ok = _module_available("yt_dlp")

    all_ok = all([mongo_ok, ffmpeg_ok, ffprobe_ok, whisper_ok, scenedetect_ok, opencv_ok, nlp_ok])
    return SystemHealthOut(
        status="ok" if all_ok else "degraded",
        mongodb_connected=mongo_ok,
        ffmpeg_available=ffmpeg_ok,
        ffprobe_available=ffprobe_ok,
        faster_whisper_available=whisper_ok,
        scenedetect_available=scenedetect_ok,
        opencv_available=opencv_ok,
        nlp_model_available=nlp_ok,
        yt_dlp_available=yt_dlp_ok,
        min_video_duration_seconds=settings.min_video_duration_seconds,
        max_video_duration_seconds=settings.max_video_duration_seconds,
    )
