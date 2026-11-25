from dataclasses import dataclass
from pathlib import Path
import threading

import numpy as np
from scipy.io import wavfile
from scipy.signal import stft

from app.core.config import Settings
from app.core.media_tools import run_ffmpeg_command


@dataclass
class AudioEnergyProfile:
    sample_rate: int
    duration: float
    hop_seconds: float
    times: np.ndarray
    rms_norm: np.ndarray
    flux_norm: np.ndarray
    zcr_norm: np.ndarray
    excitement_curve: np.ndarray
    avg_energy: float
    peak_count: int


def extract_wav_audio(
    video_path: Path,
    wav_path: Path,
    settings: Settings,
    cancel_event: threading.Event | None = None,
) -> Path:
    """Extract 16kHz mono 16-bit PCM WAV audio from the video via FFmpeg."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg_command(
        [
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ],
        settings=settings,
        cancel_event=cancel_event,
    )
    return wav_path


def _robust_normalize(arr: np.ndarray) -> np.ndarray:
    if arr.size == 0:
        return arr
    lo = float(np.percentile(arr, 5))
    hi = float(np.percentile(arr, 98))
    if hi - lo < 1e-8:
        return np.zeros_like(arr, dtype=np.float32)
    clipped = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)
    return clipped.astype(np.float32)


def analyze_audio_dynamics(wav_path: Path, hop_seconds: float = 0.25) -> AudioEnergyProfile:
    """Compute acoustic energy, spectral flux, ZCR, and excitement envelope across the full audio."""
    sr, samples = wavfile.read(str(wav_path))
    if samples.ndim > 1:
        samples = samples.mean(axis=1)

    if np.issubdtype(samples.dtype, np.integer):
        max_val = float(np.iinfo(samples.dtype).max)
        signal = samples.astype(np.float32) / max(max_val, 1.0)
    else:
        signal = samples.astype(np.float32)

    duration = float(len(signal)) / float(sr) if sr > 0 else 0.0
    hop_samples = max(1, int(sr * hop_seconds))
    n_frames = max(1, len(signal) // hop_samples)

    trimmed = signal[: n_frames * hop_samples]
    if len(trimmed) < hop_samples:
        trimmed = np.pad(signal, (0, hop_samples - len(signal)))
        n_frames = 1

    frames = trimmed.reshape(n_frames, hop_samples)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-10)

    # Zero-crossing rate detects crisp vocal articulation and energetic laughter/applause
    signs = np.signbit(frames)
    zcr = np.mean(signs[:, 1:] != signs[:, :-1], axis=1).astype(np.float32)

    # Spectral flux via STFT aligned to hop windows
    _, _, zxx = stft(trimmed, fs=sr, nperseg=min(1024, hop_samples), noverlap=min(512, hop_samples // 2))
    mag = np.abs(zxx)
    if mag.shape[1] > 1:
        diff = np.maximum(0.0, mag[:, 1:] - mag[:, :-1])
        flux_raw = np.sqrt(np.mean(diff ** 2, axis=0))
        flux_interp = np.interp(
            np.linspace(0, 1, n_frames),
            np.linspace(0, 1, len(flux_raw)),
            flux_raw,
        )
    else:
        flux_interp = np.zeros(n_frames, dtype=np.float32)

    rms_norm = _robust_normalize(rms)
    flux_norm = _robust_normalize(flux_interp)
    zcr_norm = _robust_normalize(zcr)

    # Combined acoustic excitement signal
    excitement = np.clip(0.50 * rms_norm + 0.35 * flux_norm + 0.15 * zcr_norm, 0.0, 1.0)
    times = (np.arange(n_frames, dtype=np.float32) + 0.5) * hop_seconds

    # Count distinct high-energy spikes above 75th percentile + margin
    threshold = max(0.65, float(np.percentile(excitement, 80)))
    above = excitement >= threshold
    peak_count = int(np.sum(above[1:] & ~above[:-1])) if len(above) > 1 else int(np.any(above))

    return AudioEnergyProfile(
        sample_rate=sr,
        duration=duration,
        hop_seconds=hop_seconds,
        times=times,
        rms_norm=rms_norm,
        flux_norm=flux_norm,
        zcr_norm=zcr_norm,
        excitement_curve=excitement,
        avg_energy=float(np.mean(rms_norm)) if rms_norm.size else 0.0,
        peak_count=peak_count,
    )


def score_audio_window(
    profile: AudioEnergyProfile | None,
    start: float,
    end: float,
) -> tuple[float, float, int]:
    """Return (audio_score_0_100, speech_activity_ratio, excitement_peaks_in_window)."""
    if profile is None or profile.times.size == 0:
        return 45.0, 0.5, 0

    mask = (profile.times >= start) & (profile.times <= end)
    if not np.any(mask):
        idx = int(np.clip(np.searchsorted(profile.times, (start + end) * 0.5), 0, profile.times.size - 1))
        val = float(profile.excitement_curve[idx])
        return round(min(100.0, max(15.0, val * 100.0)), 2), 0.7, 0

    win_exc = profile.excitement_curve[mask]
    win_rms = profile.rms_norm[mask]

    mean_exc = float(np.mean(win_exc))
    peak_exc = float(np.percentile(win_exc, 90))
    dynamic_range = float(np.std(win_exc))
    active_ratio = float(np.mean(win_rms >= 0.18))

    # Reward energetic delivery + dynamic shifts + low dead-air
    raw = (
        0.40 * mean_exc
        + 0.30 * peak_exc
        + 0.15 * min(1.0, dynamic_range * 3.0)
        + 0.15 * active_ratio
    )
    score = round(min(100.0, max(5.0, raw * 100.0)), 2)

    threshold = max(0.65, float(np.percentile(profile.excitement_curve, 82)))
    above = win_exc >= threshold
    peaks = int(np.sum(above[1:] & ~above[:-1])) if len(above) > 1 else int(np.any(above))
    return score, round(active_ratio, 3), peaks
