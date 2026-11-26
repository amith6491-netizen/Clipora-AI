import asyncio
from pathlib import Path
import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.core.config import Settings
from app.core.database import DatabaseManager, utc_now
from app.models.schemas import (
    AnalysisSummary,
    AspectRatio,
    InstagramDownloadIn,
    InstagramDownloadOut,
    ScoreBreakdown,
    SubtitleStyle,
)
from app.services.auth_service import get_optional_user
from app.services.instagram_service import InstagramVideoResult, download_instagram_high_quality
from app.services.storage_service import get_poster_path, get_source_video_path

router = APIRouter(prefix="/api/instagram", tags=["instagram"])


def _serialize_instagram(doc: dict) -> InstagramDownloadOut:
    item_id = str(doc["_id"])
    clip_id = doc.get("clip_id")
    return InstagramDownloadOut(
        id=item_id,
        url=doc["url"],
        shortcode=doc["shortcode"],
        title=doc["title"],
        author=doc["author"],
        duration=float(doc["duration"]),
        width=int(doc["width"]),
        height=int(doc["height"]),
        file_name=doc["file_name"],
        file_size_bytes=int(doc["file_size_bytes"]),
        preview_url=f"/api/instagram/{item_id}/file",
        download_url=f"/api/instagram/{item_id}/file?download=true",
        thumbnail_url=f"/api/instagram/{item_id}/thumbnail",
        video_id=doc.get("video_id"),
        clip_id=clip_id,
        edit_url=f"/clips/{clip_id}/edit" if clip_id else None,
        created_at=doc["created_at"],
    )


def _stage_editable_source_files(
    res: InstagramVideoResult,
    video_id: str,
    clip_id: str,
    settings: Settings,
) -> None:
    """Mirror downloaded Instagram media into studio upload/thumbnail paths for EditorPage."""
    src_target = get_source_video_path(settings, video_id, ".mp4")
    src_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(res.file_path, src_target)

    poster_target = get_poster_path(settings, video_id)
    poster_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(res.thumbnail_path, poster_target)

    clip_thumb = settings.thumbs_dir / f"{video_id}_{clip_id}.jpg"
    shutil.copy2(res.thumbnail_path, clip_thumb)


@router.get("", response_model=list[InstagramDownloadOut])
async def list_instagram_downloads(
    request: Request,
    current_user: dict | None = Depends(get_optional_user),
) -> list[InstagramDownloadOut]:
    db: DatabaseManager = request.app.state.db
    user_id = str(current_user["_id"]) if current_user else None
    docs = await db.list_instagram_downloads(user_id=user_id)
    return [_serialize_instagram(d) for d in docs]


@router.post("/download", response_model=InstagramDownloadOut, status_code=status.HTTP_201_CREATED)
async def fetch_instagram_video(
    payload: InstagramDownloadIn,
    request: Request,
    current_user: dict | None = Depends(get_optional_user),
) -> InstagramDownloadOut:
    settings: Settings = request.app.state.settings
    db: DatabaseManager = request.app.state.db

    res = await asyncio.to_thread(download_instagram_high_quality, payload.url, settings)
    user_id = str(current_user["_id"]) if current_user else None
    now = utc_now()
    video_id = f"ig_{res.item_id}"
    clip_id = f"igc_{uuid.uuid4().hex[:11]}"
    duration = round(max(0.5, float(res.metadata.duration)), 3)
    default_ar: AspectRatio = "9:16" if res.metadata.height >= res.metadata.width else "16:9"

    await asyncio.to_thread(_stage_editable_source_files, res, video_id, clip_id, settings)

    video_doc = {
        "_id": video_id,
        "user_id": user_id,
        "title": res.title[:120],
        "original_filename": res.file_name,
        "format_ext": ".mp4",
        "size_bytes": res.metadata.size_bytes,
        "duration": duration,
        "width": res.metadata.width,
        "height": res.metadata.height,
        "fps": res.metadata.fps,
        "has_audio": res.metadata.has_audio,
        "source_type": "instagram",
        "youtube_url": None,
        "instagram_url": res.normalized_url,
        "status": "completed",
        "progress": 100.0,
        "current_stage": "completed",
        "error_message": None,
        "target_shorts_count": 1,
        "default_aspect_ratio": default_ar,
        "default_quality": "1080p",
        "pipeline_steps": [],
        "analysis_summary": AnalysisSummary(shorts_generated=1).model_dump(),
        "clips_count": 1,
        "created_at": now,
        "updated_at": now,
    }
    await db.insert_video(video_doc)

    clip_doc = {
        "_id": clip_id,
        "video_id": video_id,
        "user_id": user_id,
        "index": 1,
        "title": res.title[:140],
        "category": "engaging",
        "secondary_categories": [],
        "engagement_score": 95.0,
        "score_breakdown": ScoreBreakdown(
            nlp_score=90.0,
            audio_score=90.0,
            visual_score=95.0,
            hook_score=95.0,
            completeness_score=100.0,
        ).model_dump(),
        "ai_reason": (
            f"Fetched directly from Instagram ({res.metadata.width}x{res.metadata.height}, "
            f"{duration:.1f}s) for Studio editing, captioning, trimming, and HD download."
        ),
        "transcript_text": "",
        "original_start": 0.0,
        "original_end": duration,
        "trim_start": 0.0,
        "trim_end": duration,
        "duration": duration,
        "aspect_ratio": default_ar,
        "captions_enabled": False,
        "subtitle_style": SubtitleStyle().model_dump(),
        "subtitles": [],
        "rendered_variants": {},
        "created_at": now,
        "updated_at": now,
    }
    await db.replace_clips_for_video(video_id, [clip_doc])

    doc = {
        "_id": res.item_id,
        "user_id": user_id,
        "url": res.normalized_url,
        "shortcode": res.shortcode,
        "title": res.title,
        "author": res.author,
        "duration": duration,
        "width": res.metadata.width,
        "height": res.metadata.height,
        "file_name": res.file_name,
        "file_path": str(res.file_path),
        "thumbnail_path": str(res.thumbnail_path),
        "file_size_bytes": res.metadata.size_bytes,
        "video_id": video_id,
        "clip_id": clip_id,
        "created_at": now,
    }
    await db.insert_instagram_download(doc)
    return _serialize_instagram(doc)


@router.get("/{item_id}/file")
async def serve_instagram_file(
    item_id: str,
    request: Request,
    download: bool = Query(default=False),
) -> FileResponse:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_instagram_download(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instagram download not found.")

    file_path = Path(doc["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file no longer exists on disk.")

    if download:
        return FileResponse(file_path, media_type="video/mp4", filename=doc["file_name"])
    return FileResponse(file_path, media_type="video/mp4")


@router.get("/{item_id}/thumbnail")
async def serve_instagram_thumbnail(item_id: str, request: Request) -> FileResponse:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_instagram_download(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instagram download not found.")

    thumb_path = Path(doc["thumbnail_path"])
    if not thumb_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thumbnail not found.")
    return FileResponse(thumb_path, media_type="image/jpeg")


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instagram_download(item_id: str, request: Request) -> None:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_instagram_download(item_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instagram download not found.")

    Path(doc["file_path"]).unlink(missing_ok=True)
    Path(doc["thumbnail_path"]).unlink(missing_ok=True)
    await db.delete_instagram_download(item_id)
