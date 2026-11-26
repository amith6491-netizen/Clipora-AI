import asyncio
from collections import defaultdict
from pathlib import Path
import threading
from typing import Any
import uuid

from app.core.cancellation import ProcessingCancelledError, raise_if_cancelled
from app.core.config import Settings
from app.core.database import DatabaseManager, utc_now
from app.models.schemas import (
    AnalysisSummary,
    AspectRatio,
    ExportQuality,
    PipelineStep,
    RenderedVariant,
    SubtitleStyle,
)
from app.services.storage_service import generate_thumbnail, get_source_video_path

PIPELINE_STEP_DEFS: list[tuple[str, str]] = [
    ("audio_extract", "Extracting Audio Track"),
    ("transcribe", "Transcribing Speech (Faster-Whisper)"),
    ("scene_detect", "Detecting Scenes & Visual Dynamics (PySceneDetect + OpenCV)"),
    ("audio_analysis", "Analyzing Acoustic Energy & Excitement"),
    ("nlp_ranking", "Understanding Conversations & Ranking Moments (NLP)"),
    ("generate_clips", "Generating 10–20s Shorts & Auto-Captions"),
    ("render_hd", "Rendering HD MP4 Shorts (FFmpeg)"),
]

YOUTUBE_PIPELINE_STEP_DEFS: list[tuple[str, str]] = [
    ("youtube_download", "Importing Video from YouTube (yt-dlp)"),
    *PIPELINE_STEP_DEFS,
]

STAGE_WEIGHTS = {
    "youtube_download": (0.0, 10.0),
    "audio_extract": (10.0, 16.0),
    "transcribe": (16.0, 46.0),
    "scene_detect": (46.0, 64.0),
    "audio_analysis": (64.0, 74.0),
    "nlp_ranking": (74.0, 85.0),
    "generate_clips": (85.0, 91.0),
    "render_hd": (91.0, 100.0),
}


def initial_pipeline_steps(include_youtube: bool = False) -> list[dict[str, Any]]:
    step_defs = YOUTUBE_PIPELINE_STEP_DEFS if include_youtube else PIPELINE_STEP_DEFS
    return [
        PipelineStep(key=key, label=label, status="pending", progress=0.0, detail="Waiting").model_dump()
        for key, label in step_defs
    ]


