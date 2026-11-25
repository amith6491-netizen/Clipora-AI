import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from app.api import serialize_video
from app.core.config import Settings
from app.core.database import DatabaseManager, utc_now
from app.models.schemas import (
    AnalysisSummary,
    AspectRatio,
    ExportQuality,
    VideoProjectOut,
    YouTubeImportIn,
    YouTubePreviewIn,
    YouTubePreviewOut,
)
from app.services.auth_service import get_optional_user
from app.services.pipeline_service import (
    cancel_video_processing,
    event_broker,
    initial_pipeline_steps,
    start_video_processing,
)
from app.services.storage_service import (
    delete_video_files,
    get_poster_path,
    get_source_video_path,
    save_and_validate_upload,
)
from app.services.youtube_service import fetch_youtube_metadata

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.get("", response_model=list[VideoProjectOut])
async def list_videos(
    request: Request,
    current_user: dict | None = Depends(get_optional_user),
) -> list[VideoProjectOut]:
    db: DatabaseManager = request.app.state.db
    user_id = str(current_user["_id"]) if current_user else None
    docs = await db.list_videos(user_id=user_id)
    return [serialize_video(d) for d in docs]


@router.post("/youtube/preview", response_model=YouTubePreviewOut)
async def preview_youtube_video(payload: YouTubePreviewIn, request: Request) -> YouTubePreviewOut:
    settings: Settings = request.app.state.settings
    meta = await asyncio.to_thread(fetch_youtube_metadata, payload.url, settings)
    return YouTubePreviewOut(
        url=meta.url,
        video_key=meta.video_key,
        title=meta.title,
        channel=meta.channel,
        duration=meta.duration,
        thumbnail_url=meta.thumbnail_url,
        valid_duration=meta.valid_duration,
        validation_message=meta.validation_message,
    )


