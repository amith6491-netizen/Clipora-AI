from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any, Callable

import cv2
import numpy as np
from scenedetect import ContentDetector, SceneManager, open_video

from app.core.cancellation import raise_if_cancelled

_FACE_CASCADE: Any = None


def _get_face_cascade() -> Any:
    global _FACE_CASCADE
    if _FACE_CASCADE is not None:
        return _FACE_CASCADE
    cascade_cls = getattr(cv2, "CascadeClassifier", None)
    haarcascades_dir = getattr(getattr(cv2, "data", None), "haarcascades", None)
    if cascade_cls is None or not haarcascades_dir:
        return None
    cascade_path = Path(haarcascades_dir) / "haarcascade_frontalface_default.xml"
    if cascade_path.exists():
        classifier = cascade_cls(str(cascade_path))
        if not classifier.empty():
            _FACE_CASCADE = classifier
    return _FACE_CASCADE


@dataclass
class SceneCut:
    start: float
    end: float


@dataclass
class VisualTimelineProfile:
    duration: float
    scenes: list[SceneCut]
    cut_timestamps: list[float]
    sample_times: np.ndarray
    motion_norm: np.ndarray
    sharpness_norm: np.ndarray
    face_presence: np.ndarray
    face_center_x: np.ndarray


def detect_scenes_and_visual_dynamics(
    video_path: Path,
    duration: float,
    progress_callback: Callable[[float, str], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> VisualTimelineProfile:
    """Detect shot boundaries via PySceneDetect and sample motion/sharpness/faces via OpenCV."""
    raise_if_cancelled(cancel_event)
    if progress_callback:
        progress_callback(5.0, "Opening video stream for PySceneDetect shot analysis")

    video = open_video(str(video_path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=27.0, min_scene_len=15))
    scene_manager.detect_scenes(video=video, show_progress=False)
    scene_list = scene_manager.get_scene_list()

    scenes: list[SceneCut] = []
    cut_timestamps: list[float] = []
    for start_tc, end_tc in scene_list:
        s_sec = round(float(start_tc.seconds), 3)
        e_sec = round(float(end_tc.seconds), 3)
        scenes.append(SceneCut(start=s_sec, end=e_sec))
        if s_sec > 0.2:
            cut_timestamps.append(s_sec)

    if not scenes:
        scenes.append(SceneCut(start=0.0, end=round(duration, 3)))

    if progress_callback:
        progress_callback(55.0, f"Detected {len(scenes)} scenes; analyzing OpenCV visual pacing & faces")

    cap = cv2.VideoCapture(str(video_path))
    sample_interval = 1.0 if duration >= 120.0 else 0.5
    sample_times_list: list[float] = []
    motion_vals: list[float] = []
    sharp_vals: list[float] = []
    face_present_vals: list[float] = []
    face_x_vals: list[float] = []

    face_cascade = _get_face_cascade()
    prev_gray: np.ndarray | None = None

    t = 0.25
    total_steps = max(1, int(duration / sample_interval))
    step_idx = 0

    try:
        while t < duration:
            raise_if_cancelled(cancel_event)
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            small = cv2.resize(frame, (320, 180))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            sharp_vals.append(lap_var)

            if prev_gray is not None:
                diff = float(np.mean(cv2.absdiff(gray, prev_gray)))
            else:
                diff = 0.0
            motion_vals.append(diff)
            prev_gray = gray

            has_face = 0.0
            center_x = 0.5
            if face_cascade is not None:
                faces = face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.15,
                    minNeighbors=4,
                    minSize=(24, 24),
                )
                if len(faces) > 0:
                    largest = max(faces, key=lambda rect: rect[2] * rect[3])
                    fx, _, fw, _ = largest
                    center_x = float(np.clip((fx + fw * 0.5) / gray.shape[1], 0.15, 0.85))
                    has_face = 1.0
            else:
                # OpenCV 5 fallback: track horizontal edge-saliency centroid of the active subject
                edges = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0))
                col_energy = np.sum(edges, axis=0)
                total_energy = float(np.sum(col_energy))
                if total_energy > 1e-3:
                    xs = np.arange(gray.shape[1], dtype=np.float32)
                    centroid = float(np.sum(xs * col_energy) / total_energy)
                    center_x = float(np.clip(centroid / gray.shape[1], 0.2, 0.8))

            face_present_vals.append(has_face)
            face_x_vals.append(center_x)
            sample_times_list.append(t)

            step_idx += 1
            if progress_callback and step_idx % 20 == 0:
                pct = min(98.0, 55.0 + (step_idx / total_steps) * 42.0)
                progress_callback(pct, f"Analyzed {step_idx} visual frames across {len(scenes)} scenes")

            t += sample_interval
    finally:
        cap.release()

    def _norm(vals: list[float]) -> np.ndarray:
        arr = np.asarray(vals, dtype=np.float32)
        if arr.size == 0:
            return arr
        lo = float(np.percentile(arr, 5))
        hi = float(np.percentile(arr, 95))
        if hi - lo < 1e-6:
            return np.full_like(arr, 0.5, dtype=np.float32)
        return np.clip((arr - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)

    if progress_callback:
        progress_callback(100.0, f"Scene & OpenCV analysis complete ({len(scenes)} scenes)")

    return VisualTimelineProfile(
        duration=duration,
        scenes=scenes,
        cut_timestamps=cut_timestamps,
        sample_times=np.asarray(sample_times_list, dtype=np.float32),
        motion_norm=_norm(motion_vals),
        sharpness_norm=_norm(sharp_vals),
        face_presence=np.asarray(face_present_vals, dtype=np.float32),
        face_center_x=np.asarray(face_x_vals, dtype=np.float32),
    )


def score_visual_window(
    profile: VisualTimelineProfile | None,
    start: float,
    end: float,
) -> tuple[float, int, float]:
    """Return (visual_score_0_100, scene_cuts_in_window, preferred_face_x_ratio)."""
    if profile is None or profile.sample_times.size == 0:
        return 50.0, 0, 0.5

    cuts_inside = sum(1 for c in profile.cut_timestamps if start <= c <= end)
    mask = (profile.sample_times >= start) & (profile.sample_times <= end)

    if not np.any(mask):
        pacing_bonus = min(1.0, cuts_inside / 3.0)
        return round(45.0 + pacing_bonus * 30.0, 2), cuts_inside, 0.5

    motion = float(np.mean(profile.motion_norm[mask]))
    sharp = float(np.mean(profile.sharpness_norm[mask]))
    face_mask = profile.face_presence[mask]
    face_ratio = float(np.mean(face_mask))

    if np.any(face_mask > 0.5):
        valid_xs = profile.face_center_x[mask][face_mask > 0.5]
        crop_x = float(np.median(valid_xs))
    else:
        crop_x = 0.5

    # 1-4 cuts in a 10-20s short gives great visual pacing; extreme flicker (>6) is penalized slightly
    cut_pacing = min(1.0, cuts_inside / 3.0) if cuts_inside <= 6 else 0.7

    raw = 0.35 * motion + 0.25 * sharp + 0.25 * cut_pacing + 0.15 * face_ratio
    score = round(min(100.0, max(15.0, raw * 100.0)), 2)
    return score, cuts_inside, round(crop_x, 3)
