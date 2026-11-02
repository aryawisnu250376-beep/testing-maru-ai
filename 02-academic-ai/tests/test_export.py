from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Subject
from app.database.database import Database
from app.web.api import create_app

SUBJECTS = {"PP": Subject("PP", "Pendidikan Pancasila", "pp")}


class DummyManager:
    provider = SimpleNamespace(close=lambda: None)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        local_api_token="export-secret",
        web_access_mode="localhost",
        subjects=SUBJECTS,
        max_pdf_bytes=1024 * 1024,
    )


def _seeded_database(path: Path) -> Database:
    async def scenario() -> Database:
        database = Database(path)
        await database.initialize(SUBJECTS)
        await database.upsert_user(0, "local-web", "Local Web")
        conversation = await database.set_active_subject(0, "PP")
        await database.add_message(conversation, "user", "Apa itu demokrasi?")
        await database.add_message(conversation, "assistant", "Demokrasi adalah ...")
        return database

    return asyncio.run(scenario())


def test_export_markdown_download(tmp_path: Path) -> None:
    database = _seeded_database(tmp_path / "exp.db")
    app = create_app(
        settings=_settings(),
        database=database,
        academic_manager=DummyManager(),
        material_service=SimpleNamespace(),
    )
    headers = {"Authorization": "Bearer export-secret"}
    with TestClient(app) as client:
        response = client.get("/api/export?subject_code=PP&format=md", headers=headers)
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert response.headers["content-disposition"].endswith('.md"')
        assert "# Riwayat Belajar" in response.text
        assert "Apa itu demokrasi?" in response.text
        assert "Demokrasi adalah" in response.text
        plain = client.get("/api/export?subject_code=PP&format=txt", headers=headers)
        assert plain.status_code == 200
        assert "RIWAYAT BELAJAR" in plain.text
        assert (
            client.get("/api/export?subject_code=PP&format=pdf", headers=headers).status_code == 422
        )
        assert client.get("/api/export?subject_code=XX", headers=headers).status_code == 404


def test_export_without_conversation_is_404(tmp_path: Path) -> None:
    async def _database() -> Database:
        database = Database(tmp_path / "empty.db")
        await database.initialize(SUBJECTS)
        return database

    database = asyncio.run(_database())
    app = create_app(
        settings=_settings(),
        database=database,
        academic_manager=DummyManager(),
        material_service=SimpleNamespace(),
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/export?subject_code=PP", headers={"Authorization": "Bearer export-secret"}
        )
        assert response.status_code == 404
