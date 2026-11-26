from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlparse
import uuid

from fastapi import HTTPException, status

from app.core.config import Settings
from app.core.media_tools import VideoMetadata, probe_video, resolve_media_binaries, run_ffmpeg_command
from app.services.render_service import make_safe_filename
from app.services.storage_service import generate_thumbnail

INSTAGRAM_HOSTS = {
    "instagram.com",
    "www.instagram.com",
    "m.instagram.com",
    "instagr.am",
    "www.instagr.am",
}
SHORTCODE_RE = re.compile(r"^[A-Za-z0-9_-]{4,40}$")


@dataclass
class InstagramVideoResult:
    item_id: str
    normalized_url: str
    shortcode: str
    title: str
    author: str
    file_path: Path
    file_name: str
    thumbnail_path: Path
    metadata: VideoMetadata


def validate_instagram_url(raw_url: str) -> tuple[str, str]:
    """Validate an Instagram Reel/Video/Post URL and return (normalized_url, shortcode)."""
    cleaned = raw_url.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please paste an Instagram Reel or video link.",
        )

    parsed = urlparse(cleaned)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in INSTAGRAM_HOSTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a valid Instagram link (e.g. https://www.instagram.com/reel/... or https://www.instagram.com/p/...).",
        )

    segs = [s for s in parsed.path.split("/") if s]
    shortcode: str | None = None
    kind = "reel"

    # Supports /reel/<code>, /reels/<code>, /p/<code>, /tv/<code>, /share/reel/<code>, /<user>/reel/<code>
    for i, seg in enumerate(segs):
        if seg in {"reel", "reels", "p", "tv"} and i + 1 < len(segs) and SHORTCODE_RE.match(segs[i + 1]):
            kind = "reel" if seg == "reels" else seg
            shortcode = segs[i + 1]
            break

    if not shortcode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not find an Instagram Reel or post ID in this link.",
        )

    normalized = f"https://www.instagram.com/{kind}/{shortcode}/"
    return normalized, shortcode


def _classify_instagram_error(exc: Exception) -> tuple[int, str]:
    """Translate raw yt-dlp exceptions into actionable HTTP status codes and clean messages."""
    raw = str(exc)
    cleaned = raw.split("; please report this issue")[0].strip()
    lowered = raw.lower()

    network_markers = (
        "unexpected_eof_while_reading",
        "sslerror",
        "ssleoferror",
        "ssl:",
        "eof occurred in violation of protocol",
        "timed out",
        "connection reset",
        "failed to resolve",
        "connection aborted",
        "network is unreachable",
    )
    if any(marker in lowered for marker in network_markers):
        return (
            status.HTTP_502_BAD_GATEWAY,
            "Unable to establish a secure TLS connection to Instagram from this server's network "
            "(the connection was dropped during the SSL handshake). Confirm instagram.com is reachable "
            "from your current ISP/network (or configure YTDLP_PROXY in backend/.env).",
        )

    auth_markers = ("login required", "use --cookies", "cookies", "rate-limit", "checkpoint")
    if any(marker in lowered for marker in auth_markers):
        return (
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Instagram blocked unauthenticated access or rate-limited this request. "
            "Try again later, or set INSTAGRAM_COOKIES_FILE in backend/.env for authenticated downloads.",
        )

    return (
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        f"Unable to download this Instagram video. Make sure the link is a public Reel or video post. ({cleaned})",
    )


def download_instagram_high_quality(raw_url: str, settings: Settings) -> InstagramVideoResult:
    """Download an Instagram Reel or video in highest available MP4 quality without AI splitting."""
    import yt_dlp

    normalized_url, shortcode = validate_instagram_url(raw_url)
    settings.ensure_dirs()
    bins = resolve_media_binaries(settings)
    item_id = uuid.uuid4().hex[:14]
    out_template = str(settings.instagram_dir / f"{item_id}.%(ext)s")
    target_mp4 = settings.instagram_dir / f"{item_id}.mp4"

    ydl_opts: dict[str, object] = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best",
        "outtmpl": out_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "playlist_items": "1",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "source_address": "0.0.0.0",
        "ffmpeg_location": str(Path(bins.ffmpeg).parent),
    }
    if settings.ytdlp_proxy and settings.ytdlp_proxy.strip():
        ydl_opts["proxy"] = settings.ytdlp_proxy.strip()
    if settings.instagram_cookies_file:
        cookie_path = Path(settings.instagram_cookies_file)
        if cookie_path.is_file():
            ydl_opts["cookiefile"] = str(cookie_path)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(normalized_url, download=True)
    except Exception as exc:
        err_status, detail = _classify_instagram_error(exc)
        raise HTTPException(status_code=err_status, detail=detail) from exc

    if isinstance(info, dict) and "entries" in info and info["entries"]:
        info = next((e for e in info["entries"] if e), info)

    if not target_mp4.exists():
        candidates = [p for p in settings.instagram_dir.glob(f"{item_id}.*") if p.is_file()]
        if not candidates:
            raise HTTPException(
                status_code=422,
                detail="This Instagram post did not contain a downloadable video stream.",
            )
        src_file = candidates[0]
        if src_file.suffix.lower() != ".mp4":
            run_ffmpeg_command(
                [
                    "-y",
                    "-i",
                    str(src_file),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-movflags",
                    "+faststart",
                    str(target_mp4),
                ],
                settings=settings,
            )
            src_file.unlink(missing_ok=True)
        else:
            src_file.rename(target_mp4)

    try:
        metadata = probe_video(target_mp4, settings)
    except ValueError as exc:
        target_mp4.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Downloaded Instagram file is not a valid video: {exc}") from exc

    thumb_path = settings.thumbs_dir / f"ig_{item_id}.jpg"
    generate_thumbnail(
        target_mp4,
        thumb_path,
        min(max(metadata.duration * 0.15, 0.2), max(0.2, metadata.duration * 0.5)),
        settings,
    )

    raw_title = (info.get("title") if isinstance(info, dict) else None) or f"Instagram Reel {shortcode}"
    author = (
        (info.get("uploader") or info.get("channel") or "Instagram Creator")
        if isinstance(info, dict)
        else "Instagram Creator"
    )
    safe_name = make_safe_filename(str(raw_title))
    download_name = f"{safe_name}_{shortcode}_{metadata.height}p.mp4"

    return InstagramVideoResult(
        item_id=item_id,
        normalized_url=normalized_url,
        shortcode=shortcode,
        title=str(raw_title).strip()[:140] or f"Instagram Reel {shortcode}",
        author=str(author).strip()[:80],
        file_path=target_mp4,
        file_name=download_name,
        thumbnail_path=thumb_path,
        metadata=metadata,
    )
