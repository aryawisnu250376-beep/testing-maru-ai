from __future__ import annotations

import asyncio
import time
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
        local_api_token="session-test-secret",
        local_web_username="u",
        local_web_password="p",
        web_access_mode="localhost",
        subjects=SUBJECTS,
        max_pdf_bytes=1024 * 1024,
    )


def test_session_survives_app_restart_and_logout_revokes(tmp_path: Path) -> None:
    async def _database() -> Database:
        database = Database(tmp_path / "sess.db")
        await database.initialize(SUBJECTS)
        return database

    database = asyncio.run(_database())
    app_before = create_app(
        settings=_settings(),
        database=database,
        academic_manager=DummyManager(),
        material_service=SimpleNamespace(),
    )
    with TestClient(app_before) as client:
        token = client.post("/api/login", json={"username": "u", "password": "p"}).json()[
            "access_token"
        ]
    # Simulate a restart: a brand-new app object over the same database file.
    app_after = create_app(
        settings=_settings(),
        database=database,
        academic_manager=DummyManager(),
        material_service=SimpleNamespace(),
    )
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app_after) as client:
        assert client.get("/api/health", headers=headers).status_code == 200
        assert client.post("/api/logout", headers=headers).status_code == 200
        assert client.get("/api/health", headers=headers).status_code == 401


def test_expired_sessions_rejected_and_cleaned(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = Database(tmp_path / "exp.db")
        await database.initialize(SUBJECTS)
        await database.create_web_session("h1", "u", time.time() - 10)
        await database.create_web_session("h2", "u", time.time() + 3600)
        assert await database.get_web_session("h1") is not None
        removed = await database.delete_expired_web_sessions(time.time())
        assert removed == 1
        assert await database.get_web_session("h1") is None
        assert await database.get_web_session("h2") is not None
        await database.delete_web_session("h2")
        assert await database.get_web_session("h2") is None

    asyncio.run(scenario())