@router.post("/youtube", response_model=VideoProjectOut, status_code=status.HTTP_201_CREATED)
async def import_youtube_video(
    payload: YouTubeImportIn,
    request: Request,
    current_user: dict | None = Depends(get_optional_user),
) -> VideoProjectOut:
    settings: Settings = request.app.state.settings
    db: DatabaseManager = request.app.state.db

    meta = await asyncio.to_thread(fetch_youtube_metadata, payload.url, settings)
    if not meta.valid_duration:
        raise HTTPException(
            status_code=422,
            detail=meta.validation_message or "YouTube video duration is outside allowed bounds.",
        )

    import uuid

    video_id = uuid.uuid4().hex
    clean_title = (payload.title or "").strip() or meta.title
    clamped_shorts = max(
        settings.min_shorts_count,
        min(settings.max_shorts_count, payload.target_shorts_count),
    )
    now = utc_now()

    doc = {
        "_id": video_id,
        "user_id": str(current_user["_id"]) if current_user else None,
        "title": clean_title[:120],
        "original_filename": f"youtube_{meta.video_key}.mp4",
        "format_ext": ".mp4",
        "size_bytes": 0,
        "duration": round(meta.duration, 3),
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "has_audio": True,
        "source_type": "youtube",
        "youtube_url": meta.url,
        "status": "queued" if payload.auto_process else "uploaded",
        "progress": 0.0,
        "current_stage": "youtube_download" if payload.auto_process else "uploaded",
        "error_message": None,
        "target_shorts_count": clamped_shorts,
        "default_aspect_ratio": payload.default_aspect_ratio,
        "default_quality": payload.default_quality,
        "pipeline_steps": initial_pipeline_steps(include_youtube=True),
        "analysis_summary": AnalysisSummary().model_dump(),
        "clips_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.insert_video(doc)

    if payload.auto_process:
        start_video_processing(video_id, db, settings)

    return serialize_video(doc)


@router.post("/upload", response_model=VideoProjectOut, status_code=status.HTTP_201_CREATED)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    target_shorts_count: int = Form(default=10),
    default_aspect_ratio: AspectRatio = Form(default="9:16"),
    default_quality: ExportQuality = Form(default="1080p"),
    auto_process: bool = Form(default=True),
    current_user: dict | None = Depends(get_optional_user),
) -> VideoProjectOut:
    settings: Settings = request.app.state.settings
    db: DatabaseManager = request.app.state.db

    clamped_shorts = max(
        settings.min_shorts_count,
        min(settings.max_shorts_count, target_shorts_count),
    )

    video_id, _, ext, metadata = await save_and_validate_upload(file, settings)
    clean_title = (title or "").strip() or Path(file.filename or "Untitled Video").stem
    now = utc_now()

    doc = {
        "_id": video_id,
        "user_id": str(current_user["_id"]) if current_user else None,
        "title": clean_title[:120],
        "original_filename": file.filename or f"{video_id}{ext}",
        "format_ext": ext,
        "size_bytes": metadata.size_bytes,
        "duration": round(metadata.duration, 3),
        "width": metadata.width,
        "height": metadata.height,
        "fps": metadata.fps,
        "has_audio": metadata.has_audio,
        "source_type": "upload",
        "youtube_url": None,
        "status": "queued" if auto_process else "uploaded",
        "progress": 0.0,
        "current_stage": "queued" if auto_process else "uploaded",
        "error_message": None,
        "target_shorts_count": clamped_shorts,
        "default_aspect_ratio": default_aspect_ratio,
        "default_quality": default_quality,
        "pipeline_steps": initial_pipeline_steps(include_youtube=False),
        "analysis_summary": AnalysisSummary().model_dump(),
        "clips_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.insert_video(doc)

    if auto_process:
        start_video_processing(video_id, db, settings)

    return serialize_video(doc)


@router.get("/{video_id}", response_model=VideoProjectOut)
async def get_video(video_id: str, request: Request) -> VideoProjectOut:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_video(video_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")
    return serialize_video(doc)


@router.post("/{video_id}/process", response_model=VideoProjectOut)
async def process_video(video_id: str, request: Request) -> VideoProjectOut:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings
    doc = await db.get_video(video_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")

    if doc["status"] == "processing":
        return serialize_video(doc)

    is_yt = doc.get("source_type") == "youtube"
    await db.update_video(
        video_id,
        {
            "status": "queued",
            "progress": 0.0,
            "current_stage": "youtube_download" if is_yt else "queued",
            "error_message": None,
            "pipeline_steps": initial_pipeline_steps(include_youtube=is_yt),
        },
    )
    start_video_processing(video_id, db, settings)
    updated = await db.get_video(video_id)
    assert updated is not None
    return serialize_video(updated)


@router.post("/{video_id}/cancel", response_model=VideoProjectOut)
async def cancel_video(video_id: str, request: Request) -> VideoProjectOut:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_video(video_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")

    updated = await cancel_video_processing(video_id, db)
    assert updated is not None
    return serialize_video(updated)


@router.get("/{video_id}/progress")
async def stream_video_progress(video_id: str, request: Request) -> StreamingResponse:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_video(video_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")

    async def event_stream():
        queue = event_broker.subscribe(video_id)
        try:
            current = await db.get_video(video_id)
            if current:
                snapshot = {
                    "video_id": video_id,
                    "status": current["status"],
                    "progress": current.get("progress", 0.0),
                    "current_stage": current.get("current_stage", "uploaded"),
                    "pipeline_steps": [
                        {
                            **s,
                            "started_at": s["started_at"].isoformat() if s.get("started_at") else None,
                            "completed_at": s["completed_at"].isoformat() if s.get("completed_at") else None,
                        }
                        for s in current.get("pipeline_steps", [])
                    ],
                    "error_message": current.get("error_message"),
                }
                yield f"data: {json.dumps(snapshot)}\n\n"
                if current["status"] in ("completed", "failed", "cancelled"):
                    return

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("status") in ("completed", "failed", "cancelled"):
                        break
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            event_broker.unsubscribe(video_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{video_id}/transcript")
async def get_video_transcript(video_id: str, request: Request) -> dict:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_video(video_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")
    artifacts = await db.get_analysis_artifacts(video_id)
    if not artifacts:
        return {"video_id": video_id, "language": "en", "segments": [], "scenes": []}
    return {
        "video_id": video_id,
        "language": artifacts.get("language", "en"),
        "segments": artifacts.get("segments", []),
        "scenes": artifacts.get("scenes", []),
    }


@router.get("/{video_id}/poster")
async def get_video_poster(video_id: str, request: Request) -> FileResponse:
    settings: Settings = request.app.state.settings
    poster = get_poster_path(settings, video_id)
    if not poster.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poster image not found.")
    return FileResponse(poster, media_type="image/jpeg")


@router.get("/{video_id}/source")
async def stream_source_video(video_id: str, request: Request) -> FileResponse:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings
    doc = await db.get_video(video_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")
    src = get_source_video_path(settings, video_id, doc["format_ext"])
    if not src.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source video file missing.")
    media_map = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }
    return FileResponse(src, media_type=media_map.get(doc["format_ext"], "application/octet-stream"))


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(video_id: str, request: Request) -> None:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings
    doc = await db.get_video(video_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")
    if doc.get("status") in ("queued", "processing"):
        await cancel_video_processing(video_id, db, wait_for_cleanup=True)
    delete_video_files(settings, video_id, doc.get("format_ext"))
    await db.delete_video(video_id)
