from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.services.youtube_service import validate_youtube_url
from tests.conftest import build_synthetic_color_video


def test_auth_register_login_me_and_user_scoping(client, test_settings, tmp_path: Path):
    # Register user A
    reg_a = client.post(
        "/api/auth/register",
        json={"name": "Alice Creator", "email": "alice@clipora.ai", "password": "secret123"},
    )
    assert reg_a.status_code == 201, reg_a.text
    token_a = reg_a.json()["access_token"]
    assert reg_a.json()["user"]["email"] == "alice@clipora.ai"

    # Duplicate email fails cleanly
    dup = client.post(
        "/api/auth/register",
        json={"name": "Alice 2", "email": "alice@clipora.ai", "password": "secret123"},
    )
    assert dup.status_code == 409

    # Wrong password rejected
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "alice@clipora.ai", "password": "wrongpassword"},
    )
    assert bad_login.status_code == 401

    # Valid login + /api/auth/me
    good_login = client.post(
        "/api/auth/login",
        json={"email": "alice@clipora.ai", "password": "secret123"},
    )
    assert good_login.status_code == 200
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    assert me_res.status_code == 200
    assert me_res.json()["name"] == "Alice Creator"

    # Unauthenticated /api/auth/me returns 401
    assert client.get("/api/auth/me").status_code == 401

    # Register user B and confirm user-scoped projects
    reg_b = client.post(
        "/api/auth/register",
        json={"name": "Bob Studio", "email": "bob@clipora.ai", "password": "secret456"},
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["access_token"]

    vid = build_synthetic_color_video(
        tmp_path / "alice_vid.mp4",
        duration_sec=25.0,
        settings=test_settings,
        fps=5,
        size="160x90",
    )
    with vid.open("rb") as fp:
        up_a = client.post(
            "/api/videos/upload",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("alice_vid.mp4", fp, "video/mp4")},
            data={"title": "Alice Private Project", "auto_process": "false"},
        )
    assert up_a.status_code == 201
    alice_vid_id = up_a.json()["id"]

    list_a = client.get("/api/videos", headers={"Authorization": f"Bearer {token_a}"}).json()
    list_b = client.get("/api/videos", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert any(v["id"] == alice_vid_id for v in list_a)
    assert not any(v["id"] == alice_vid_id for v in list_b)


def test_youtube_url_validation_formats():
    norm1, key1 = validate_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=12s")
    assert norm1 == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert key1 == "dQw4w9WgXcQ"

    norm2, key2 = validate_youtube_url("https://youtu.be/abcDEF12345")
    assert norm2 == "https://www.youtube.com/watch?v=abcDEF12345"
    assert key2 == "abcDEF12345"

    norm3, key3 = validate_youtube_url("https://youtube.com/shorts/xyz987654")
    assert norm3 == "https://www.youtube.com/watch?v=xyz987654"
    assert key3 == "xyz987654"

    with pytest.raises(HTTPException) as exc:
        validate_youtube_url("https://example.com/video.mp4")
    assert exc.value.status_code == 400


def test_youtube_preview_and_import_duration_guard(client):
    class FakeYdlValid:
        def __init__(self, _opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, _url, download=False):
            return {
                "title": "Clean Coding Interview",
                "channel": "Dev Channel",
                "duration": 480,
                "thumbnail": "https://i.ytimg.com/vi/abcDEF12345/hqdefault.jpg",
                "is_live": False,
            }

    class FakeYdlTooLong(FakeYdlValid):
        def extract_info(self, _url, download=False):
            return {
                "title": "3 Hour Podcast",
                "channel": "Long Cast",
                "duration": 3600,
                "thumbnail": None,
                "is_live": False,
            }

    with patch("yt_dlp.YoutubeDL", FakeYdlValid):
        prev_res = client.post(
            "/api/videos/youtube/preview",
            json={"url": "https://youtu.be/abcDEF12345"},
        )
        assert prev_res.status_code == 200
        prev = prev_res.json()
        assert prev["valid_duration"] is True
        assert prev["duration"] == 480.0

        imp_res = client.post(
            "/api/videos/youtube",
            json={"url": "https://youtu.be/abcDEF12345", "auto_process": False},
        )
        assert imp_res.status_code == 201
        imp = imp_res.json()
        assert imp["source_type"] == "youtube"
        assert imp["youtube_url"] == "https://www.youtube.com/watch?v=abcDEF12345"
        assert imp["pipeline_steps"][0]["key"] == "youtube_download"

    with patch("yt_dlp.YoutubeDL", FakeYdlTooLong):
        bad_prev = client.post(
            "/api/videos/youtube/preview",
            json={"url": "https://youtu.be/abcDEF12345"},
        )
        assert bad_prev.status_code == 200
        assert bad_prev.json()["valid_duration"] is False

        bad_imp = client.post(
            "/api/videos/youtube",
            json={"url": "https://youtu.be/abcDEF12345", "auto_process": False},
        )
        assert bad_imp.status_code == 422
        assert "must be under" in bad_imp.json()["detail"]
