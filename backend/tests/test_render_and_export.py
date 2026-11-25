from pathlib import Path
import zipfile

from app.core.media_tools import probe_video
from app.services.render_service import hex_to_ass_color
from tests.conftest import build_synthetic_color_video


def test_ass_color_conversion():
    assert hex_to_ass_color("#FFFFFF", 1.0) == "&H00FFFFFF"
    assert hex_to_ass_color("#FF0000", 0.0) == "&HFF0000FF"
    assert hex_to_ass_color("#00FF00", 0.5) == "&H8000FF00"


def test_edit_render_and_zip_export_pipeline(client, test_settings, tmp_path: Path):
    # Temporarily relax test_settings duration bounds for fast 45s end-to-end upload + render test
    test_settings.min_video_duration_seconds = 30.0
    test_settings.max_video_duration_seconds = 1200.0

    src_mp4 = build_synthetic_color_video(
        tmp_path / "sample_45s.mp4",
        duration_sec=45.0,
        settings=test_settings,
        with_audio=True,
        fps=15,
        size="640x360",
    )
    with src_mp4.open("rb") as fp:
        up_res = client.post(
            "/api/videos/upload",
            files={"file": ("sample_45s.mp4", fp, "video/mp4")},
            data={
                "title": "Render Test Video",
                "target_shorts_count": "5",
                "default_aspect_ratio": "9:16",
                "default_quality": "720p",
                "auto_process": "false",
            },
        )
    assert up_res.status_code == 201, up_res.text
    video_id = up_res.json()["id"]

    # Trigger full processing synchronously via API and wait for completion
    proc_res = client.post(f"/api/videos/{video_id}/process")
    assert proc_res.status_code == 200

    import time

    deadline = time.time() + 90.0
    status_val = "queued"
    while time.time() < deadline:
        v_res = client.get(f"/api/videos/{video_id}")
        assert v_res.status_code == 200
        status_val = v_res.json()["status"]
        if status_val in ("completed", "failed"):
            break
        time.sleep(0.5)

    assert status_val == "completed", f"Pipeline ended in state {status_val}: {v_res.json().get('error_message')}"

    clips_res = client.get(f"/api/videos/{video_id}/clips")
    assert clips_res.status_code == 200
    clips = clips_res.json()
    assert len(clips) >= 3  # 45s synthetic test clip produces >=3 non-overlapping 10s clips

    clip = clips[0]
    clip_id = clip["id"]

    # Edit trim, captions, style, and aspect ratio 1:1
    patch_res = client.patch(
        f"/api/clips/{clip_id}",
        json={
            "title": "Edited Viral Hook",
            "trim_start": clip["trim_start"],
            "trim_end": min(44.0, clip["trim_start"] + 11.5),
            "aspect_ratio": "1:1",
            "captions_enabled": True,
            "subtitle_style": {
                "preset": "neon_box",
                "text_color": "#FFFFFF",
                "accent_color": "#22D3EE",
                "background_color": "#5B21B6",
                "background_opacity": 0.85,
                "outline_color": "#000000",
                "font_size": 34,
                "position": "bottom",
                "uppercase": False,
            },
            "subtitles": [
                {
                    "id": "c1",
                    "start": clip["trim_start"] + 0.5,
                    "end": clip["trim_start"] + 4.0,
                    "text": "Testing burned-in styled captions!",
                }
            ],
        },
    )
    assert patch_res.status_code == 200, patch_res.text
    assert patch_res.json()["aspect_ratio"] == "1:1"

    # Render 1080p in 1:1 -> must probe at 1080x1080
    render_res = client.post(
        f"/api/clips/{clip_id}/render",
        json={"quality": "1080p", "aspect_ratio": "1:1"},
    )
    assert render_res.status_code == 200, render_res.text

    dl_res = client.get(f"/api/clips/{clip_id}/download?quality=1080p&aspect_ratio=1:1")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "video/mp4"
    dl_file = tmp_path / "downloaded_1080_1x1.mp4"
    dl_file.write_bytes(dl_res.content)
    meta = probe_video(dl_file, test_settings)
    assert meta.width == 1080 and meta.height == 1080
    assert 10.0 <= meta.duration <= 13.0

    # Verify 720p in 9:16 -> 720x1280 and 720p in 16:9 -> 1280x720
    dl_916 = client.get(f"/api/clips/{clip_id}/download?quality=720p&aspect_ratio=9:16")
    assert dl_916.status_code == 200
    p_916 = tmp_path / "dl_720_9x16.mp4"
    p_916.write_bytes(dl_916.content)
    m_916 = probe_video(p_916, test_settings)
    assert m_916.width == 720 and m_916.height == 1280

    dl_169 = client.get(f"/api/clips/{clip_id}/download?quality=720p&aspect_ratio=16:9")
    assert dl_169.status_code == 200
    p_169 = tmp_path / "dl_720_16x9.mp4"
    p_169.write_bytes(dl_169.content)
    m_169 = probe_video(p_169, test_settings)
    assert m_169.width == 1280 and m_169.height == 720

    # Export all clips as 720p ZIP
    zip_req = client.post(
        f"/api/videos/{video_id}/export-zip",
        json={"quality": "720p"},
    )
    assert zip_req.status_code == 201, zip_req.text
    zip_dl = client.get(zip_req.json()["download_url"])
    assert zip_dl.status_code == 200
    zip_path = tmp_path / "all_shorts.zip"
    zip_path.write_bytes(zip_dl.content)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert len(names) == len(clips)
        assert all(n.endswith(".mp4") for n in names)
