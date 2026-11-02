from __future__ import annotations

import asyncio
import wave
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Subject
from app.database.database import Database
from app.services import tts as tts_mod
from app.services import video_service as vs
from app.services import webfetch
from app.services.tts import pick_engine, synthesize, voice_for_engine
from app.services.video_service import (
    Scene,
    VideoService,
    assemble_video,
    build_srt,
    preflight,
    render_slide,
    split_script,
    wav_duration,
)
from app.settings_update import update_settings
from app.web.api import create_app
from app.web.jobs import JobManager

SUBJECTS = {"PP": Subject("PP", "Pendidikan Pancasila", "pp")}


def _write_wav(path: Path, seconds: float = 0.5) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * 16000)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * frames)
    return path


def test_split_script_groups_paragraphs() -> None:
    scenes = split_script("Satu.\nDua.\nTiga.\nEmpat.", 2)
    assert len(scenes) == 2
    assert scenes[0].bullets == ["Satu.", "Dua."]
    assert "Satu." in scenes[0].narration


def test_split_script_empty_raises() -> None:
    try:
        split_script("   \n  ", 3)
    except ValueError as exc:
        assert "rangkuman" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_render_slide_and_srt_and_duration(tmp_path: Path) -> None:
    scene = Scene(title="Judul", narration="Narasi.", bullets=["Poin satu"])
    png = render_slide(scene, 0, 2, "PP", "topik", tmp_path / "s0.png")
    assert png.is_file() and png.stat().st_size > 1000
    srt = build_srt([scene, scene], [1.5, 2.0], tmp_path / "s.srt")
    text = srt.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,500" in text
    assert "00:00:01,500 --> 00:00:03,500" in text
    assert abs(wav_duration(_write_wav(tmp_path / "a.wav", 2.0)) - 2.0) < 0.05


def test_voice_for_engine_defaults() -> None:
    assert voice_for_engine("edge", "id_ID-fajri-medium") == "id-ID-ArdiNeural"
    assert voice_for_engine("edge", "id-ID-GadisNeural") == "id-ID-GadisNeural"
    assert voice_for_engine("piper", "") == "id_ID-fajri-medium"


