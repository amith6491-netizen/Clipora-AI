from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from typing import Any
import zipfile

from app.core.config import Settings
from app.core.media_tools import run_ffmpeg_command
from app.models.schemas import AspectRatio, ExportQuality, SubtitleCue, SubtitleStyle

RESOLUTION_MAP: dict[tuple[AspectRatio, ExportQuality], tuple[int, int]] = {
    ("9:16", "720p"): (720, 1280),
    ("9:16", "1080p"): (1080, 1920),
    ("16:9", "720p"): (1280, 720),
    ("16:9", "1080p"): (1920, 1080),
    ("1:1", "720p"): (720, 720),
    ("1:1", "1080p"): (1080, 1080),
}


def hex_to_ass_color(hex_color: str, opacity: float = 1.0) -> str:
    """Convert #RRGGBB + opacity [0..1] to ASS &HAABBGGRR format (00=opaque, FF=transparent)."""
    clean = hex_color.lstrip("#")
    if len(clean) != 6:
        clean = "FFFFFF"
    rr = clean[0:2].upper()
    gg = clean[2:4].upper()
    bb = clean[4:6].upper()
    alpha = int(round((1.0 - max(0.0, min(1.0, opacity))) * 255.0))
    return f"&H{alpha:02X}{bb}{gg}{rr}"


def _format_ass_timestamp(seconds: float) -> str:
    sec = max(0.0, seconds)
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    rem = sec % 60
    whole_secs = int(rem)
    centis = int(round((rem - whole_secs) * 100))
    if centis >= 100:
        whole_secs += 1
        centis -= 100
    return f"{hrs}:{mins:02d}:{whole_secs:02d}.{centis:02d}"


def _escape_ass_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def generate_ass_subtitle_file(
    cues: list[SubtitleCue],
    style: SubtitleStyle,
    trim_start: float,
    trim_end: float,
    target_width: int,
    target_height: int,
    output_ass_path: Path,
) -> Path:
    """Build an Advanced SubStation Alpha (.ass) subtitle file calibrated to the output canvas."""
    scale_factor = target_height / 1280.0
    font_size = max(18, int(round(style.font_size * scale_factor * (1.15 if target_width >= target_height else 1.35))))

    alignment = {"bottom": 2, "center": 5, "top": 8}[style.position]
    margin_v = int(round(target_height * (0.11 if style.position == "bottom" else 0.08)))
    margin_lr = int(round(target_width * 0.07))

    use_box = style.preset in {"neon_box", "bold_pop"} and style.background_opacity > 0.05
    border_style = 3 if use_box else 1
    outline_px = 3 if style.preset == "bold_pop" else (2 if style.preset != "minimal_clean" else 1)
    shadow_px = 2 if not use_box else 0

    primary_col = hex_to_ass_color(style.text_color, 1.0)
    secondary_col = hex_to_ass_color(style.accent_color, 1.0)
    outline_col = hex_to_ass_color(style.outline_color, 0.95)
    back_col = hex_to_ass_color(
        style.background_color if use_box else style.outline_color,
        style.background_opacity if use_box else 0.55,
    )
    bold_flag = -1 if style.preset in {"bold_pop", "neon_box"} else 0

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {target_width}",
        f"PlayResY: {target_height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,Arial,{font_size},{primary_col},{secondary_col},{outline_col},{back_col},"
        f"{bold_flag},0,0,0,100,100,0,0,{border_style},{outline_px},{shadow_px},{alignment},{margin_lr},{margin_lr},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    clip_duration = max(0.2, trim_end - trim_start)
    for cue in cues:
        if cue.end <= trim_start or cue.start >= trim_end:
            continue
        rel_start = max(0.0, cue.start - trim_start)
        rel_end = min(clip_duration, cue.end - trim_start)
        if rel_end - rel_start < 0.12:
            continue
        txt = cue.text.upper() if style.uppercase else cue.text
        lines.append(
            f"Dialogue: 0,{_format_ass_timestamp(rel_start)},{_format_ass_timestamp(rel_end)},Default,,0,0,0,,{_escape_ass_text(txt)}"
        )

    output_ass_path.parent.mkdir(parents=True, exist_ok=True)
    output_ass_path.write_text("\n".join(lines), encoding="utf-8")
    return output_ass_path


