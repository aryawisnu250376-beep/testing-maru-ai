"""Regression tests for mobile access, approval integrity and historical metrics."""

import base64
import json
import sqlite3
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from src import approve, dashboard, db, queue, security, voice


def test_password_minimum_and_session_logout(monkeypatch):
    monkeypatch.setenv("STUDIO_PASSWORD", "pendek")
    with pytest.raises(RuntimeError):
        security.from_environment("0.0.0.0")
    monkeypatch.delenv("STUDIO_PASSWORD")
    with pytest.raises(RuntimeError):
        security.from_environment("0.0.0.0")
    auth = security.AuthManager("rahasia-panjang-untuk-uji")
    token, ttl = auth.login("rahasia-panjang-untuk-uji", "client")
    assert ttl == security.SESSION_TTL and auth.valid(token)
    assert not auth.valid(token, now=2**60)
    auth.logout(token)
    assert not auth.valid(token)


def test_login_rate_limit():
    auth = security.AuthManager("rahasia-panjang-untuk-uji")
    for _ in range(5):
        assert auth.login("salah", "client")[0] is None
    token, wait = auth.login("rahasia-panjang-untuk-uji", "client")
    assert token is None and wait > 0


def test_approval_binds_exact_script_and_rejects_bare_file(
    fresh_db, cfg, cluster, tmp_path, monkeypatch
):
    from src import scriptwriter

    sc = scriptwriter.write_with_template(cluster, cfg)
    db.save_episode("ep-auth", "pending_approval", cluster, sc)
    monkeypatch.setattr(approve, "out_dir", lambda _: tmp_path)
    with pytest.raises(PermissionError):
        approve.require_approval("ep-auth", sc)
    (tmp_path / "decision.json").write_text('{"status":"approve"}')
    with pytest.raises(PermissionError):
        approve.require_approval("ep-auth", sc)
    approve.apply_decision("ep-auth", "approve")
    approve.require_approval("ep-auth", sc)
    changed = json.loads(json.dumps(sc))
    changed["beats"][1]["narration"] += " Klaim baru."
    with pytest.raises(PermissionError):
        approve.require_approval("ep-auth", changed)
    approve.invalidate("ep-auth")
    with pytest.raises(PermissionError):
        approve.require_approval("ep-auth", sc)


def test_metrics_history_same_second_and_latest_learning(fresh_db, monkeypatch):
    db.save_episode(
        "ep-m", "rendered", {}, {"hook_variant": "A", "beats": []}, {"duration_sec": 40}
    )
    monkeypatch.setattr(db, "now", lambda: "2026-11-01T00:00:00+00:00")
    db.save_metrics("ep-m", {"views": 100, "avg_watch": 20, "retention_3s": 80})
    db.save_metrics(
        "ep-m", {"views": 200, "avg_watch": 30, "retention_3s": 60, "hook_variant": "B"}
    )
    latest = db.latest_metrics("ep-m")
    assert latest["views"] == 200 and latest["hook_variant"] == "B"
    with db.conn() as c:
        assert c.execute("select count(*) from metrics").fetchone()[0] == 2
    from src import learning

    rows = learning.collect_dataset()
    assert len(rows) == 1 and rows[0]["retention"] == 0.75 and rows[0]["retention_3s"] == 0.6


@pytest.mark.parametrize(
    "payload",
    [
        {"views": -1},
        {"views": True},
        {"views": 1.5},
        {"avg_watch": float("nan")},
        {"retention_3s": 101},
        {"views": 1, "likes": 2},
    ],
)
def test_metrics_invalid(fresh_db, payload):
    db.save_episode("ep-m", "rendered", {}, {}, {})
    with pytest.raises(ValueError):
        db.validate_metrics("ep-m", payload)


