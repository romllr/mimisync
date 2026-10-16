import json
import subprocess
import sys
import threading
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from mimisync.api import create_app
from mimisync.catalog import ENGINES
from mimisync.adapters import ADAPTERS
from mimisync.hardware import recommendation
from mimisync.media import probe, prepare, export
from mimisync.process import run, Cancelled
from mimisync.store import Store

TOKEN = "test-token-" + "a" * 40


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "app", TOKEN)) as client:
        client.headers["Authorization"] = f"Bearer {TOKEN}"
        yield client


@pytest.fixture
def samples(tmp_path):
    video, audio = tmp_path / "video.mp4", tmp_path / "audio.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            str(audio),
        ],
        check=True,
    )
    return video, audio


def test_auth_required_and_query_token_scoped(client):
    assert client.get("/health", headers={"Authorization": ""}).status_code == 401
    assert (
        client.get("/health?token=" + TOKEN, headers={"Authorization": ""}).status_code
        == 401
    )
    assert client.get("/health").json()["status"] == "ok"
    assert (
        client.post("/jobs", headers={"Authorization": ""}, json={}).status_code == 401
    )


def test_catalog_and_distinct_versions(client):
    models = client.get("/models").json()
    assert len(models) == 3
    assert all(not m["ready"] for m in models)
    assert models[1]["commit"] != models[2]["commit"]
    assert models[1]["checkpoint_repo"] != models[2]["checkpoint_repo"]
    assert client.get("/models/unknown/preflight").status_code == 404


def test_license_required_before_install(client):
    r = client.post("/models/musetalk-1.5/actions", json={"action": "environment"})
    assert r.status_code == 400
    assert "licenças" in r.json()["detail"]


def test_upload_validation_and_range(client, samples):
    video, audio = samples
    with video.open("rb") as f:
        response = client.post(
            "/media", files={"file": ("original with spaces.mp4", f, "video/mp4")}
        )
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["width"] == 320 and record["fps"] == "30/1"
    assert "path" not in record
    ranged = client.get(
        "/media/" + record["id"] + "/file?token=" + TOKEN,
        headers={"Authorization": "", "Range": "bytes=0-31"},
    )
    assert ranged.status_code == 206 and len(ranged.content) == 32
    assert (
        client.post("/media", files={"file": ("bad.mp4", b"invalid")}).status_code
        == 422
    )
    assert (
        client.post("/media", files={"file": ("bad.exe", b"invalid")}).status_code
        == 415
    )
    assert len(client.get("/media").json()) == 1


def test_render_does_not_fake_missing_model(client, samples):
    ids = []
    for file in samples:
        with file.open("rb") as f:
            ids.append(
                client.post("/media", files={"file": (file.name, f)}).json()["id"]
            )
    payload = {"model": "musetalk-1.5", "video_id": ids[0], "audio_id": ids[1]}
    assert client.post("/jobs", json=payload).status_code == 409
    assert client.get("/jobs").json() == []
    payload["params"] = {"steps": 0}
    assert client.post("/jobs", json=payload).status_code == 422
    payload["params"] = {}
    payload["start"] = 20
    assert client.post("/jobs", json=payload).status_code == 400


def test_real_ffmpeg_prepare_export(samples, tmp_path):
    video, audio = samples
    work = tmp_path / "work"
    work.mkdir()
    log = []
    cancel = threading.Event()
    v, a = prepare(str(video), str(audio), work, 0, 0.8, True, log.append, cancel)
    assert probe(v)["fps"] == "25/1"
    assert probe(a)["has_audio"]
    # Tests export using an FFmpeg fixture; this is deliberately not an inference test.
    info = export(
        v,
        str(audio),
        work / "output.mp4",
        str(video),
        0,
        0.8,
        18,
        work,
        log.append,
        cancel,
    )
    assert info["width"] == 320 and info["height"] == 180
    assert info["fps"] == "30/1" and info["has_audio"]
    assert abs(info["duration"] - 0.8) < 0.1