def compute_render_signature(
    clip_doc: dict[str, Any],
    quality: ExportQuality,
    aspect_ratio: AspectRatio,
) -> str:
    payload = {
        "trim_start": round(float(clip_doc["trim_start"]), 3),
        "trim_end": round(float(clip_doc["trim_end"]), 3),
        "quality": quality,
        "aspect_ratio": aspect_ratio,
        "captions_enabled": bool(clip_doc.get("captions_enabled", True)),
        "subtitle_style": clip_doc.get("subtitle_style", {}),
        "subtitles": clip_doc.get("subtitles", []),
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def build_crop_scale_filter(
    src_width: int,
    src_height: int,
    target_width: int,
    target_height: int,
    crop_x_ratio: float = 0.5,
) -> str:
    """Construct an exact aspect-ratio FFmpeg crop + Lanczos scale filter centered on the speaker."""
    src_ar = src_width / max(1, src_height)
    tgt_ar = target_width / max(1, target_height)

    if abs(src_ar - tgt_ar) < 0.01:
        return f"scale={target_width}:{target_height}:flags=lanczos,setsar=1"

    if src_ar > tgt_ar:
        # Source is wider than target (e.g. 16:9 -> 9:16 or 1:1): crop width around face center
        crop_h = src_height - (src_height % 2)
        crop_w = int(round(crop_h * tgt_ar))
        crop_w -= crop_w % 2
        crop_w = max(2, min(src_width - (src_width % 2), crop_w))
        max_x = max(0, src_width - crop_w)
        desired_x = int(round(crop_x_ratio * src_width - crop_w * 0.5))
        crop_x = max(0, min(max_x, desired_x))
        crop_y = max(0, (src_height - crop_h) // 2)
    else:
        # Source is taller than target (e.g. 9:16 -> 16:9): crop height symmetrically
        crop_w = src_width - (src_width % 2)
        crop_h = int(round(crop_w / tgt_ar))
        crop_h -= crop_h % 2
        crop_h = max(2, min(src_height - (src_height % 2), crop_h))
        crop_x = max(0, (src_width - crop_w) // 2)
        crop_y = max(0, (src_height - crop_h) // 2)

    return f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={target_width}:{target_height}:flags=lanczos,setsar=1"


def render_clip_mp4(
    source_video_path: Path,
    src_width: int,
    src_height: int,
    has_audio: bool,
    clip_doc: dict[str, Any],
    quality: ExportQuality,
    aspect_ratio: AspectRatio,
    settings: Settings,
    cancel_event: threading.Event | None = None,
) -> tuple[Path, str, int]:
    """Render an HD MP4 clip using FFmpeg with trim, aspect ratio crop, and optional ASS subtitles."""
    target_w, target_h = RESOLUTION_MAP[(aspect_ratio, quality)]
    trim_start = float(clip_doc["trim_start"])
    trim_end = float(clip_doc["trim_end"])
    clip_duration = max(1.0, trim_end - trim_start)
    crop_x = float(clip_doc.get("preferred_crop_x_ratio", 0.5))

    signature = compute_render_signature(clip_doc, quality, aspect_ratio)
    clip_id = str(clip_doc["_id"])
    video_id = str(clip_doc["video_id"])
    out_name = f"{video_id}_{clip_id}_{aspect_ratio.replace(':', 'x')}_{quality}_{signature}.mp4"
    out_path = settings.renders_dir / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and out_path.stat().st_size > 1024:
        return out_path, signature, out_path.stat().st_size

    vf_parts = [build_crop_scale_filter(src_width, src_height, target_w, target_h, crop_x)]

    captions_enabled = bool(clip_doc.get("captions_enabled", True))
    raw_cues = clip_doc.get("subtitles", [])
    ass_filename: str | None = None

    if captions_enabled and raw_cues:
        cues = [SubtitleCue.model_validate(c) for c in raw_cues]
        style = SubtitleStyle.model_validate(clip_doc.get("subtitle_style", {}))
        ass_filename = f"{video_id}_{clip_id}_{signature}.ass"
        ass_path = settings.subtitles_dir / ass_filename
        generate_ass_subtitle_file(
            cues=cues,
            style=style,
            trim_start=trim_start,
            trim_end=trim_end,
            target_width=target_w,
            target_height=target_h,
            output_ass_path=ass_path,
        )
        # Running FFmpeg with cwd=subtitles_dir avoids Windows drive-letter escaping bugs in libass
        vf_parts.append(f"subtitles={ass_filename}")

    vf_chain = ",".join(vf_parts)
    args = [
        "-y",
        "-ss",
        f"{trim_start:.3f}",
        "-i",
        str(source_video_path.resolve()),
        "-t",
        f"{clip_duration:.3f}",
        "-vf",
        vf_chain,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18" if quality == "1080p" else "20",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_audio:
        args.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "48000"])
    else:
        args.append("-an")
    args.extend(["-movflags", "+faststart", str(out_path.resolve())])

    run_ffmpeg_command(
        args,
        settings=settings,
        cwd=settings.subtitles_dir.resolve() if ass_filename else None,
        cancel_event=cancel_event,
    )

    return out_path, signature, out_path.stat().st_size


def build_variant_key(quality: ExportQuality, aspect_ratio: AspectRatio) -> str:
    return f"{quality}_{aspect_ratio}"


def make_safe_filename(title: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in title.strip())
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_")[:60] or "short_clip"


def create_clips_zip_archive(
    video_id: str,
    video_title: str,
    rendered_entries: list[tuple[str, Path]],
    quality: ExportQuality,
    settings: Settings,
) -> tuple[Path, str, int]:
    """Bundle rendered HD MP4 clips into a single downloadable ZIP file."""
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_proj = make_safe_filename(video_title)
    zip_name = f"{video_id}_{safe_proj}_{quality}_{ts}.zip"
    zip_path = settings.exports_dir / zip_name

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_STORED) as zf:
        for arcname, file_path in rendered_entries:
            if file_path.exists():
                zf.write(file_path, arcname=arcname)

    return zip_path, zip_name, zip_path.stat().st_size
