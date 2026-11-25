from dataclasses import dataclass
from pathlib import Path
import re
import threading
from typing import Callable
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException, status

from app.core.cancellation import raise_if_cancelled
from app.core.config import Settings
from app.core.media_tools import VideoMetadata, probe_video, resolve_media_binaries
from app.services.storage_service import format_duration_hms, generate_thumbnail, get_poster_path

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")


@dataclass
class YouTubeMetadata:
    url: str
    video_key: str
    title: str
    channel: str
    duration: float
    thumbnail_url: str | None
    valid_duration: bool
    validation_message: str | None


def validate_youtube_url(raw_url: str) -> tuple[str, str]:
    """Validate that the URL is a valid YouTube video URL and return (normalized_url, video_key)."""
    cleaned = raw_url.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please paste a YouTube video link.")

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in YOUTUBE_HOSTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a valid YouTube link (e.g. https://www.youtube.com/watch?v=... or https://youtu.be/...).",
        )

    host = (parsed.hostname or "").lower()
    video_key: str | None = None
    if "youtu.be" in host:
        part = parsed.path.strip("/").split("/")[0]
        if VIDEO_ID_RE.match(part):
            video_key = part
    else:
        qs = parse_qs(parsed.query)
        if qs.get("v") and VIDEO_ID_RE.match(qs["v"][0]):
            video_key = qs["v"][0]
        else:
            segs = [s for s in parsed.path.split("/") if s]
            if len(segs) >= 2 and segs[0] in {"shorts", "live", "embed"} and VIDEO_ID_RE.match(segs[1]):
                video_key = segs[1]

    if not video_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not identify a YouTube video ID in this URL.",
        )

    normalized = f"https://www.youtube.com/watch?v={video_key}"
    return normalized, video_key


def fetch_youtube_metadata(raw_url: str, settings: Settings) -> YouTubeMetadata:
    """Inspect YouTube video metadata and duration without downloading the full stream."""
    import yt_dlp

    normalized_url, video_key = validate_youtube_url(raw_url)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(normalized_url, download=False)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unable to read YouTube video metadata: {exc}",
        ) from exc

    if not info:
        raise HTTPException(status_code=422, detail="Could not retrieve metadata for this YouTube video.")

    if info.get("is_live"):
        raise HTTPException(
            status_code=422,
            detail="Active YouTube live streams are not supported. Please use a finished video under 20 minutes.",
        )

    duration = float(info.get("duration") or 0.0)
    if duration <= 0:
        raise HTTPException(status_code=422, detail="Could not determine the duration of this YouTube video.")

    min_dur = settings.min_video_duration_seconds
    max_dur = settings.max_video_duration_seconds
    valid = min_dur <= duration <= max_dur
    msg = None
    if not valid:
        msg = (
            f"YouTube video duration is {format_duration_hms(duration)} ({duration:.0f}s). "
            f"Videos must be under {format_duration_hms(max_dur)} (at least {format_duration_hms(min_dur)})."
        )

    return YouTubeMetadata(
        url=normalized_url,
        video_key=video_key,
        title=str(info.get("title") or f"YouTube Video {video_key}")[:120],
        channel=str(info.get("channel") or info.get("uploader") or "YouTube"),
        duration=duration,
        thumbnail_url=info.get("thumbnail"),
        valid_duration=valid,
        validation_message=msg,
    )


def download_youtube_video(
    normalized_url: str,
    video_id: str,
    settings: Settings,
    progress_callback: Callable[[float, str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> tuple[Path, VideoMetadata]:
    """Download a validated YouTube video as MP4 using yt-dlp + FFmpeg and probe metadata."""
    import yt_dlp

    raise_if_cancelled(cancel_event)
    settings.ensure_dirs()
    bins = resolve_media_binaries(settings)
    out_template = str(settings.uploads_dir / f"{video_id}.%(ext)s")
    target_mp4 = settings.uploads_dir / f"{video_id}.mp4"

    def _hook(d: dict) -> None:
        raise_if_cancelled(cancel_event)
        if progress_callback is None:
            return
        status_str = d.get("status")
        if status_str == "downloading":
            total = float(d.get("total_bytes") or d.get("total_bytes_estimate") or 0.0)
            downloaded = float(d.get("downloaded_bytes") or 0.0)
            if total > 0:
                pct = min(92.0, max(3.0, (downloaded / total) * 90.0))
                mb_done = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                progress_callback(pct, f"Downloading YouTube video: {mb_done:.1f} / {mb_total:.1f} MB")
            else:
                progress_callback(25.0, "Downloading YouTube video stream…")
        elif status_str == "finished":
            progress_callback(94.0, "Merging video and audio streams with FFmpeg…")

    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/bestvideo[height<=1080]+bestaudio/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": str(Path(bins.ffmpeg).parent),
        "progress_hooks": [_hook],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([normalized_url])

    if not target_mp4.exists():
        # Fallback if yt-dlp produced another container
        candidates = list(settings.uploads_dir.glob(f"{video_id}.*"))
        if not candidates:
            raise RuntimeError("YouTube download completed without producing a media file.")
        target_mp4 = candidates[0]

    metadata = probe_video(target_mp4, settings)
    poster_path = get_poster_path(settings, video_id)
    generate_thumbnail(
        target_mp4,
        poster_path,
        min(max(metadata.duration * 0.1, 1.0), metadata.duration * 0.5),
        settings,
    )
    if progress_callback:
        progress_callback(100.0, "YouTube video imported successfully")
    return target_mp4, metadata
