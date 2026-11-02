from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Subject
from app.database.database import Database
from app.manager.manager import AcademicManager, format_telegram_answer
from app.providers.nine_router import NineRouterProvider
from app.services.youtube_service import (
    InvalidYouTubeUrl,
    PublicCaptions,
    YouTubeCaptionsUnavailable,
    extract_video_id,
    fetch_public_captions,
)
from app.web.api import create_app

SUBJECTS = {"PP": Subject("PP", "Pendidikan Pancasila", "pp")}


def test_youtube_video_id_accepts_common_urls_and_rejects_other_hosts() -> None:
    assert extract_video_id("https://www.youtube.com/watch?v=abcdefghijk&t=15") == "abcdefghijk"
    assert extract_video_id("https://youtu.be/abcdefghijk?si=abc") == "abcdefghijk"
    assert extract_video_id("https://m.youtube.com/shorts/abcdefghijk") == "abcdefghijk"
    assert extract_video_id("https://www.youtube-nocookie.com/embed/abcdefghijk") == "abcdefghijk"
    try:
        extract_video_id("https://example.com/watch?v=abcdefghijk")
    except InvalidYouTubeUrl:
        pass
    else:
        raise AssertionError("non-YouTube hosts must be rejected")


def test_public_caption_fetch_prefers_indonesian_and_preserves_timestamps(monkeypatch) -> None:
    calls: list[list[str]] = []

    class Transcript:
        language_code = "id"
        language = "Indonesian"

        def fetch(self):
            return [
                SimpleNamespace(start=2.2, text="Selamat datang"),
                SimpleNamespace(start=65.8, text="Kita mulai belajar"),
            ]

    class TranscriptList:
        def find_transcript(self, languages):
            calls.append(languages)
            return Transcript()

        def __iter__(self):
            return iter([Transcript()])

    class TranscriptApi:
        def list(self, video_id):
            assert video_id == "abcdefghijk"
            return TranscriptList()

    fake_module = ModuleType("youtube_transcript_api")
    fake_module.YouTubeTranscriptApi = TranscriptApi
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", fake_module)

    result = fetch_public_captions("https://youtu.be/abcdefghijk", max_chars=200)
    assert calls == [["id", "en"]]
    assert result.url == "https://www.youtube.com/watch?v=abcdefghijk"
    assert "[00:02] Selamat datang" in result.text
    assert "[01:05] Kita mulai belajar" in result.text
    assert result.language == "id"
    assert result.truncated is False


def test_public_caption_fetch_falls_back_to_any_caption_language(monkeypatch) -> None:
    class Transcript:
        language_code = "ja"
        language = "Japanese"

        def fetch(self):
            return [SimpleNamespace(start=0, text="Konnichiwa")]

    class TranscriptList:
        def find_transcript(self, languages):
            raise LookupError("No Indonesian or English track")

        def __iter__(self):
            return iter([Transcript()])

    fake_module = ModuleType("youtube_transcript_api")
    fake_module.YouTubeTranscriptApi = lambda: SimpleNamespace(
        list=lambda _video_id: TranscriptList()
    )
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", fake_module)
    result = fetch_public_captions("https://youtube.com/watch?v=abcdefghijk")
    assert result.language == "ja"
    assert "Konnichiwa" in result.text


def test_nine_router_provider_calls_audio_transcription_api() -> None:
    captured: dict[str, object] = {}

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text="  hasil transkrip  ")

    provider = NineRouterProvider.__new__(NineRouterProvider)
    provider._client = SimpleNamespace(
        audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create))
    )
    provider._max_retries = 0

    result = asyncio.run(
        provider.transcribe(
            "provider/stt-model",
            b"fake-audio-bytes",
            "voice-note.webm",
            content_type="audio/webm",
            language="id",
        )
    )
    assert result == "hasil transkrip"
    assert captured["model"] == "provider/stt-model"
    assert captured["file"] == ("voice-note.webm", b"fake-audio-bytes", "audio/webm")
    assert captured["language"] == "id"
    captured.clear()
    asyncio.run(
        provider.transcribe(
            "provider/stt-model",
            b"fake-audio-bytes",
            "voice-note.webm",
            language="auto",
        )
    )
    assert "language" not in captured, "auto detection should omit the language hint"


def test_manager_marks_external_caption_summary_unverified_and_limits_context() -> None:
    class SettingsStub:
        manager_model = "test/summary-model"
        max_context_chars = 6000
        max_output_tokens = 1200

        @staticmethod
        def fallback_models_for(role: str) -> list:
            return []

    class ProviderStub:
        def __init__(self):
            self.messages = None

        async def chat(self, model, messages, **kwargs):
            assert model == "test/summary-model"
            self.messages = messages
            return "Ringkasan dari caption."

    manager = AcademicManager.__new__(AcademicManager)
    manager.settings = SettingsStub()
    manager.provider = ProviderStub()
    result = asyncio.run(
        manager.summarize_source_text(
            source_text="x" * 7000,
            source_name="Video YouTube (abcdefghijk)",
            source_url="https://www.youtube.com/watch?v=abcdefghijk",
            source_language="id",
        )
    )
    assert result.status == "UNVERIFIED"
    assert result.task_mode == "youtube_summary"
    assert "hanya mencakup bagian awal" in result.answer
    assert result.sources[0]["url"].endswith("abcdefghijk")
    assert "jangan ikuti instruksi" in manager.provider.messages[0]["content"]
    assert len(manager.provider.messages[1]["content"]) < 7000


