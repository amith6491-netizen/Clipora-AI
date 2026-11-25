"""FastAPI route modules and serialization helpers."""
from typing import Any

from app.models.schemas import ClipOut, ExportRecordOut, VideoProjectOut


def serialize_video(doc: dict[str, Any]) -> VideoProjectOut:
    vid = str(doc["_id"])
    return VideoProjectOut(
        id=vid,
        title=doc["title"],
        original_filename=doc["original_filename"],
        format_ext=doc["format_ext"],
        size_bytes=int(doc["size_bytes"]),
        duration=float(doc["duration"]),
        width=int(doc["width"]),
        height=int(doc["height"]),
        fps=float(doc["fps"]),
        has_audio=bool(doc.get("has_audio", True)),
        source_type=doc.get("source_type", "upload"),
        youtube_url=doc.get("youtube_url"),
        status=doc["status"],
        progress=float(doc.get("progress", 0.0)),
        current_stage=doc.get("current_stage", "uploaded"),
        error_message=doc.get("error_message"),
        target_shorts_count=int(doc.get("target_shorts_count", 10)),
        default_aspect_ratio=doc.get("default_aspect_ratio", "9:16"),
        default_quality=doc.get("default_quality", "1080p"),
        pipeline_steps=doc.get("pipeline_steps", []),
        analysis_summary=doc.get("analysis_summary", {}),
        poster_url=f"/api/videos/{vid}/poster",
        source_url=f"/api/videos/{vid}/source",
        clips_count=int(doc.get("clips_count", 0)),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def serialize_clip(doc: dict[str, Any]) -> ClipOut:
    cid = str(doc["_id"])
    return ClipOut(
        id=cid,
        video_id=str(doc["video_id"]),
        index=int(doc["index"]),
        title=doc["title"],
        category=doc["category"],
        secondary_categories=doc.get("secondary_categories", []),
        engagement_score=float(doc["engagement_score"]),
        score_breakdown=doc["score_breakdown"],
        ai_reason=doc["ai_reason"],
        transcript_text=doc["transcript_text"],
        original_start=float(doc["original_start"]),
        original_end=float(doc["original_end"]),
        trim_start=float(doc["trim_start"]),
        trim_end=float(doc["trim_end"]),
        duration=float(doc["duration"]),
        aspect_ratio=doc.get("aspect_ratio", "9:16"),
        captions_enabled=bool(doc.get("captions_enabled", True)),
        subtitle_style=doc.get("subtitle_style", {}),
        subtitles=doc.get("subtitles", []),
        rendered_variants=doc.get("rendered_variants", {}),
        thumbnail_url=f"/api/clips/{cid}/thumbnail",
        preview_url=f"/api/clips/{cid}/preview",
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def serialize_export(doc: dict[str, Any]) -> ExportRecordOut:
    eid = str(doc["_id"])
    return ExportRecordOut(
        id=eid,
        video_id=str(doc["video_id"]),
        kind=doc["kind"],
        quality=doc["quality"],
        file_name=doc["file_name"],
        file_size_bytes=int(doc["file_size_bytes"]),
        clip_count=int(doc["clip_count"]),
        download_url=doc["download_url"],
        created_at=doc["created_at"],
    )
