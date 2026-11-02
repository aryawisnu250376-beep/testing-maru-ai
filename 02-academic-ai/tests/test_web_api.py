from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Settings, Subject
from app.database.database import Database
from app.web.api import create_app, is_private_lan_address

SUBJECTS = {
    "PP": Subject("PP", "Pendidikan Pancasila", "pp"),
    "KAP": Subject("KAP", "Komunikasi Antarpribadi", "kap"),
}


class DummyManager:
    provider = SimpleNamespace(close=lambda: None)


async def _database(path: Path) -> Database:
    database = Database(path)
    await database.initialize(SUBJECTS)
    return database


def test_local_website_serves_ui_and_protects_api_with_bearer_token(tmp_path) -> None:
    database = asyncio.run(_database(tmp_path / "academic_ai.db"))
    settings = SimpleNamespace(
        local_api_token="local-test-secret",
        web_access_mode="localhost",
        subjects=SUBJECTS,
        max_pdf_bytes=1024 * 1024,
    )
    app = create_app(
        settings=settings,
        database=database,
        academic_manager=DummyManager(),
        material_service=SimpleNamespace(),
    )
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "AI ACADEMIC" in page.text
        assert "by arya wisnu" in page.text
        assert 'id="agentOffice"' in page.text
        assert 'id="username"' in page.text
        assert 'id="password"' in page.text
        assert 'id="loginBtn"' in page.text
        assert 'id="token"' not in page.text
        assert 'id="youtubeUrl"' in page.text
        assert 'id="recordBtn"' in page.text
        assert 'id="audioFile"' in page.text
        assert client.get("/api/health").status_code == 401
        assert (
            client.get(
                "/api/health",
                headers={"Authorization": "Bearer not-the-local-token"},
            ).status_code
            == 401
        )
        headers = {"Authorization": "Bearer local-test-secret"}
        assert client.get("/api/health", headers=headers).json()["scope"] == "localhost-only"
        subjects = client.get("/api/subjects", headers=headers).json()
        assert {item["code"] for item in subjects} == {"PP", "KAP"}
        assert client.get("/api/materials/KAP", headers=headers).json() == []
        assert client.get("/api/materials/UNKNOWN", headers=headers).status_code == 404


def test_lan_mode_allows_private_clients_but_rejects_public_clients(tmp_path) -> None:
    database = asyncio.run(_database(tmp_path / "lan.db"))
    settings = SimpleNamespace(
        local_api_token="lan-test-secret",
        local_web_username="student",
        local_web_password="test-password",
        web_access_mode="lan",
        subjects=SUBJECTS,
        max_pdf_bytes=1024 * 1024,
    )
    app = create_app(
        settings=settings,
        database=database,
        academic_manager=DummyManager(),
        material_service=SimpleNamespace(),
    )
    headers = {"Authorization": "Bearer lan-test-secret"}
    with TestClient(app, client=("192.168.1.55", 43210)) as private_client:
        health = private_client.get("/api/health", headers=headers)
        assert health.status_code == 200
        assert health.json()["scope"] == "private-lan"
        login = private_client.post(
            "/api/login", json={"username": "student", "password": "test-password"}
        )
        assert login.status_code == 200
    with TestClient(app, client=("8.8.8.8", 43210)) as public_client:
        assert public_client.get("/api/health", headers=headers).status_code == 403
        assert (
            public_client.post(
                "/api/login", json={"username": "student", "password": "test-password"}
            ).status_code
            == 403
        )


def test_private_lan_address_guard() -> None:
    assert is_private_lan_address("192.168.1.2")
    assert is_private_lan_address("10.0.0.2")
    assert is_private_lan_address("127.0.0.1")
    assert not is_private_lan_address("8.8.8.8")
    assert not is_private_lan_address("not-an-ip")
    assert not is_private_lan_address(None)


def test_settings_lan_mode_binds_all_interfaces_but_local_mode_does_not(monkeypatch) -> None:
    monkeypatch.setenv("NINE_ROUTER_API_KEY", "test-key")
    monkeypatch.setenv("NINE_ROUTER_BASE_URL", "http://127.0.0.1:20128/v1")
    monkeypatch.setenv("WEB_HOST", "127.0.0.1")
    monkeypatch.setenv("MAX_CONTEXT_CHARS", "60000")
    monkeypatch.setenv("MAX_AUDIO_MB", "25")
    monkeypatch.setenv("MODEL_STT", "test/stt-model")
    monkeypatch.setenv("LOCAL_WEB_USERNAME", "test-user")
    monkeypatch.setenv("LOCAL_WEB_PASSWORD", "test-password")
    monkeypatch.setenv("WEB_ACCESS_MODE", "lan")
    lan_settings = Settings.load(require_telegram=False)
    assert lan_settings.web_access_mode == "lan"
    assert lan_settings.web_host == "0.0.0.0"
    assert lan_settings.max_context_chars == 60000
    assert lan_settings.max_audio_bytes == 25 * 1024 * 1024
    assert lan_settings.stt_model == "test/stt-model"
    assert lan_settings.local_web_username == "test-user"
    assert lan_settings.local_web_password == "test-password"

    monkeypatch.setenv("WEB_ACCESS_MODE", "localhost")
    local_settings = Settings.load(require_telegram=False)
    assert local_settings.web_access_mode == "localhost"
    assert local_settings.web_host == "127.0.0.1"


