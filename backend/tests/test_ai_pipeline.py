from pathlib import Path
import subprocess

from app.core.media_tools import resolve_media_binaries
from app.services.audio_service import analyze_audio_dynamics, extract_wav_audio
from app.services.ranking_service import select_and_rank_shorts
from app.services.scene_service import detect_scenes_and_visual_dynamics
from app.services.transcription_service import build_subtitle_cues_from_segments, transcribe_audio_with_whisper


def _build_multi_scene_speech_video(out_mp4: Path, settings) -> Path:
    """Create a 90-second multi-scene video with real spoken English across diverse topics."""
    fixtures_dir = Path(__file__).resolve().parent / "fixtures"
    host_mp3 = fixtures_dir / "host.mp3"
    guest_mp3 = fixtures_dir / "guest.mp3"
    assert host_mp3.exists() and guest_mp3.exists()

    # Concatenate 6 visually distinct scenes (15s each = 90s) + spaced real speech across the full timeline
    bins = resolve_media_binaries(settings)
    filter_complex = (
        "color=c=#1e1b4b:s=640x360:r=15:d=15[v0];"
        "color=c=#0f766e:s=640x360:r=15:d=15[v1];"
        "color=c=#991b1b:s=640x360:r=15:d=15[v2];"
        "color=c=#854d0e:s=640x360:r=15:d=15[v3];"
        "color=c=#312e81:s=640x360:r=15:d=15[v4];"
        "color=c=#064e3b:s=640x360:r=15:d=15[v5];"
        "[v0][v1][v2][v3][v4][v5]concat=n=6:v=1:a=0,format=yuv420p[vout];"
        "[0:a]asplit=2[a1][a3src];"
        "[1:a]adelay=31000|31000[a2];"
        "[a3src]adelay=60000|60000[a3];"
        "[a1][a2][a3]amix=inputs=3:duration=longest:normalize=0,apad=whole_dur=90[aout]"
    )
    proc = subprocess.run(
        [
            bins.ffmpeg,
            "-y",
            "-i",
            str(host_mp3),
            "-i",
            str(guest_mp3),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-t",
            "90",
            str(out_mp4),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed creating multi-scene speech video: {proc.stderr}")
    return out_mp4


def test_real_ai_pipeline_end_to_end(test_settings, tmp_path: Path):
    test_settings.ensure_dirs()
    video_path = _build_multi_scene_speech_video(tmp_path / "talk.mp4", test_settings)

    # 1. Extract audio
    wav_path = test_settings.audio_dir / "talk.wav"
    extract_wav_audio(video_path, wav_path, test_settings)
    assert wav_path.exists() and wav_path.stat().st_size > 10000

    # 2. Faster-Whisper transcription with word timestamps
    segments, lang = transcribe_audio_with_whisper(wav_path, 90.0, test_settings)
    assert len(segments) >= 3
    total_words = sum(len(s.words) for s in segments)
    assert total_words >= 30
    assert lang

    # 3. PySceneDetect + OpenCV
    visual_profile = detect_scenes_and_visual_dynamics(video_path, 90.0)
    assert len(visual_profile.scenes) >= 4
    assert len(visual_profile.cut_timestamps) >= 3

    # 4. Audio analysis
    audio_profile = analyze_audio_dynamics(wav_path)
    assert audio_profile.duration > 30.0
    assert audio_profile.rms_norm.size > 50

    # 5. NLP understanding & multimodal ranking (5-15 shorts, 10-20s each, zero overlap)
    ranked, evaluated_count = select_and_rank_shorts(
        segments=segments,
        audio_profile=audio_profile,
        visual_profile=visual_profile,
        video_duration=90.0,
        target_shorts_count=6,
        settings=test_settings,
    )
    assert evaluated_count >= 5
    assert 5 <= len(ranked) <= 10

    for i, clip in enumerate(ranked):
        assert 9.9 <= clip.duration <= 20.1
        assert 0.0 <= clip.engagement_score <= 100.0
        assert clip.title and len(clip.title) >= 4
        assert clip.category in {
            "interesting",
            "funny",
            "important",
            "motivational",
            "educational",
            "engaging",
        }
        cues = build_subtitle_cues_from_segments(segments, clip.start, clip.end)
        # At least the speech clips should have generated cues
        if clip.start < 50.0:
            assert isinstance(cues, list)
        # Check zero temporal overlap against all other selected clips
        for j, other in enumerate(ranked):
            if i != j:
                assert clip.end <= other.start + 0.01 or clip.start >= other.end - 0.01