def test_legacy_migration_preserves_data_and_backups(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    c = sqlite3.connect(path)
    c.executescript("""CREATE TABLE episodes (id TEXT PRIMARY KEY,status TEXT,topic TEXT,script_json TEXT,paths_json TEXT,created_at TEXT,updated_at TEXT);
    CREATE TABLE metrics (episode_id TEXT,views INTEGER,avg_watch REAL,likes INTEGER,comments INTEGER,shares INTEGER,fetched_at TEXT,PRIMARY KEY(episode_id,fetched_at));
    CREATE TABLE jobs (id INTEGER PRIMARY KEY,episode_id TEXT,kind TEXT,status TEXT,attempts INTEGER,max_attempts INTEGER,payload TEXT,result TEXT,error TEXT,created_at TEXT,started_at TEXT,finished_at TEXT);
    INSERT INTO episodes VALUES ('ep-old','pending_approval','{}','{"title":"lama"}','{}','2026-01-01','2026-01-01');
    INSERT INTO metrics VALUES ('ep-old',12,5,1,0,0,'2026-01-01');""")
    c.commit()
    c.close()
    db.set_db_path(path)
    db.init()
    assert db.get_episode("ep-old")["script"]["title"] == "lama"
    assert db.latest_metrics("ep-old")["views"] == 12
    assert (tmp_path / "legacy.pre-v2.db").exists()
    assert (tmp_path / "legacy.pre-v3.db").exists()
    db.save_metrics("ep-old", {"views": 13, "avg_watch": 5})
    assert db.latest_metrics("ep-old")["views"] == 13


def test_recording_requires_consent_and_valid_audio(tmp_path):
    import subprocess
    from src.config import find_ffmpeg

    raw = tmp_path / "input.wav"
    subprocess.run(
        [
            find_ffmpeg(),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-ar",
            "44100",
            "-ac",
            "1",
            str(raw),
        ],
        check=True,
    )
    data = base64.b64encode(raw.read_bytes()).decode()
    with pytest.raises(ValueError):
        voice.import_recording(data, tmp_path / "a.wav", False)
    with pytest.raises(ValueError):
        voice.import_recording("not-audio", tmp_path / "a.wav", True)
    meta = voice.import_recording(data, tmp_path / "a.wav", True)
    assert meta["consent"] and 0.9 <= meta["duration_sec"] <= 1.2
    words, alignment = voice.align_recording(tmp_path / "a.wav", "satu dua tiga", 1)
    assert alignment == "estimated" and words


def test_caption_failure_never_silent_copy(tmp_path, monkeypatch):
    from src import render

    monkeypatch.setattr(
        render,
        "_run",
        lambda cmd: type("R", (), {"returncode": 1, "stderr": "caption filter missing"})(),
    )
    (tmp_path / "missing.ass").write_text("[Script Info]\n")
    with pytest.raises(RuntimeError, match="Caption"):
        render.mux(
            tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "out.mp4", tmp_path / "missing.ass"
        )


def test_queue_dedup_and_terminal_failure(fresh_db):
    db.save_episode("ep-q", "approved", {}, {}, {})
    a = queue.enqueue("render", "ep-q")
    b = queue.enqueue("render", "ep-q")
    assert a == b
    job = queue.claim()
    assert queue.retry_or_fail(job, "first") == "retry"
    job = queue.claim(now=2**40)
    assert queue.retry_or_fail(job, "second") == "retry"
    job = queue.claim(now=2**41)
    assert queue.retry_or_fail(job, "third") == "failed"
    assert db.get_episode("ep-q")["status"] == "failed"


@pytest.fixture()
def http_server(fresh_db, monkeypatch):
    monkeypatch.setattr(
        dashboard, "RUNTIME", security.Runtime(security.AuthManager("rahasia-panjang-untuk-uji"))
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), dashboard.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:" + str(server.server_port)
    server.shutdown()
    server.server_close()
    thread.join()


def request(url, path, token=None, payload=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        url + path, data=json.dumps(payload).encode() if payload is not None else None, headers=h
    )
    try:
        r = urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as e:
        r = e
    with r:
        body = r.read()
        return r.status, json.loads(body) if body and "application/json" in r.headers.get(
            "Content-Type", ""
        ) else body


def test_http_auth_login_csrf_and_actions(http_server):
    url = http_server
    assert request(url, "/api/state")[0] == 401
    assert request(url, "/video/ep-x")[0] == 401
    assert request(url, "/api/login", payload={"password": "salah"})[0] == 401
    code, data = request(url, "/api/login", payload={"password": "rahasia-panjang-untuk-uji"})
    assert code == 200
    token = data["token"]
    assert request(url, "/api/state", token)[0] == 200
    assert request(url, "/api/action", token, {"action": "scan"})[0] == 400
    assert (
        request(
            url,
            "/api/action",
            token,
            {"action": "approve", "episode_id": "ep-x", "confirmed": True},
            {"Origin": "https://evil.example"},
        )[0]
        == 403
    )
    assert request(url, "/api/logout", token, {})[0] == 200
    assert request(url, "/api/state", token)[0] == 401


def test_http_range_and_pwa_assets(http_server, tmp_path, monkeypatch):
    from src.config import ROOT

    db.save_episode("ep-media", "rendered", {}, {}, {})
    d = ROOT / "out" / "ep-media"
    d.mkdir(parents=True, exist_ok=True)
    (d / "final.mp4").write_bytes(b"0123456789")
    token = request(
        http_server, "/api/login", payload={"password": "rahasia-panjang-untuk-uji"}
    )[1]["token"]
    req = urllib.request.Request(
        http_server + "/video/ep-media",
        headers={"Authorization": "Bearer " + token, "Range": "bytes=2-5"},
    )
    with urllib.request.urlopen(req) as r:
        assert (
            r.status == 206 and r.read() == b"2345" and r.headers["Content-Range"] == "bytes 2-5/10"
        )
    code, manifest = request(http_server, "/manifest.webmanifest")
    assert code == 200 and json.loads(manifest)["display"] == "standalone"
    assert request(http_server, "/icon-192.png")[0] == 200
    (d / "final.mp4").unlink()