def test_website_requires_nonempty_local_token(tmp_path) -> None:
    settings = SimpleNamespace(local_api_token="", subjects=SUBJECTS)
    database = Database(tmp_path / "academic_ai.db")
    try:
        create_app(
            settings=settings,
            database=database,
            academic_manager=DummyManager(),
            material_service=SimpleNamespace(),
        )
    except ValueError as exc:
        assert "LOCAL_API_TOKEN" in str(exc)
    else:
        raise AssertionError("create_app must refuse to start without a local API token")


def test_username_password_login_issues_revocable_background_session(tmp_path) -> None:
    database = asyncio.run(_database(tmp_path / "login.db"))
    settings = SimpleNamespace(
        local_api_token="static-server-secret",
        local_web_username="aryastudy",
        local_web_password="strong-local-password",
        web_access_mode="localhost",
        subjects=SUBJECTS,
        max_pdf_bytes=1024 * 1024,
    )
    app = create_app(
        settings=settings,
        database=database,
        academic_manager=DummyManager(),
        material_service=SimpleNamespace(),
    )
    with TestClient(app) as client:
        wrong = client.post("/api/login", json={"username": "aryastudy", "password": "wrong"})
        assert wrong.status_code == 401
        login = client.post(
            "/api/login", json={"username": "aryastudy", "password": "strong-local-password"}
        )
        assert login.status_code == 200
        payload = login.json()
        assert payload["expires_in"] == 12 * 60 * 60
        assert payload["username"] == "aryastudy"
        session_headers = {"Authorization": "Bearer " + payload["access_token"]}
        assert client.get("/api/health", headers=session_headers).status_code == 200
        assert client.post("/api/logout", headers=session_headers).status_code == 200
        assert client.get("/api/health", headers=session_headers).status_code == 401
        # The existing server-side token remains compatible for older local scripts.
        assert (
            client.get(
                "/api/health", headers={"Authorization": "Bearer static-server-secret"}
            ).status_code
            == 200
        )


def test_stats_endpoint_returns_dashboard_snapshot(tmp_path) -> None:
    async def seed() -> Database:
        database = await _database(tmp_path / "stats.db")
        await database.upsert_user(1, "u", "U")
        await database.add_document_and_chunks(
            {
                "id": "doc-1",
                "subject_code": "PP",
                "original_name": "m.pdf",
                "stored_path": "data/knowledge/pp/m.pdf",
                "sha256": "s",
                "embedding_model": "test-emb",
                "file_size_bytes": 10,
                "page_count": 1,
                "uploaded_by": 1,
            },
            [],
        )
        conversation = await database.set_active_subject(1, "PP")
        question_id = await database.add_message(conversation, "user", "apa itu?")
        await database.record_verification_run(
            question_message_id=question_id,
            round_number=0,
            decision="APPROVED",
            confidence=0.9,
            reason="ok",
            revision_instruction=None,
            result={},
        )
        return database

    database = asyncio.run(seed())
    settings = SimpleNamespace(
        local_api_token="stats-secret",
        web_access_mode="localhost",
        subjects=SUBJECTS,
        max_pdf_bytes=1024 * 1024,
    )
    app = create_app(
        settings=settings,
        database=database,
        academic_manager=DummyManager(),
        material_service=SimpleNamespace(),
    )
    with TestClient(app) as client:
        assert client.get("/api/stats").status_code == 401
        payload = client.get("/api/stats", headers={"Authorization": "Bearer stats-secret"}).json()
        pp_row = next(item for item in payload["subjects"] if item["code"] == "PP")
        assert pp_row["documents"] == 1
        assert pp_row["chunks"] == 0
        assert pp_row["embedding_models"] == ["test-emb"]
        assert payload["recent_verifications"][0]["decision"] == "APPROVED"
        assert payload["recent_verifications"][0]["confidence"] == 0.9
        assert "server_time" in payload
