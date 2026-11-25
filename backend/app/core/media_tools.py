from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Sequence

from app.core.cancellation import ProcessingCancelledError, raise_if_cancelled
from app.core.config import Settings


@dataclass(frozen=True)
class MediaBinaries:
    ffmpeg: str
    ffprobe: str


@dataclass(frozen=True)
class VideoMetadata:
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None
    has_audio: bool
    format_name: str
    size_bytes: int


_cached_binaries: MediaBinaries | None = None


def resolve_media_binaries(settings: Settings | None = None) -> MediaBinaries:
    """Resolve FFmpeg and FFprobe binaries from config, PATH, or static-ffmpeg."""
    global _cached_binaries
    if _cached_binaries is not None:
        return _cached_binaries

    ffmpeg_bin = settings.ffmpeg_path if settings and settings.ffmpeg_path else shutil.which("ffmpeg")
    ffprobe_bin = settings.ffprobe_path if settings and settings.ffprobe_path else shutil.which("ffprobe")

    if not ffmpeg_bin or not ffprobe_bin:
        try:
            import static_ffmpeg.run  # type: ignore

            sf_ffmpeg, sf_ffprobe = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
            ffmpeg_bin = ffmpeg_bin or sf_ffmpeg
            ffprobe_bin = ffprobe_bin or sf_ffprobe
        except Exception as exc:
            raise RuntimeError(
                "FFmpeg/FFprobe binaries were not found on PATH and static-ffmpeg could not provide them. "
                "Install FFmpeg and ensure ffmpeg and ffprobe are in PATH."
            ) from exc

    _cached_binaries = MediaBinaries(ffmpeg=str(ffmpeg_bin), ffprobe=str(ffprobe_bin))
    return _cached_binaries


def reset_media_binary_cache() -> None:
    global _cached_binaries
    _cached_binaries = None


def _parse_fps(rate_str: str | None) -> float:
    if not rate_str or rate_str == "0/0":
        return 30.0
    if "/" in rate_str:
        num, den = rate_str.split("/", 1)
        try:
            d = float(den)
            return round(float(num) / d, 3) if d != 0 else 30.0
        except ValueError:
            return 30.0
    try:
        return round(float(rate_str), 3)
    except ValueError:
        return 30.0


def probe_video(file_path: Path, settings: Settings | None = None) -> VideoMetadata:
    """Extract authoritative media stream metadata using ffprobe."""
    bins = resolve_media_binaries(settings)
    cmd = [
        bins.ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ValueError(f"Invalid or unreadable media file: {proc.stderr.strip() or 'ffprobe failed'}")

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Failed to parse ffprobe metadata output") from exc

    streams = payload.get("streams", [])
    fmt = payload.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise ValueError("Uploaded file does not contain a valid video stream")

    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration_raw = fmt.get("duration") or video_stream.get("duration")
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Could not determine video duration") from exc

    if duration <= 0:
        raise ValueError("Video duration must be greater than zero")

    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ValueError("Invalid video frame dimensions")

    fps = _parse_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))
    size_bytes = int(fmt.get("size") or file_path.stat().st_size)

    return VideoMetadata(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        video_codec=str(video_stream.get("codec_name") or "unknown"),
        audio_codec=str(audio_stream.get("codec_name")) if audio_stream else None,
        has_audio=audio_stream is not None,
        format_name=str(fmt.get("format_name") or ""),
        size_bytes=size_bytes,
    )


def run_ffmpeg_command(
    args: Sequence[str],
    settings: Settings | None = None,
    cwd: Path | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    """Run an FFmpeg command with optional cancellation support and raise on failure."""
    raise_if_cancelled(cancel_event)
    bins = resolve_media_binaries(settings)
    cmd = [bins.ffmpeg, "-hide_banner", "-loglevel", "error", *args]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    try:
        while proc.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2.0)
                raise ProcessingCancelledError("FFmpeg operation cancelled by user.")
            time.sleep(0.15)
        stdout, stderr = proc.communicate()
    except ProcessingCancelledError:
        raise
    except Exception:
        if proc.poll() is None:
            proc.kill()
        raise

    if proc.returncode != 0:
        detail = (stderr or "").strip() or (stdout or "").strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"FFmpeg command failed: {detail}")
