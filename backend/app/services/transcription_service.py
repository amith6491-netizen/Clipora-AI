from math import gcd
from pathlib import Path
import threading
from threading import Lock
from typing import Callable

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

from app.core.cancellation import raise_if_cancelled
from app.core.config import Settings
from app.models.schemas import SubtitleCue, TranscriptSegment, TranscriptWord

_model_cache: dict[tuple[str, str, str], object] = {}
_model_lock = Lock()


def _resolve_device_and_compute(device: str, compute_type: str) -> tuple[str, str]:
    resolved_device = device
    if resolved_device == "auto":
        try:
            import ctranslate2

            resolved_device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            resolved_device = "cpu"

    resolved_compute = compute_type
    if resolved_compute == "auto":
        resolved_compute = "float16" if resolved_device == "cuda" else "int8"

    return resolved_device, resolved_compute


def get_whisper_model(settings: Settings):
    """Load and cache the Faster-Whisper model instance with offline cache fallback."""
    from faster_whisper import WhisperModel

    device, compute_type = _resolve_device_and_compute(
        settings.whisper_device,
        settings.whisper_compute_type,
    )
    key = (settings.whisper_model_size, device, compute_type)
    with _model_lock:
        if key not in _model_cache:
            try:
                _model_cache[key] = WhisperModel(
                    settings.whisper_model_size,
                    device=device,
                    compute_type=compute_type,
                    local_files_only=True,
                )
            except Exception:
                _model_cache[key] = WhisperModel(
                    settings.whisper_model_size,
                    device=device,
                    compute_type=compute_type,
                )
        return _model_cache[key]


def _load_wav_as_whisper_array(wav_path: Path, target_sr: int = 16000) -> np.ndarray:
    """Load 16kHz mono float32 waveform directly, bypassing PyAV 19 metadata_errors issues."""
    sr, samples = wavfile.read(str(wav_path))
    if samples.ndim > 1:
        samples = samples.mean(axis=1)

    if np.issubdtype(samples.dtype, np.integer):
        max_val = float(np.iinfo(samples.dtype).max)
        audio = samples.astype(np.float32) / max(max_val, 1.0)
    else:
        audio = samples.astype(np.float32)

    if sr != target_sr and sr > 0 and audio.size > 0:
        g = gcd(int(sr), int(target_sr))
        audio = resample_poly(audio, target_sr // g, sr // g).astype(np.float32)

    return np.ascontiguousarray(audio, dtype=np.float32)


def transcribe_audio_with_whisper(
    audio_path: Path,
    total_duration: float,
    settings: Settings,
    progress_callback: Callable[[float, str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> tuple[list[TranscriptSegment], str]:
    """Transcribe audio with Faster-Whisper including word-level timestamps."""
    raise_if_cancelled(cancel_event)
    model = get_whisper_model(settings)
    audio_input: np.ndarray | str = (
        _load_wav_as_whisper_array(audio_path)
        if audio_path.suffix.lower() == ".wav"
        else str(audio_path)
    )
    segments_iter, info = model.transcribe(
        audio_input,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 350},
        beam_size=5,
    )

    language = getattr(info, "language", "en") or "en"
    duration_basis = max(float(getattr(info, "duration", 0.0) or total_duration), 1.0)
    results: list[TranscriptSegment] = []

    for idx, seg in enumerate(segments_iter):
        raise_if_cancelled(cancel_event)
        words: list[TranscriptWord] = []
        if getattr(seg, "words", None):
            for w in seg.words:
                word_text = (w.word or "").strip()
                if not word_text:
                    continue
                w_start = max(0.0, float(w.start))
                w_end = max(w_start + 0.04, float(w.end))
                words.append(
                    TranscriptWord(
                        word=word_text,
                        start=round(w_start, 3),
                        end=round(w_end, 3),
                        probability=round(float(getattr(w, "probability", 1.0) or 1.0), 3),
                    )
                )

        seg_text = (seg.text or "").strip()
        if not seg_text:
            continue

        seg_start = max(0.0, float(seg.start))
        seg_end = max(seg_start + 0.1, float(seg.end))
        results.append(
            TranscriptSegment(
                id=idx,
                start=round(seg_start, 3),
                end=round(seg_end, 3),
                text=seg_text,
                words=words,
            )
        )

        if progress_callback is not None:
            pct = min(99.0, max(1.0, (seg_end / duration_basis) * 100.0))
            progress_callback(pct, f"Transcribed {len(results)} segments ({seg_end:.1f}s / {duration_basis:.1f}s)")

    if progress_callback is not None:
        progress_callback(100.0, f"Completed transcription: {len(results)} segments ({language})")

    return results, language


def build_subtitle_cues_from_segments(
    segments: list[TranscriptSegment],
    clip_start: float,
    clip_end: float,
    max_words_per_cue: int = 5,
    max_cue_duration: float = 2.6,
) -> list[SubtitleCue]:
    """Generate tight, readable subtitle cues aligned to Faster-Whisper word timestamps."""
    clip_words: list[TranscriptWord] = []
    for seg in segments:
        if seg.end < clip_start or seg.start > clip_end:
            continue
        if seg.words:
            for w in seg.words:
                mid = 0.5 * (w.start + w.end)
                if clip_start - 0.05 <= mid <= clip_end + 0.05:
                    clip_words.append(w)
        else:
            tokens = seg.text.split()
            if not tokens:
                continue
            seg_dur = max(0.1, seg.end - seg.start)
            step = seg_dur / len(tokens)
            for i, tok in enumerate(tokens):
                ws = seg.start + i * step
                we = ws + step
                mid = 0.5 * (ws + we)
                if clip_start - 0.05 <= mid <= clip_end + 0.05:
                    clip_words.append(TranscriptWord(word=tok, start=round(ws, 3), end=round(we, 3)))

    if not clip_words:
        return []

    cues: list[SubtitleCue] = []
    chunk: list[TranscriptWord] = []

    def flush_chunk() -> None:
        if not chunk:
            return
        start_t = max(clip_start, chunk[0].start)
        end_t = min(clip_end, max(start_t + 0.25, chunk[-1].end))
        text = " ".join(w.word for w in chunk).strip()
        if text and end_t > start_t:
            cues.append(
                SubtitleCue(
                    id=f"cue-{len(cues) + 1}",
                    start=round(start_t, 3),
                    end=round(end_t, 3),
                    text=text,
                )
            )
        chunk.clear()

    for w in clip_words:
        if chunk:
            gap = w.start - chunk[-1].end
            span = w.end - chunk[0].start
            ends_sentence = chunk[-1].word.endswith((".", "?", "!"))
            if len(chunk) >= max_words_per_cue or span > max_cue_duration or gap > 0.45 or ends_sentence:
                flush_chunk()
        chunk.append(w)

    flush_chunk()
    return cues