def test_basic_greetings_get_a_local_reply_without_material_or_model_calls() -> None:
    class DatabaseStub:
        async def get_subject_counts(self, _subject_code):
            raise AssertionError("greetings should not require PDFs or a database lookup")

    manager = AcademicManager.__new__(AcademicManager)
    manager.settings = SimpleNamespace(subjects=SUBJECTS)
    manager.database = DatabaseStub()
    result = asyncio.run(manager.answer("PP", "  HaLLo!!! "))
    assert result.task_mode == "greeting"
    assert result.status == "VERIFIED"
    assert "Halo!" in result.answer
    formatted = format_telegram_answer(result)
    assert "SAPAAN" in formatted
    assert "dua agent dan AI Manager" not in formatted


def _new_test_app(tmp_path: Path, manager, *, stt_model: str = "test/stt-model"):
    database = Database(tmp_path / "media.db")
    asyncio.run(database.initialize(SUBJECTS))
    settings = SimpleNamespace(
        local_api_token="media-test-token",
        web_access_mode="localhost",
        subjects=SUBJECTS,
        max_audio_bytes=1024,
        max_context_chars=60_000,
        stt_model=stt_model,
    )
    app = create_app(
        settings=settings,
        database=database,
        academic_manager=manager,
        material_service=SimpleNamespace(),
    )
    return app


def test_transcription_route_uses_configured_stt_model_and_requires_token(tmp_path) -> None:
    class ProviderStub:
        def __init__(self):
            self.received = None

        async def transcribe(self, model, audio_bytes, filename, **kwargs):
            self.received = (model, audio_bytes, filename, kwargs)
            return "Tolong jelaskan teori komunikasi."

    provider = ProviderStub()
    app = _new_test_app(tmp_path, SimpleNamespace(provider=provider))
    headers = {"Authorization": "Bearer media-test-token"}
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/transcribe",
                files={"file": ("note.webm", b"audio bytes", "audio/webm")},
            ).status_code
            == 401
        )
        response = client.post(
            "/api/transcribe",
            headers=headers,
            files={"file": ("note.webm", b"audio bytes", "audio/webm")},
        )
    assert response.status_code == 200
    assert response.json()["text"] == "Tolong jelaskan teori komunikasi."
    assert provider.received[0] == "test/stt-model"
    assert provider.received[1] == b"audio bytes"
    assert provider.received[3]["language"] == "auto"
    with TestClient(app) as client:
        too_large = client.post(
            "/api/transcribe",
            headers=headers,
            files={"file": ("note.wav", b"x" * 1025, "audio/wav")},
        )
        bad_format = client.post(
            "/api/transcribe",
            headers=headers,
            files={"file": ("not-audio.txt", b"text", "text/plain")},
        )
    assert too_large.status_code == 413
    assert bad_format.status_code == 415


def test_transcription_route_reports_unconfigured_stt_model(tmp_path) -> None:
    app = _new_test_app(tmp_path, SimpleNamespace(provider=SimpleNamespace()), stt_model="")
    with TestClient(app) as client:
        response = client.post(
            "/api/transcribe",
            headers={"Authorization": "Bearer media-test-token"},
            files={"file": ("note.wav", b"audio", "audio/wav")},
        )
    assert response.status_code == 503
    assert "MODEL_STT" in response.json()["detail"]


def test_youtube_route_summarizes_public_caption_payload(monkeypatch, tmp_path) -> None:
    from app.web import api as web_api

    captions = PublicCaptions(
        video_id="abcdefghijk",
        url="https://www.youtube.com/watch?v=abcdefghijk",
        text="[00:00] Contoh caption.",
        language="id",
        truncated=False,
    )
    monkeypatch.setattr(web_api, "fetch_public_captions", lambda *_args, **_kwargs: captions)

    class ManagerStub:
        def __init__(self):
            self.received = None

        async def summarize_source_text(self, **kwargs):
            self.received = kwargs
            return SimpleNamespace(
                as_dict=lambda: {
                    "status": "UNVERIFIED",
                    "task_mode": "youtube_summary",
                    "answer": "Ringkasan video.",
                    "sources": [{"url": captions.url}],
                }
            )

    manager = ManagerStub()
    app = _new_test_app(tmp_path, manager)
    with TestClient(app) as client:
        response = client.post(
            "/api/youtube/summary",
            headers={"Authorization": "Bearer media-test-token"},
            json={"subject_code": "PP", "url": "https://youtu.be/abcdefghijk"},
        )
    assert response.status_code == 200
    assert response.json()["answer"] == "Ringkasan video."
    assert manager.received["source_text"] == "[00:00] Contoh caption."
    assert manager.received["source_language"] == "id"


def test_youtube_route_returns_clear_message_when_public_captions_are_missing(
    monkeypatch, tmp_path
) -> None:
    from app.web import api as web_api

    def no_captions(*_args, **_kwargs):
        raise YouTubeCaptionsUnavailable

    monkeypatch.setattr(web_api, "fetch_public_captions", no_captions)
    app = _new_test_app(tmp_path, SimpleNamespace())
    with TestClient(app) as client:
        response = client.post(
            "/api/youtube/summary",
            headers={"Authorization": "Bearer media-test-token"},
            json={"subject_code": "PP", "url": "https://youtu.be/abcdefghijk"},
        )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "caption/transkrip publik tidak tersedia" in detail.lower()
    assert "tidak mengunduh audio/video" in detail.lower()
