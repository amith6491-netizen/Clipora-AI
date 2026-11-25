from pathlib import Path
import shutil
import socket
import subprocess
import time

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.core.media_tools import resolve_media_binaries
from app.main import create_app


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


@pytest.fixture(scope="session")
def mongo_uri(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Use running local MongoDB on 27017 or spin up an isolated mongod test instance."""
    if _port_open("127.0.0.1", 27017):
        return "mongodb://127.0.0.1:27017"

    mongod_exe = shutil.which("mongod") or r"C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe"
    if not Path(mongod_exe).exists():
        pytest.skip("mongod executable not found for integration tests.")

    db_dir = tmp_path_factory.mktemp("mongod_data")
    test_port = 27117
    proc = subprocess.Popen(
        [
            mongod_exe,
            "--dbpath",
            str(db_dir),
            "--port",
            str(test_port),
            "--bind_ip",
            "127.0.0.1",
            "--nojournal" if False else "--quiet",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 15.0
        while time.time() < deadline:
            if _port_open("127.0.0.1", test_port):
                break
            time.sleep(0.25)
        else:
            pytest.fail("Timed out waiting for temporary mongod test instance.")
        yield f"mongodb://127.0.0.1:{test_port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture()
def test_settings(tmp_path: Path, mongo_uri: str) -> Settings:
    return Settings(
        mongodb_uri=mongo_uri,
        mongodb_db=f"clipora_test_{tmp_path.name}",
        storage_dir=tmp_path / "storage",
        min_video_duration_seconds=10.0,
        max_video_duration_seconds=1200.0,
        whisper_model_size="tiny",
        min_shorts_count=5,
        max_shorts_count=10,
    )


@pytest.fixture()
def client(test_settings: Settings):
    app = create_app(test_settings)
    with TestClient(app) as tc:
        yield tc


def build_synthetic_color_video(
    out_path: Path,
    duration_sec: float,
    settings: Settings,
    with_audio: bool = True,
    fps: int = 10,
    size: str = "320x180",
) -> Path:
    bins = resolve_media_binaries(settings)
    args = [
        bins.ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=#1e293b:s={size}:r={fps}:d={duration_sec}",
    ]
    if with_audio:
        args.extend(["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=16000:duration={duration_sec}"])
    args.extend(["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"])
    if with_audio:
        args.extend(["-c:a", "aac", "-b:a", "64k"])
    args.append(str(out_path))
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg synthetic video generation failed: {proc.stderr}")
    return out_path