def test_pick_engine_prefers_piper_then_edge(monkeypatch) -> None:
    monkeypatch.setattr(tts_mod, "available_engines", lambda: {"piper": "/p", "edge": "/e"})
    assert pick_engine("auto") == "piper"
    monkeypatch.setattr(tts_mod, "available_engines", lambda: {"piper": None, "edge": "/e"})
    assert pick_engine("auto") == "edge"
    monkeypatch.setattr(tts_mod, "available_engines", lambda: {"piper": None, "edge": None})
    try:
        pick_engine("auto")
    except ValueError as exc:
        assert "pip install" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_synthesize_piper_command_and_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(tts_mod, "available_engines", lambda: {"piper": "/bin/piper", "edge": None})
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        out = Path(command[command.index("--output_file") + 1])
        _write_wav(out)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(tts_mod.subprocess, "run", fake_run)
    out = synthesize("Halo dunia", tmp_path / "n.wav", engine="piper", voice="v1")
    assert out.is_file()
    assert calls[0][:3] == ["/bin/piper", "--model", "v1"]

    def bad_run(command, **kwargs):
        return SimpleNamespace(returncode=1, stderr=b"boom")

    monkeypatch.setattr(tts_mod.subprocess, "run", bad_run)
    try:
        synthesize("Halo", tmp_path / "x.wav", engine="piper", voice="v1")
    except ValueError as exc:
        assert "gagal" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_preflight_requires_ffmpeg(monkeypatch) -> None:
    monkeypatch.setattr(vs, "ffmpeg_binary", lambda: None)
    try:
        preflight(SimpleNamespace(tts_provider="auto"))
    except ValueError as exc:
        assert "ffmpeg" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_assemble_video_builds_filter_command(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        Path(command[-1]).write_bytes(b"fake-mp4")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(vs.subprocess, "run", fake_run)
    (tmp_path / "s0.png").write_bytes(b"img")
    (tmp_path / "a0.wav").write_bytes(b"wav")
    (tmp_path / "s.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHai\n", encoding="utf-8")
    out = assemble_video(
        "ffmpeg",
        [tmp_path / "s0.png"],
        [tmp_path / "a0.wav"],
        [1.0],
        tmp_path / "s.srt",
        tmp_path / "out.mp4",
    )
    assert out.is_file()
    command = calls[0]
    assert "libx264" in command and "mov_text" in command
    assert any("concat=n=1:v=1:a=0[v]" in arg for arg in command)


def test_build_video_end_to_end_mocked(monkeypatch, tmp_path: Path) -> None:
    settings = SimpleNamespace(
        tts_provider="auto",
        tts_voice="v1",
        video_max_scenes=2,
        videos_dir=tmp_path / "videos",
    )
    paragraphs = "\n".join(f"Paragraf {name} tentang fotosintesis." for name in "ABCD")
    manager = SimpleNamespace(summarize=lambda *a, **k: _coro(SimpleNamespace(answer=paragraphs)))
    db_calls: dict = {}

    async def _create_video(**kwargs):
        db_calls["created"] = kwargs

    async def _update_video_status(video_id, status, **fields):
        db_calls["status"] = (video_id, status, fields)

    database = SimpleNamespace(create_video=_create_video, update_video_status=_update_video_status)
    monkeypatch.setattr(
        vs, "preflight", lambda settings: {"ffmpeg": "ffmpeg", "tts_engine": "piper"}
    )

    def fake_synth(text, output, **kwargs):
        return _write_wav(Path(output))

    monkeypatch.setattr(vs.tts_engine, "synthesize", fake_synth)
    monkeypatch.setattr(vs, "normalize_audio", lambda ffmpeg, src, dest: _write_wav(Path(dest)))

    def fake_assemble(ffmpeg, slides, wavs, durations, subtitles, output):
        Path(output).write_bytes(b"fake-mp4")
        return Path(output)

    monkeypatch.setattr(vs, "assemble_video", fake_assemble)
    stages: list[str] = []
    service = VideoService(settings, manager, database)
    meta = asyncio.run(
        service.build_video(
            subject_code="PP",
            topic="fotosintesis",
            progress=lambda stage, detail="": stages.append(stage),
        )
    )
    assert meta["scene_count"] == 2
    assert meta["decision_log"]["tts_engine"] == "piper"
    assert meta["download_url"].endswith("/download")
    assert Path(meta["file_path"]).is_file()
    assert stages[:3] == ["preflight", "research", "script"]
    assert db_calls["status"][1] == "done"


def _coro(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner()


def test_build_video_empty_summary_raises(monkeypatch, tmp_path: Path) -> None:
    settings = SimpleNamespace(
        tts_provider="auto",
        tts_voice="v1",
        video_max_scenes=2,
        videos_dir=tmp_path / "videos",
    )
    manager = SimpleNamespace(summarize=lambda *a, **k: _coro(SimpleNamespace(answer="  ")))
    monkeypatch.setattr(vs, "preflight", lambda settings: {"ffmpeg": "f", "tts_engine": "piper"})
    service = VideoService(settings, manager, SimpleNamespace())
    try:
        asyncio.run(service.build_video(subject_code="PP", topic="x"))
    except ValueError as exc:
        assert "kosong" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def _video_stubs():
    async def _noop(*args, **kwargs):
        return None

    async def _add_message(conversation_id, role, content):
        return 1

    database = SimpleNamespace(
        upsert_user=_noop, set_active_subject=_noop, add_message=_add_message
    )
    return database


def test_job_video_task_lifecycle() -> None:
    async def scenario():
        seen: list[str] = []

        async def fake_build(**kwargs):
            progress = kwargs.get("progress")
            if progress:
                progress("render", "ffmpeg")
            return {
                "video_id": "v123",
                "title": "PP: x",
                "subject_code": "PP",
                "topic": "x",
                "duration_sec": 9.9,
                "scene_count": 2,
                "download_url": "/api/videos/v123/download",
            }

        video_service = SimpleNamespace(build_video=fake_build)
        manager = JobManager(SimpleNamespace(), _video_stubs(), video_service=video_service)
        await manager.start()
        job = await manager.submit(task="video", subject_code="PP", topic="x", question="")
        await asyncio.wait_for(manager.queue.join(), timeout=10)
        await manager.stop()
        return job, seen

    job, _ = asyncio.run(scenario())
    assert job.status == "done"
    assert job.result["video_id"] == "v123"
    assert job.stage == "done"


def test_job_video_requires_topic() -> None:
    async def scenario():
        manager = JobManager(SimpleNamespace(), _video_stubs(), video_service=SimpleNamespace())
        await manager.start()
        job = await manager.submit(task="video", subject_code="PP", topic="", question="")
        await asyncio.wait_for(manager.queue.join(), timeout=10)
        await manager.stop()
        return job

    job = asyncio.run(scenario())
    assert job.status == "failed"
    assert "Topik" in job.error


def _api_client(tmp_path: Path):
    async def _database() -> Database:
        database = Database(tmp_path / "v.db")
        await database.initialize(SUBJECTS)
        return database

    settings = SimpleNamespace(
        local_api_token="vid-secret",
        web_access_mode="localhost",
        subjects=SUBJECTS,
        max_pdf_bytes=1024,
    )
    app = create_app(
        settings=settings,
        database=asyncio.run(_database()),
        academic_manager=SimpleNamespace(provider=SimpleNamespace(close=lambda: None)),
        material_service=SimpleNamespace(),
    )
    return app


def test_api_video_and_web_and_patterns(tmp_path: Path, monkeypatch) -> None:
    app = _api_client(tmp_path)
    headers = {"Authorization": "Bearer vid-secret"}
    with TestClient(app) as client:
        assert client.get("/api/videos", headers=headers).json() == []
        assert client.get("/api/videos/x/download", headers=headers).status_code == 404
        bad = client.post(
            "/api/jobs",
            json={"task": "video", "subject_code": "PP", "topic": ""},
            headers=headers,
        )
        assert bad.status_code == 422
        patterns = client.get("/api/patterns", headers=headers).json()
        assert "explain_simple" in patterns
        monkeypatch.setattr(
            webfetch, "duckduckgo_links", lambda query, limit=3: [("T", "http://e")]
        )
        monkeypatch.setattr(webfetch, "fetch_text", lambda url, timeout=20: "isi " * 200)
        app.state.academic_manager.summarize_source_text = lambda **k: _coro(
            SimpleNamespace(as_dict=lambda: {"status": "OK"})
        )
        good = client.post("/api/web", json={"query": "fotosintesis"}, headers=headers)
        assert good.status_code == 200 and good.json()["status"] == "OK"


def test_settings_new_keys_roundtrip(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("RAG_TOP_K=6\n", encoding="utf-8")
    settings = SimpleNamespace(
        env_file=env_file,
        subjects={},
        models={},
        tts_provider="auto",
        tts_voice="v",
        video_max_scenes=6,
        rag_mode="vector",
        memory_enabled=True,
        skills_learn_enabled=True,
        web_research_enabled=False,
    )
    report = update_settings(
        settings,
        {
            "tts_provider": "edge",
            "rag_mode": "tree",
            "memory_enabled": "false",
            "video_max_scenes": 4,
            "tts_voice": "custom-voice",
        },
    )
    assert settings.tts_provider == "edge"
    assert settings.rag_mode == "tree"
    assert settings.memory_enabled is False
    assert settings.video_max_scenes == 4
    assert report["needs_restart"] == []
    assert "TTS_PROVIDER=edge" in env_file.read_text(encoding="utf-8")
    try:
        update_settings(settings, {"rag_mode": "quantum"})
    except ValueError as exc:
        assert "RAG_MODE" in str(exc)
    else:
        raise AssertionError("expected ValueError")
