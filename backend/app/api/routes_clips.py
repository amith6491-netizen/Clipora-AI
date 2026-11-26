import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from app.api import serialize_clip
from app.core.config import Settings
from app.core.database import DatabaseManager, utc_now
from app.models.schemas import (
    ClipOut,
    ClipUpdateIn,
    MomentCategory,
    RenderRequestIn,
    RenderedVariant,
    TranscriptSegment,
)
from app.services.audio_service import extract_wav_audio
from app.services.render_service import (
    build_variant_key,
    compute_render_signature,
    render_clip_mp4,
)
from app.services.storage_service import get_source_video_path
from app.services.transcription_service import (
    build_subtitle_cues_from_segments,
    transcribe_audio_with_whisper,
)

router = APIRouter(tags=["clips"])


@router.get("/api/videos/{video_id}/clips", response_model=list[ClipOut])
async def list_video_clips(
    video_id: str,
    request: Request,
    category: MomentCategory | None = Query(default=None),
    sort_by: Literal["score", "timeline", "duration"] = Query(default="score"),
) -> list[ClipOut]:
    db: DatabaseManager = request.app.state.db
    video = await db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video project not found.")

    docs = await db.list_clips(video_id)
    if category is not None:
        docs = [d for d in docs if d.get("category") == category or category in d.get("secondary_categories", [])]

    if sort_by == "timeline":
        docs.sort(key=lambda d: float(d["trim_start"]))
    elif sort_by == "duration":
        docs.sort(key=lambda d: float(d["duration"]), reverse=True)
    else:
        docs.sort(key=lambda d: float(d["engagement_score"]), reverse=True)

    return [serialize_clip(d) for d in docs]