@pytest.mark.parametrize("id", list(ENGINES))
def test_adapter_arguments_match_official_cli(id, tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    args = ADAPTERS[id].command(
        Path("/env/bin/python"),
        Path("/source"),
        work,
        {
            "steps": 30,
            "guidance": 1.5,
            "batch_size": 4,
            "extra_margin": 10,
            "cheek_width": 90,
            "parsing_mode": "jaw",
            "seed": 1247,
        },
        0,
    )
    assert args[:3] == ["/env/bin/python", "-m", "scripts.inference"]
    if id.startswith("musetalk"):
        assert args[args.index("--version") + 1] == "v15"
        assert "musetalkV15/unet.pth" in " ".join(args)
        config = json.loads((work / "inference.json").read_text())
        assert config["job"]["result_name"] == str(work / "generated.mp4")
    else:
        assert args[args.index("--unet_config_path") + 1] == ENGINES[id].config
        assert args[args.index("--video_out_path") + 1] == str(work / "generated.mp4")


def test_queue_records_interrupted_on_restart(tmp_path):
    first = Store(tmp_path / "jobs.db")
    job = first.create("render", model="musetalk-1.5")
    first.update(job["id"], status="running")
    second = Store(tmp_path / "jobs.db")
    assert second.get("jobs", job["id"])["status"] == "interrupted"


def test_process_cancellation_kills_actual_child(tmp_path):
    event = threading.Event()
    timer = threading.Timer(0.25, event.set)
    timer.start()
    started = time.monotonic()
    with pytest.raises(Cancelled):
        run(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            tmp_path,
            lambda _: None,
            event,
        )
    assert time.monotonic() - started < 5


def test_recommendation_uses_free_memory():
    assert recommendation({"gpus": []}, ENGINES) is None
    assert recommendation({"gpus": [{"free_mb": 9000}]}, ENGINES) == "latentsync-1.5"
    assert recommendation({"gpus": [{"free_mb": 20000}]}, ENGINES) == "latentsync-1.6"


def test_cli_loopback_api_and_parent_shutdown(tmp_path):
    import os
    import socket
    import urllib.request
    import urllib.error

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "MIMISYNC_DATA": str(tmp_path / "runtime")}
    p = subprocess.Popen(
        [sys.executable, "-m", "mimisync", "--token-stdin", "--port", str(port)],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
    try:
        p.stdin.write(TOKEN + "\n")
        p.stdin.flush()
        url = f"http://127.0.0.1:{port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(100):
            try:
                response = opener.open(
                    urllib.request.Request(
                        url + "/health", headers={"Authorization": "Bearer " + TOKEN}
                    ),
                    timeout=1,
                )
                assert json.load(response)["status"] == "ok"
                break
            except (OSError, urllib.error.URLError):
                if p.poll() is not None:
                    pytest.fail(p.stderr.read())
                time.sleep(0.05)
        else:
            pytest.fail("API did not become ready")
        with pytest.raises(urllib.error.HTTPError) as unauthorized:
            opener.open(url + "/system", timeout=2)
        assert unauthorized.value.code == 401
        system = json.load(
            opener.open(
                urllib.request.Request(
                    url + "/system", headers={"Authorization": "Bearer " + TOKEN}
                ),
                timeout=15,
            )
        )
        assert system["ffmpeg"] and system["ffprobe"]
        p.stdin.close()
        assert p.wait(timeout=15) == 0
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def test_one_click_model_install_runs_both_stages(client, monkeypatch):
    """Orchestration test only: no claim of real model inference."""
    models = client.app.state.models
    steps = []
    monkeypatch.setattr(models, "preflight", lambda _: {"issues": []})
    monkeypatch.setattr(
        models, "install_environment", lambda *args: steps.append("environment")
    )
    monkeypatch.setattr(models, "download", lambda *args: steps.append("checkpoints"))
    rejected = client.post("/models/musetalk-1.5/actions", json={"action": "install"})
    assert rejected.status_code == 400
    response = client.post(
        "/models/musetalk-1.5/actions",
        json={"action": "install", "licenses_reviewed": True},
    )
    assert response.status_code == 202
    client.app.state.worker.queue.join()
    assert steps == ["environment", "checkpoints"]
    job = client.app.state.store.get("jobs", response.json()["id"])
    assert job["status"] == "completed"
    assert job["kind"] == "install"
    assert models.status("musetalk-1.5")["ready"] is False