class PipelineEventBroker:
    """In-memory pub/sub for real-time Server-Sent Events (SSE) progress updates."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def subscribe(self, video_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[video_id].add(queue)
        return queue

    def unsubscribe(self, video_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers[video_id].discard(queue)
        if not self._subscribers[video_id]:
            self._subscribers.pop(video_id, None)

    def publish(self, video_id: str, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(video_id, set())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except Exception:
                    pass


event_broker = PipelineEventBroker()
_active_tasks: dict[str, asyncio.Task[None]] = {}
_cancel_flags: dict[str, threading.Event] = {}


def start_video_processing(
    video_id: str,
    db: DatabaseManager,
    settings: Settings,
) -> None:
    """Launch background AI processing task for a video if not already running."""
    existing = _active_tasks.get(video_id)
    if existing and not existing.done():
        return

    cancel_event = threading.Event()
    _cancel_flags[video_id] = cancel_event
    task = asyncio.create_task(_run_pipeline(video_id, db, settings, cancel_event))
    _active_tasks[video_id] = task

    def _cleanup(_t: asyncio.Task[None]) -> None:
        if _active_tasks.get(video_id) is _t:
            _active_tasks.pop(video_id, None)
        if _cancel_flags.get(video_id) is cancel_event:
            _cancel_flags.pop(video_id, None)

    task.add_done_callback(_cleanup)


async def cancel_video_processing(
    video_id: str,
    db: DatabaseManager,
    wait_for_cleanup: bool = False,
) -> dict[str, Any] | None:
    """Signal an active pipeline job to abort and persist cancelled state immediately."""
    flag = _cancel_flags.get(video_id)
    if flag is not None:
        flag.set()

    doc = await db.get_video(video_id)
    if doc and doc.get("status") in ("queued", "processing"):
        steps = list(doc.get("pipeline_steps") or [])
        now = utc_now()
        for step in steps:
            if step.get("status") == "running":
                step["status"] = "cancelled"
                step["detail"] = "Cancelled by user"
                step["completed_at"] = now

        await db.update_video(
            video_id,
            {
                "status": "cancelled",
                "error_message": None,
                "pipeline_steps": steps,
            },
        )
        event_broker.publish(
            video_id,
            {
                "video_id": video_id,
                "status": "cancelled",
                "progress": float(doc.get("progress", 0.0)),
                "current_stage": doc.get("current_stage", "cancelled"),
                "detail": "Processing cancelled by user",
                "pipeline_steps": [
                    {
                        **s,
                        "started_at": s["started_at"].isoformat() if hasattr(s.get("started_at"), "isoformat") else s.get("started_at"),
                        "completed_at": s["completed_at"].isoformat() if hasattr(s.get("completed_at"), "isoformat") else s.get("completed_at"),
                    }
                    for s in steps
                ],
                "error_message": None,
            },
        )

    if wait_for_cleanup:
        task = _active_tasks.get(video_id)
        if task is not None and not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=4.0)
            except Exception:
                pass

    return await db.get_video(video_id)


async def _run_pipeline(
    video_id: str,
    db: DatabaseManager,
    settings: Settings,
    cancel_event: threading.Event,
) -> None:
    video_doc = await db.get_video(video_id)
    if not video_doc:
        return

    loop = asyncio.get_running_loop()
    is_youtube = video_doc.get("source_type") == "youtube"
    steps = initial_pipeline_steps(include_youtube=is_youtube)
    step_idx_map = {s["key"]: i for i, s in enumerate(steps)}
    current_stage = "youtube_download" if is_youtube else "audio_extract"

    async def sync_progress(
        stage_key: str,
        step_status: str,
        step_progress: float,
        detail: str,
        overall_status: str = "processing",
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        if cancel_event.is_set() and overall_status not in ("cancelled",):
            raise ProcessingCancelledError("Processing cancelled by user.")

        idx = step_idx_map[stage_key]
        step = steps[idx]
        if step_status == "running" and step.get("started_at") is None:
            step["started_at"] = utc_now()
        if step_status in ("completed", "failed", "cancelled"):
            step["completed_at"] = utc_now()
        step["status"] = step_status
        step["progress"] = round(min(100.0, max(0.0, step_progress)), 1)
        step["detail"] = detail

        lo, hi = STAGE_WEIGHTS[stage_key]
        overall_progress = round(lo + (hi - lo) * (step["progress"] / 100.0), 1)
        if overall_status == "completed":
            overall_progress = 100.0
        elif overall_status == "cancelled":
            current_doc = await db.get_video(video_id)
            if current_doc:
                overall_progress = float(current_doc.get("progress", overall_progress))

        update_payload: dict[str, Any] = {
            "status": overall_status,
            "progress": overall_progress,
            "current_stage": stage_key,
            "pipeline_steps": steps,
            **(extra_fields or {}),
        }
        await db.update_video(video_id, update_payload)
        event_broker.publish(
            video_id,
            {
                "video_id": video_id,
                "status": overall_status,
                "progress": overall_progress,
                "current_stage": stage_key,
                "detail": detail,
                "pipeline_steps": [
                    {
                        **s,
                        "started_at": s["started_at"].isoformat() if s.get("started_at") else None,
                        "completed_at": s["completed_at"].isoformat() if s.get("completed_at") else None,
                    }
                    for s in steps
                ],
                "error_message": update_payload.get("error_message"),
            },
        )

    def make_thread_callback(stage_key: str):
        last_sent = {"pct": -10.0}

        def _cb(pct: float, detail: str) -> None:
            raise_if_cancelled(cancel_event)
            if pct - last_sent["pct"] < 5.0 and pct < 99.0:
                return
            last_sent["pct"] = pct
            fut = asyncio.run_coroutine_threadsafe(
                sync_progress(stage_key, "running", pct, detail),
                loop,
            )
            try:
                fut.result(timeout=5)
            except Exception:
                pass

        return _cb

    try:
        from app.services.audio_service import analyze_audio_dynamics, extract_wav_audio
        from app.services.ranking_service import select_and_rank_shorts
        from app.services.render_service import build_variant_key, render_clip_mp4
        from app.services.scene_service import detect_scenes_and_visual_dynamics
        from app.services.transcription_service import (
            build_subtitle_cues_from_segments,
            transcribe_audio_with_whisper,
        )
        from app.services.youtube_service import download_youtube_video

        source_path = get_source_video_path(settings, video_id, video_doc["format_ext"])
        if is_youtube:
            current_stage = "youtube_download"
            if not source_path.exists():
                await sync_progress("youtube_download", "running", 3.0, "Connecting to YouTube via yt-dlp")
                yt_url = video_doc.get("youtube_url")
                if not yt_url:
                    raise RuntimeError("Missing YouTube source URL on project record.")
                downloaded_path, yt_meta = await asyncio.to_thread(
                    download_youtube_video,
                    yt_url,
                    video_id,
                    settings,
                    make_thread_callback("youtube_download"),
                    cancel_event,
                )
                source_path = downloaded_path
                await db.update_video(
                    video_id,
                    {
                        "format_ext": downloaded_path.suffix.lower(),
                        "size_bytes": yt_meta.size_bytes,
                        "duration": round(yt_meta.duration, 3),
                        "width": yt_meta.width,
                        "height": yt_meta.height,
                        "fps": yt_meta.fps,
                        "has_audio": yt_meta.has_audio,
                    },
                )
                video_doc["format_ext"] = downloaded_path.suffix.lower()
                video_doc["duration"] = round(yt_meta.duration, 3)
                video_doc["width"] = yt_meta.width
                video_doc["height"] = yt_meta.height
                video_doc["has_audio"] = yt_meta.has_audio
            await sync_progress("youtube_download", "completed", 100.0, "YouTube video downloaded and validated")

        if not source_path.exists():
            raise FileNotFoundError(f"Source video file missing at {source_path}")

        duration = float(video_doc["duration"])
        has_audio = bool(video_doc.get("has_audio", True))
        src_width = int(video_doc["width"])
        src_height = int(video_doc["height"])
        default_ar: AspectRatio = video_doc.get("default_aspect_ratio", "9:16")
        default_quality: ExportQuality = video_doc.get("default_quality", "720p")
        target_shorts = int(video_doc.get("target_shorts_count", 10))

        # 1. Extract Audio
        raise_if_cancelled(cancel_event)
        current_stage = "audio_extract"
        await sync_progress("audio_extract", "running", 15.0, "Extracting 16kHz mono WAV audio stream via FFmpeg")
        wav_path = settings.audio_dir / f"{video_id}.wav"
        if has_audio:
            await asyncio.to_thread(extract_wav_audio, source_path, wav_path, settings, cancel_event)
            await sync_progress("audio_extract", "completed", 100.0, "Audio extracted successfully")
        else:
            await sync_progress("audio_extract", "completed", 100.0, "Source video has no audio track; proceeding with visual analysis")

        # 2. Transcribe via Faster-Whisper
        raise_if_cancelled(cancel_event)
        current_stage = "transcribe"
        await sync_progress("transcribe", "running", 3.0, f"Loading Faster-Whisper ({settings.whisper_model_size}) model")
        if has_audio and wav_path.exists():
            segments, detected_lang = await asyncio.to_thread(
                transcribe_audio_with_whisper,
                wav_path,
                duration,
                settings,
                make_thread_callback("transcribe"),
                cancel_event,
            )
        else:
            segments, detected_lang = [], "en"
        word_count = sum(len(s.words) if s.words else len(s.text.split()) for s in segments)
        await sync_progress(
            "transcribe",
            "completed",
            100.0,
            f"Transcribed {len(segments)} segments ({word_count} words, lang={detected_lang})",
        )

        # 3. Scene Detection & OpenCV Visual Analysis
        raise_if_cancelled(cancel_event)
        current_stage = "scene_detect"
        await sync_progress("scene_detect", "running", 5.0, "Running PySceneDetect content detector")
        visual_profile = await asyncio.to_thread(
            detect_scenes_and_visual_dynamics,
            source_path,
            duration,
            make_thread_callback("scene_detect"),
            cancel_event,
        )
        await sync_progress(
            "scene_detect",
            "completed",
            100.0,
            f"Detected {len(visual_profile.scenes)} scenes & tracked speaker framing",
        )

        # 4. Audio Excitement Analysis
        raise_if_cancelled(cancel_event)
        current_stage = "audio_analysis"
        await sync_progress("audio_analysis", "running", 20.0, "Computing RMS energy, spectral flux & speech peaks")
        audio_profile = (
            await asyncio.to_thread(analyze_audio_dynamics, wav_path)
            if has_audio and wav_path.exists()
            else None
        )
        peak_moments = audio_profile.peak_count if audio_profile else 0
        avg_energy = round(audio_profile.avg_energy, 3) if audio_profile else 0.0
        await sync_progress(
            "audio_analysis",
            "completed",
            100.0,
            f"Identified {peak_moments} high-energy acoustic peaks",
        )

        # 5. NLP Understanding & Multimodal Ranking
        raise_if_cancelled(cancel_event)
        current_stage = "nlp_ranking"
        await sync_progress("nlp_ranking", "running", 25.0, "Running transformer NLP embeddings, TF-IDF & multimodal ranking")
        ranked_clips, windows_evaluated = await asyncio.to_thread(
            select_and_rank_shorts,
            segments,
            audio_profile,
            visual_profile,
            duration,
            target_shorts,
            settings,
        )
        if not ranked_clips:
            raise RuntimeError("Unable to identify valid 10–20 second clips from this video.")

        await sync_progress(
            "nlp_ranking",
            "completed",
            100.0,
            f"Ranked {windows_evaluated} candidate windows -> selected top {len(ranked_clips)} non-overlapping shorts",
        )

        # Persist full analysis artifacts in MongoDB
        await db.save_analysis_artifacts(
            video_id,
            {
                "language": detected_lang,
                "segments": [s.model_dump() for s in segments],
                "scenes": [{"start": sc.start, "end": sc.end} for sc in visual_profile.scenes],
            },
        )

        # 6. Build Clip Docs, Subtitles & Thumbnails
        current_stage = "generate_clips"
        await sync_progress("generate_clips", "running", 15.0, "Generating word-aligned captions and clip thumbnails")
        now = utc_now()
        clip_docs: list[dict[str, Any]] = []
        default_style = SubtitleStyle().model_dump()

        for rank_idx, cand in enumerate(ranked_clips, start=1):
            raise_if_cancelled(cancel_event)
            clip_id = uuid.uuid4().hex[:12]
            cues = build_subtitle_cues_from_segments(segments, cand.start, cand.end)
            thumb_path = settings.thumbs_dir / f"{video_id}_{clip_id}.jpg"
            await asyncio.to_thread(
                generate_thumbnail,
                source_path,
                thumb_path,
                min(cand.end - 0.2, cand.start + min(2.0, cand.duration * 0.25)),
                settings,
                cancel_event,
            )

            clip_docs.append(
                {
                    "_id": clip_id,
                    "video_id": video_id,
                    "index": rank_idx,
                    "title": cand.title,
                    "category": cand.category,
                    "secondary_categories": cand.secondary_categories,
                    "engagement_score": cand.engagement_score,
                    "score_breakdown": cand.score_breakdown.model_dump(),
                    "ai_reason": cand.ai_reason,
                    "transcript_text": cand.text,
                    "original_start": cand.start,
                    "original_end": cand.end,
                    "trim_start": cand.start,
                    "trim_end": cand.end,
                    "duration": round(cand.end - cand.start, 3),
                    "preferred_crop_x_ratio": cand.preferred_crop_x_ratio,
                    "aspect_ratio": default_ar,
                    "captions_enabled": True,
                    "subtitle_style": default_style,
                    "subtitles": [c.model_dump() for c in cues],
                    "rendered_variants": {},
                    "created_at": now,
                    "updated_at": now,
                }
            )

        await db.replace_clips_for_video(video_id, clip_docs)
        await sync_progress(
            "generate_clips",
            "completed",
            100.0,
            f"Prepared {len(clip_docs)} clips with synchronized captions",
        )

        # 7. Render HD MP4 Shorts via FFmpeg
        current_stage = "render_hd"
        total_clips = len(clip_docs)
        for idx, clip_doc in enumerate(clip_docs, start=1):
            raise_if_cancelled(cancel_event)
            await sync_progress(
                "render_hd",
                "running",
                ((idx - 1) / total_clips) * 100.0,
                f"Rendering HD short {idx}/{total_clips}: {clip_doc['title']}",
            )
            out_path, sig, size_bytes = await asyncio.to_thread(
                render_clip_mp4,
                source_path,
                src_width,
                src_height,
                has_audio,
                clip_doc,
                default_quality,
                default_ar,
                settings,
                cancel_event,
            )
            v_key = build_variant_key(default_quality, default_ar)
            variant = RenderedVariant(
                quality=default_quality,
                aspect_ratio=default_ar,
                file_name=out_path.name,
                file_size_bytes=size_bytes,
                rendered_at=utc_now(),
                signature=sig,
            ).model_dump()
            await db.update_clip(
                clip_doc["_id"],
                {f"rendered_variants.{v_key}": variant},
            )

        summary = AnalysisSummary(
            language=detected_lang,
            word_count=word_count,
            segment_count=len(segments),
            scene_count=len(visual_profile.scenes),
            avg_audio_energy=avg_energy,
            peak_audio_moments=peak_moments,
            candidate_windows_evaluated=windows_evaluated,
            shorts_generated=len(clip_docs),
        ).model_dump()

        await sync_progress(
            "render_hd",
            "completed",
            100.0,
            f"All {len(clip_docs)} HD shorts rendered and ready for editing & download",
            overall_status="completed",
            extra_fields={
                "analysis_summary": summary,
                "clips_count": len(clip_docs),
                "error_message": None,
            },
        )
    except (ProcessingCancelledError, asyncio.CancelledError):
        await sync_progress(
            current_stage,
            "cancelled",
            0.0,
            "Cancelled by user",
            overall_status="cancelled",
            extra_fields={"error_message": None},
        )
    except Exception as exc:
        if cancel_event.is_set():
            await sync_progress(
                current_stage,
                "cancelled",
                0.0,
                "Cancelled by user",
                overall_status="cancelled",
                extra_fields={"error_message": None},
            )
            return
        err_msg = str(exc) or exc.__class__.__name__
        await sync_progress(
            current_stage,
            "failed",
            0.0,
            f"Failed: {err_msg}",
            overall_status="failed",
            extra_fields={"error_message": err_msg},
        )