@router.get("/api/clips/{clip_id}", response_model=ClipOut)
async def get_clip(clip_id: str, request: Request) -> ClipOut:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_clip(clip_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")
    return serialize_clip(doc)


@router.patch("/api/clips/{clip_id}", response_model=ClipOut)
async def update_clip(clip_id: str, payload: ClipUpdateIn, request: Request) -> ClipOut:
    db: DatabaseManager = request.app.state.db
    doc = await db.get_clip(clip_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")

    video = await db.get_video(doc["video_id"])
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent video project not found.")

    video_duration = float(video["duration"])
    new_start = float(payload.trim_start) if payload.trim_start is not None else float(doc["trim_start"])
    new_end = float(payload.trim_end) if payload.trim_end is not None else float(doc["trim_end"])

    if new_start < 0.0 or new_end > video_duration:
        raise HTTPException(
            status_code=422,
            detail=f"Trim range [{new_start:.2f}s, {new_end:.2f}s] must lie within video duration (0s – {video_duration:.2f}s).",
        )
    if new_end <= new_start:
        raise HTTPException(
            status_code=422,
            detail="Trim end time must be greater than trim start time.",
        )

    is_full_video = video.get("source_type") == "instagram"
    min_dur = min(1.0, video_duration) if is_full_video else 3.0
    max_dur = max(45.0, video_duration) if is_full_video else 45.0
    new_dur = round(new_end - new_start, 3)
    if new_dur < min_dur or new_dur > max_dur:
        raise HTTPException(
            status_code=422,
            detail=f"Clip duration after trimming must be between {min_dur:.1f} and {max_dur:.1f} seconds.",
        )

    updates: dict = {
        "trim_start": round(new_start, 3),
        "trim_end": round(new_end, 3),
        "duration": new_dur,
    }
    if payload.title is not None:
        updates["title"] = payload.title.strip()
    if payload.aspect_ratio is not None:
        updates["aspect_ratio"] = payload.aspect_ratio
    if payload.captions_enabled is not None:
        updates["captions_enabled"] = payload.captions_enabled
    if payload.subtitle_style is not None:
        updates["subtitle_style"] = payload.subtitle_style.model_dump()
    if payload.subtitles is not None:
        updates["subtitles"] = [c.model_dump() for c in payload.subtitles]

    updated = await db.update_clip(clip_id, updates)
    assert updated is not None
    return serialize_clip(updated)


def _transcribe_video_on_demand(
    video: dict,
    settings: Settings,
) -> tuple[list[dict], str]:
    """Extract WAV and run Faster-Whisper on demand for videos imported without pre-analysis."""
    source_path = get_source_video_path(settings, video["_id"], video["format_ext"])
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source video file missing.")
    wav_path = settings.audio_dir / f"{video['_id']}.wav"
    extract_wav_audio(source_path, wav_path, settings)
    segments, language = transcribe_audio_with_whisper(wav_path, float(video["duration"]), settings)
    return [s.model_dump() for s in segments], language


@router.post("/api/clips/{clip_id}/auto-captions", response_model=ClipOut)
async def regenerate_auto_captions(clip_id: str, request: Request) -> ClipOut:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings
    doc = await db.get_clip(clip_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")

    artifacts = await db.get_analysis_artifacts(doc["video_id"])
    raw_segments = artifacts.get("segments") if artifacts else None
    if not raw_segments:
        video = await db.get_video(doc["video_id"])
        if not video:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent video project not found.")
        if not video.get("has_audio", True):
            raise HTTPException(
                status_code=422,
                detail="This video has no audio track to generate captions from.",
            )
        raw_segments, language = await asyncio.to_thread(_transcribe_video_on_demand, video, settings)
        await db.save_analysis_artifacts(
            doc["video_id"],
            {"language": language, "segments": raw_segments, "scenes": []},
        )
        if not raw_segments:
            raise HTTPException(
                status_code=422,
                detail="No spoken dialogue was detected in this video for auto-captions.",
            )

    segments = [TranscriptSegment.model_validate(s) for s in raw_segments]
    cues = build_subtitle_cues_from_segments(
        segments=segments,
        clip_start=float(doc["trim_start"]),
        clip_end=float(doc["trim_end"]),
    )
    updated = await db.update_clip(
        clip_id,
        {
            "captions_enabled": True,
            "subtitles": [c.model_dump() for c in cues],
        },
    )
    assert updated is not None
    return serialize_clip(updated)


@router.post("/api/clips/{clip_id}/render", response_model=ClipOut)
async def render_clip_endpoint(
    clip_id: str,
    payload: RenderRequestIn,
    request: Request,
) -> ClipOut:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings
    doc = await db.get_clip(clip_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")
    video = await db.get_video(doc["video_id"])
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent video project not found.")

    source_path = get_source_video_path(settings, video["_id"], video["format_ext"])
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source video file missing.")

    target_ar = payload.aspect_ratio or doc.get("aspect_ratio", "9:16")
    out_path, sig, size_bytes = await asyncio.to_thread(
        render_clip_mp4,
        source_path,
        int(video["width"]),
        int(video["height"]),
        bool(video.get("has_audio", True)),
        doc,
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
    updated = await db.update_clip(clip_id, {f"rendered_variants.{v_key}": variant})
    assert updated is not None
    return serialize_clip(updated)


@router.get("/api/clips/{clip_id}/thumbnail")
async def get_clip_thumbnail(clip_id: str, request: Request) -> FileResponse:
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings
    doc = await db.get_clip(clip_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")

    thumb = settings.thumbs_dir / f"{doc['video_id']}_{clip_id}.jpg"
    if not thumb.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip thumbnail not found.")
    return FileResponse(thumb, media_type="image/jpeg")


@router.get("/api/clips/{clip_id}/preview")
async def stream_clip_preview(clip_id: str, request: Request) -> FileResponse:
    """Stream an MP4 preview matching the clip's current trim & aspect ratio (rendered on demand if stale)."""
    db: DatabaseManager = request.app.state.db
    settings: Settings = request.app.state.settings
    doc = await db.get_clip(clip_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found.")
    video = await db.get_video(doc["video_id"])
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent video project not found.")

    aspect_ratio = doc.get("aspect_ratio", "9:16")
    quality = "720p"
    sig = compute_render_signature(doc, quality, aspect_ratio)
    expected_name = f"{doc['video_id']}_{clip_id}_{aspect_ratio.replace(':', 'x')}_{quality}_{sig}.mp4"
    rendered_path = settings.renders_dir / expected_name

    if not rendered_path.exists():
        source_path = get_source_video_path(settings, video["_id"], video["format_ext"])
        if not source_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source video file missing.")
        rendered_path, sig, size_bytes = await asyncio.to_thread(
            render_clip_mp4,
            source_path,
            int(video["width"]),
            int(video["height"]),
            bool(video.get("has_audio", True)),
            doc,
            quality,
            aspect_ratio,
            settings,
        )
        v_key = build_variant_key(quality, aspect_ratio)
        variant = RenderedVariant(
            quality=quality,
            aspect_ratio=aspect_ratio,
            file_name=rendered_path.name,
            file_size_bytes=size_bytes,
            rendered_at=utc_now(),
            signature=sig,
        ).model_dump()
        await db.update_clip(clip_id, {f"rendered_variants.{v_key}": variant})

    return FileResponse(rendered_path, media_type="video/mp4")
