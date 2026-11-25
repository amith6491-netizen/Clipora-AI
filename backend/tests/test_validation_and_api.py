from pathlib import Path

from tests.conftest import build_synthetic_color_video


def test_system_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["mongodb_connected"] is True
    assert data["ffmpeg_available"] is True
    assert data["ffprobe_available"] is True
    assert data["faster_whisper_available"] is True
    assert data["scenedetect_available"] is True
    assert data["opencv_available"] is True
    assert data["nlp_model_available"] is True
    assert data["min_video_duration_seconds"] == 10.0
    assert data["max_video_duration_seconds"] == 1200.0


def test_reject_invalid_extension(client, tmp_path: Path):
    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("not a video", encoding="utf-8")
    with bad_file.open("rb") as fp:
        res = client.post(
            "/api/videos/upload",
            files={"file": ("notes.txt", fp, "text/plain")},
            data={"auto_process": "false"},
        )
    assert res.status_code == 400
    assert "Unsupported video format" in res.json()["detail"]


def test_reject_video_shorter_than_10_seconds(client, test_settings, tmp_path: Path):
    short_vid = build_synthetic_color_video(
        tmp_path / "short_5s.mp4",
        duration_sec=5.0,
        settings=test_settings,
    )
    with short_vid.open("rb") as fp:
        res = client.post(
            "/api/videos/upload",
            files={"file": ("short_5s.mp4", fp, "video/mp4")},
            data={"auto_process": "false"},
        )
    assert res.status_code == 422
    assert "must be under" in res.json()["detail"]


def test_reject_video_longer_than_20_minutes(client, test_settings, tmp_path: Path):
    long_vid = build_synthetic_color_video(
        tmp_path / "long_21m.mp4",
        duration_sec=1260.0,
        settings=test_settings,
        with_audio=False,
        fps=1,
        size="160x90",
    )
    with long_vid.open("rb") as fp:
        res = client.post(
            "/api/videos/upload",
            files={"file": ("long_21m.mp4", fp, "video/mp4")},
            data={"auto_process": "false"},
        )
    assert res.status_code == 422
    assert "must be under" in res.json()["detail"]


def test_accept_valid_short_2_min_video(client, test_settings, tmp_path: Path):
    vid_2m = build_synthetic_color_video(
        tmp_path / "clip_2m.mp4",
        duration_sec=120.0,
        settings=test_settings,
        with_audio=True,
        fps=5,
        size="160x90",
    )
    with vid_2m.open("rb") as fp:
        res = client.post(
            "/api/videos/upload",
            files={"file": ("clip_2m.mp4", fp, "video/mp4")},
            data={"title": "2 Min Demo Video", "auto_process": "false"},
        )
    assert res.status_code == 201, res.text
    vid_id = res.json()["id"]
    assert 118.0 <= res.json()["duration"] <= 122.0
    assert client.delete(f"/api/videos/{vid_id}").status_code == 204


def test_accept_valid_11_min_video_and_delete(client, test_settings, tmp_path: Path):
    valid_vid = build_synthetic_color_video(
        tmp_path / "podcast_11m.mp4",
        duration_sec=660.0,
        settings=test_settings,
        with_audio=True,
        fps=1,
        size="160x90",
    )
    with valid_vid.open("rb") as fp:
        res = client.post(
            "/api/videos/upload",
            files={"file": ("podcast_11m.mp4", fp, "video/mp4")},
            data={
                "title": "Podcast Episode 11",
                "target_shorts_count": "8",
                "default_aspect_ratio": "9:16",
                "default_quality": "720p",
                "auto_process": "false",
            },
        )
    assert res.status_code == 201, res.text
    payload = res.json()
    vid_id = payload["id"]
    assert payload["title"] == "Podcast Episode 11"
    assert 658.0 <= payload["duration"] <= 662.0
    assert payload["status"] == "uploaded"

    # Verify listing, detail, and poster frame
    list_res = client.get("/api/videos")
    assert list_res.status_code == 200
    assert any(v["id"] == vid_id for v in list_res.json())

    poster_res = client.get(payload["poster_url"])
    assert poster_res.status_code == 200
    assert poster_res.headers["content-type"] == "image/jpeg"

    del_res = client.delete(f"/api/videos/{vid_id}")
    assert del_res.status_code == 204
    assert client.get(f"/api/videos/{vid_id}").status_code == 404


def test_cancel_active_processing_job(client, test_settings, tmp_path: Path):
    import time

    vid = build_synthetic_color_video(
        tmp_path / "cancel_demo.mp4",
        duration_sec=35.0,
        settings=test_settings,
        with_audio=True,
        fps=10,
        size="320x180",
    )
    with vid.open("rb") as fp:
        up_res = client.post(
            "/api/videos/upload",
            files={"file": ("cancel_demo.mp4", fp, "video/mp4")},
            data={"title": "Cancel Test Video", "auto_process": "false"},
        )
    assert up_res.status_code == 201
    vid_id = up_res.json()["id"]

    proc_res = client.post(f"/api/videos/{vid_id}/process")
    assert proc_res.status_code == 200
    assert proc_res.json()["status"] in ("queued", "processing")

    # Immediately cancel while pipeline is executing
    cancel_res = client.post(f"/api/videos/{vid_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Give background task a moment to unwind and confirm status remains cancelled (not failed/completed)
    time.sleep(1.0)
    check_res = client.get(f"/api/videos/{vid_id}")
    assert check_res.status_code == 200
    assert check_res.json()["status"] == "cancelled"

    assert client.delete(f"/api/videos/{vid_id}").status_code == 204
