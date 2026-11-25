from pathlib import Path
import shutil
import threading
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings
from app.core.media_tools import VideoMetadata, probe_video, run_ffmpeg_command

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
CHUNK_SIZE_BYTES = 1024 * 1024


def format_duration_hms(seconds: float) -> str:
    total = int(round(seconds))
    mins, secs = divmod(total, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs}h {mins}m {secs}s"
    return f"{mins}m {secs}s"


def get_source_video_path(settings: Settings, video_id: str, ext: str) -> Path:
    return settings.uploads_dir / f"{video_id}{ext}"


def get_poster_path(settings: Settings, video_id: str) -> Path:
    return settings.thumbs_dir / f"{video_id}_poster.jpg"


async def save_and_validate_upload(
    file: UploadFile,
    settings: Settings,
) -> tuple[str, Path, str, VideoMetadata]:
    """Stream upload to disk, validate format & duration, and generate a poster frame."""
    settings.ensure_dirs()
    original_name = file.filename or "upload.mp4"
    ext = Path(original_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported video format '{ext or 'unknown'}'. "
                "Supported formats: MP4, MOV, MKV, and WebM."
            ),
        )

    video_id = uuid.uuid4().hex
    target_path = get_source_video_path(settings, video_id, ext)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    written_bytes = 0

    try:
        with target_path.open("wb") as out_fp:
            while True:
                chunk = await file.read(CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                written_bytes += len(chunk)
                if written_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Uploaded file exceeds maximum allowed size of {settings.max_upload_size_mb} MB.",
                    )
                out_fp.write(chunk)

        if written_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded video file is empty.",
            )

        try:
            metadata = probe_video(target_path, settings)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        min_dur = settings.min_video_duration_seconds
        max_dur = settings.max_video_duration_seconds
        if metadata.duration < min_dur or metadata.duration > max_dur:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Video duration is {format_duration_hms(metadata.duration)} "
                    f"({metadata.duration:.1f}s). Uploaded videos must be under "
                    f"{format_duration_hms(max_dur)} (at least {format_duration_hms(min_dur)})."
                ),
            )

        poster_path = get_poster_path(settings, video_id)
        generate_thumbnail(target_path, poster_path, min(max(metadata.duration * 0.1, 1.0), metadata.duration * 0.5), settings)
        return video_id, target_path, ext, metadata
    except Exception:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


def generate_thumbnail(
    video_path: Path,
    output_path: Path,
    timestamp_sec: float,
    settings: Settings,
    cancel_event: threading.Event | None = None,
) -> Path:
    """Capture a crisp JPEG thumbnail at the given timestamp."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg_command(
        [
            "-y",
            "-ss",
            f"{max(0.0, timestamp_sec):.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=640:-2",
            "-q:v",
            "3",
            str(output_path),
        ],
        settings=settings,
        cancel_event=cancel_event,
    )
    return output_path


def delete_video_files(settings: Settings, video_id: str, ext: str | None = None) -> None:
    """Remove all stored source, audio, thumbnail, render, and export artifacts for a video."""
    if ext:
        get_source_video_path(settings, video_id, ext).unlink(missing_ok=True)
    else:
        for candidate in settings.uploads_dir.glob(f"{video_id}.*"):
            candidate.unlink(missing_ok=True)

    for folder, pattern in (
        (settings.audio_dir, f"{video_id}*"),
        (settings.thumbs_dir, f"{video_id}*"),
        (settings.subtitles_dir, f"{video_id}*"),
        (settings.renders_dir, f"{video_id}*"),
        (settings.exports_dir, f"{video_id}*"),
    ):
        for match in folder.glob(pattern):
            if match.is_dir():
                shutil.rmtree(match, ignore_errors=True)
            else:
                match.unlink(missing_ok=True)
