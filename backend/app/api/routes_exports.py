import asyncio
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.api import serialize_export
from app.core.config import Settings
from app.core.database import DatabaseManager, utc_now
from app.models.schemas import (
    AspectRatio,
    BatchExportIn,
    ExportQuality,
    ExportRecordOut,
    RenderedVariant,
)
from app.services.auth_service import get_optional_user
from app.services.render_service import (
    build_variant_key,
    create_clips_zip_archive,
    make_safe_filename,
    render_clip_mp4,
)
from app.services.storage_service import get_source_video_path

router = APIRouter(tags=["exports"])


@router.get("/api/exports", response_model=list[ExportRecordOut])
async def list_all_exports(
    request: Request,
    current_user: dict | None = Depends(get_optional_user),
) -> list[ExportRecordOut]:
    db: DatabaseManager = request.app.state.db
    user_id = str(current_user["_id"]) if current_user else None
    docs = await db.list_exports(user_id=user_id)
    return [serialize_export(d) for d in docs]


@router.get("/api/videos/{video_id}/exports", response_model=list[ExportRecordOut])
async def list_video_exports(video_id: str, request: Request) -> list[ExportRecordOut]:
    db: DatabaseManager = request.app.state.db
    docs = await db.list_exports(video_id=video_id)
    return [serialize_export(d) for d in docs]


@router.get("/api/clips/{clip_id}/download")
async def download_clip_mp4(
    clip_id: str,
    request: Request,
    quality: ExportQuality = Query(default="1080p"),
    aspect_ratio: AspectRatio | None = Query(default=None),
) -> FileResponse:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings

    clip = await db.get_clip(clip_id)
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")
    video = await db.get_video(clip["video_id"])
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent video project not found.")

    source_path = get_source_video_path(settings, video["_id"], video["format_ext"])
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source video file missing.")

    target_ar = aspect_ratio or clip.get("aspect_ratio", "9:16")
    out_path, sig, size_bytes = await asyncio.to_thread(
        render_clip_mp4,
        source_path,
        int(video["width"]),
        int(video["height"]),
        bool(video.get("has_audio", True)),
        clip,
        quality,
        target_ar,
        settings,
    )

    v_key = build_variant_key(quality, target_ar)
    variant = RenderedVariant(
        quality=quality,
        aspect_ratio=target_ar,
        file_name=out_path.name,
        file_size_bytes=size_bytes,
        rendered_at=utc_now(),
        signature=sig,
    ).model_dump()
    await db.update_clip(clip_id, {f"rendered_variants.{v_key}": variant})

    download_name = f"{int(clip['index']):02d}_{make_safe_filename(clip['title'])}_{quality}_{target_ar.replace(':', 'x')}.mp4"
    export_id = uuid.uuid4().hex[:14]
    await db.insert_export(
        {
            "_id": export_id,
            "user_id": video.get("user_id"),
            "video_id": str(clip["video_id"]),
            "kind": "single",
            "quality": quality,
            "file_name": download_name,
            "file_path": str(out_path),
            "file_size_bytes": size_bytes,
            "clip_count": 1,
            "download_url": f"/api/clips/{clip_id}/download?quality={quality}&aspect_ratio={target_ar}",
            "created_at": utc_now(),
        }
    )

    return FileResponse(
        out_path,
        media_type="video/mp4",
        filename=download_name,
    )


@router.post("/api/videos/{video_id}/export-zip", response_model=ExportRecordOut, status_code=status.HTTP_201_CREATED)
async def export_all_clips_zip(
    video_id: str,
    payload: BatchExportIn,
    request: Request,
) -> ExportRecordOut:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings

    video = await db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")

    clips = await db.list_clips(video_id)
    if payload.clip_ids:
        requested = set(payload.clip_ids)
        clips = [c for c in clips if c["_id"] in requested]
    if not clips:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No clips found to export.")

    source_path = get_source_video_path(settings, video_id, video["format_ext"])
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source video file missing.")

    rendered_entries: list[tuple[str, Path]] = []
    for clip in clips:
        target_ar = clip.get("aspect_ratio", "9:16")
        out_path, sig, size_bytes = await asyncio.to_thread(
            render_clip_mp4,
            source_path,
            int(video["width"]),
            int(video["height"]),
            bool(video.get("has_audio", True)),
            clip,
            payload.quality,
            target_ar,
            settings,
        )
        v_key = build_variant_key(payload.quality, target_ar)
        variant = RenderedVariant(
            quality=payload.quality,
            aspect_ratio=target_ar,
            file_name=out_path.name,
            file_size_bytes=size_bytes,
            rendered_at=utc_now(),
            signature=sig,
        ).model_dump()
        await db.update_clip(clip["_id"], {f"rendered_variants.{v_key}": variant})

        arcname = f"{int(clip['index']):02d}_{make_safe_filename(clip['title'])}_{payload.quality}_{target_ar.replace(':', 'x')}.mp4"
        rendered_entries.append((arcname, out_path))

    zip_path, zip_name, zip_size = await asyncio.to_thread(
        create_clips_zip_archive,
        video_id,
        video["title"],
        rendered_entries,
        payload.quality,
        settings,
    )

    export_id = uuid.uuid4().hex[:14]
    export_doc = {
        "_id": export_id,
        "user_id": video.get("user_id"),
        "video_id": video_id,
        "kind": "zip",
        "quality": payload.quality,
        "file_name": zip_name,
        "file_path": str(zip_path),
        "file_size_bytes": zip_size,
        "clip_count": len(rendered_entries),
        "download_url": f"/api/exports/{export_id}/download",
        "created_at": utc_now(),
    }
    await db.insert_export(export_doc)
    return serialize_export(export_doc)


@router.get("/api/exports/{export_id}/download")
async def download_export_zip(export_id: str, request: Request) -> FileResponse:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_export(export_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export archive not found.")

    file_path = Path(doc["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file no longer exists on disk.")

    return FileResponse(
        file_path,
        media_type="application/zip",
        filename=doc["file_name"],
    )
