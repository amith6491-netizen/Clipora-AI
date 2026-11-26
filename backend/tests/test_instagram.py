from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.models.schemas import TranscriptSegment, TranscriptWord
from app.services.instagram_service import validate_instagram_url
from tests.conftest import build_synthetic_color_video


def test_instagram_url_validation():
    norm1, code1 = validate_instagram_url("https://www.instagram.com/reel/CxYz12345/?igsh=abc")
    assert norm1 == "https://www.instagram.com/reel/CxYz12345/"
    assert code1 == "CxYz12345"

    norm2, code2 = validate_instagram_url("https://www.instagram.com/p/AbCd98765/")
    assert norm2 == "https://www.instagram.com/p/AbCd98765/"
    assert code2 == "AbCd98765"

    norm3, code3 = validate_instagram_url("https://www.instagram.com/share/reel/ShaRe1234/")
    assert norm3 == "https://www.instagram.com/reel/ShaRe1234/"
    assert code3 == "ShaRe1234"

    with pytest.raises(HTTPException) as exc:
        validate_instagram_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert exc.value.status_code == 400


def test_instagram_high_quality_download_and_serve(client, test_settings):
    class FakeInstagramYdl:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, _url, download=True):
            assert download is True
            out_path = Path(str(self.opts["outtmpl"]).replace("%(ext)s", "mp4"))
            build_synthetic_color_video(
                out_path,
                duration_sec=14.0,
                settings=test_settings,
                with_audio=True,
                fps=15,
                size="1080x1920",
            )
            return {
                "title": "Morning Coding Productivity Reel",
                "uploader": "creator_dev",
            }

    with patch("yt_dlp.YoutubeDL", FakeInstagramYdl):
        res = client.post(
            "/api/instagram/download",
            json={"url": "https://www.instagram.com/reel/CxYz12345/"},
        )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["shortcode"] == "CxYz12345"
    assert data["width"] == 1080 and data["height"] == 1920
    assert data["file_name"].endswith("_1920p.mp4")
    assert data["video_id"] and data["clip_id"]
    assert data["edit_url"] == f"/clips/{data['clip_id']}/edit"

    # Linked Studio project and editable clip work identically to YouTube clips
    vid_res = client.get(f"/api/videos/{data['video_id']}")
    assert vid_res.status_code == 200
    assert vid_res.json()["source_type"] == "instagram"
    assert vid_res.json()["clips_count"] == 1

    # Lazy auto-captions transcription works even though AI splitting was skipped
    fake_segments = [
        TranscriptSegment(
            id=0,
            start=0.5,
            end=4.2,
            text="Quick productivity tip for developers",
            words=[
                TranscriptWord(word="Quick", start=0.5, end=1.0),
                TranscriptWord(word="productivity", start=1.1, end=2.0),
                TranscriptWord(word="tip", start=2.1, end=2.6),
                TranscriptWord(word="for", start=2.7, end=3.1),
                TranscriptWord(word="developers", start=3.2, end=4.2),
            ],
        )
    ]
    with patch("app.api.routes_clips.transcribe_audio_with_whisper", return_value=(fake_segments, "en")):
        cap_res = client.post(f"/api/clips/{data['clip_id']}/auto-captions")
    assert cap_res.status_code == 200, cap_res.text
    assert cap_res.json()["captions_enabled"] is True
    assert len(cap_res.json()["subtitles"]) >= 1

    # Edit trim/aspect ratio (including <3s test or full length) and download rendered MP4
    edit_res = client.patch(
        f"/api/clips/{data['clip_id']}",
        json={"title": "Edited IG Reel", "trim_start": 1.0, "trim_end": 8.0, "aspect_ratio": "1:1"},
    )
    assert edit_res.status_code == 200, edit_res.text
    assert edit_res.json()["duration"] == 7.0
    assert edit_res.json()["aspect_ratio"] == "1:1"

    edited_dl = client.get(f"/api/clips/{data['clip_id']}/download?quality=720p&aspect_ratio=1:1")
    assert edited_dl.status_code == 200
    assert edited_dl.headers["content-type"] == "video/mp4"
    assert len(edited_dl.content) > 5000

    # Verify list, thumbnail, preview stream, and direct attachment download
    list_res = client.get("/api/instagram")
    assert list_res.status_code == 200
    assert any(item["id"] == data["id"] for item in list_res.json())

    thumb_res = client.get(data["thumbnail_url"])
    assert thumb_res.status_code == 200
    assert thumb_res.headers["content-type"] == "image/jpeg"

    dl_res = client.get(data["download_url"])
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "video/mp4"
    assert "attachment" in dl_res.headers["content-disposition"]
    assert len(dl_res.content) > 5000

    del_res = client.delete(f"/api/instagram/{data['id']}")
    assert del_res.status_code == 204
    assert client.get(data["download_url"]).status_code == 404


def test_instagram_ssl_error_and_proxy_cookie_opts(client, test_settings, tmp_path):
    cookie_file = tmp_path / "ig_cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    test_settings.ytdlp_proxy = "http://127.0.0.1:8888"
    test_settings.instagram_cookies_file = cookie_file

    captured_opts = {}

    class FailingSslYdl:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, _url, download=True):
            raise RuntimeError(
                "ERROR: [Instagram] DgNBGrxhkRY: Unable to download webpage: "
                "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1011); "
                "please report this issue on https://github.com/yt-dlp/yt-dlp/issues?q="
            )

    try:
        with patch("yt_dlp.YoutubeDL", FailingSslYdl):
            res = client.post(
                "/api/instagram/download",
                json={"url": "https://www.instagram.com/reel/DgNBGrxhkRY/"},
            )
    finally:
        test_settings.ytdlp_proxy = None
        test_settings.instagram_cookies_file = None

    assert res.status_code == 502
    detail = res.json()["detail"]
    assert "TLS connection to Instagram" in detail
    assert "github.com/yt-dlp" not in detail
    assert captured_opts["proxy"] == "http://127.0.0.1:8888"
    assert captured_opts["cookiefile"] == str(cookie_file)
    assert captured_opts["socket_timeout"] == 20
    assert captured_opts["source_address"] == "0.0.0.0"
