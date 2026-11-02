from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.config import Subject
from app.database.database import Database
from app.manager.manager import AcademicManager, AcademicResult
from app.web.api import create_app

SUBJECTS = {"PP": Subject("PP", "Pendidikan Pancasila", "pp")}


def _stub_manager(calls: dict) -> AcademicManager:
    async def fake_retrieve(code: str, question: str):
        calls["retrieve"] = (code, question)
        return ["chunk-1"]

    async def fake_retrieve_empty(code: str, question: str):
        calls["retrieve"] = (code, question)
        return []

    async def fake_all(code: str):
        calls["all"] = code
        return (["chunk-1"], False)

    async def fake_workflow(
        *,
        subject,
        question,
        task_mode,
        task_instruction,
        chunks,
        history,
        question_message_id,
        progress_callback=None,
    ):
        calls["workflow"] = {"question": question, "chunks": chunks, "mode": task_mode}
        return AcademicResult(
            status="VERIFIED",
            answer="R",
            sources=[],
            confidence=1.0,
            reason="",
            revision_rounds=0,
            successful_agents=2,
            task_mode="summary",
            manager_model="m",
        )

    manager = AcademicManager.__new__(AcademicManager)
    manager._subject = lambda code: SimpleNamespace(code=code, name="PP")
    manager._retrieve = fake_retrieve
    manager._retrieve_empty = fake_retrieve_empty
    manager._all_subject_chunks = fake_all
    manager._run_workflow = fake_workflow
    manager._not_found = AcademicManager._not_found.__get__(manager, AcademicManager)
    return manager


def test_summarize_with_topic_uses_retrieval_path() -> None:
    calls: dict = {}
    manager = _stub_manager(calls)
    result = asyncio.run(manager.summarize("PP", topic="demokrasi"))
    assert calls["retrieve"] == ("PP", "demokrasi")
    assert "demokrasi" in calls["workflow"]["question"]
    assert calls["workflow"]["chunks"] == ["chunk-1"]
    assert calls.get("all") is None
    assert result.status == "VERIFIED"


def test_summarize_without_topic_uses_full_corpus_path() -> None:
    calls: dict = {}
    manager = _stub_manager(calls)
    result = asyncio.run(manager.summarize("PP"))
    assert calls.get("all") == "PP"
    assert calls.get("retrieve") is None
    assert result.status == "VERIFIED"


def test_summarize_with_unmatched_topic_returns_not_found() -> None:
    calls: dict = {}
    manager = _stub_manager(calls)
    manager._retrieve = manager._retrieve_empty
    result = asyncio.run(manager.summarize("PP", topic="topik-aneh"))
    assert result.status == "UNVERIFIED"
    assert "topik" in result.reason.lower()
    assert calls.get("workflow") is None


def test_api_summary_passes_topic_to_manager(tmp_path: Path) -> None:
    async def _database() -> Database:
        database = Database(tmp_path / "topic.db")
        await database.initialize(SUBJECTS)
        return database

    database = asyncio.run(_database())
    seen: dict = {}

    class ManagerStub:
        provider = SimpleNamespace(close=lambda: None)

        async def summarize(self, code, *, question_message_id=None, topic=""):
            seen.update(code=code, topic=topic)
            return AcademicResult(
                status="VERIFIED",
                answer="R",
                sources=[],
                confidence=1.0,
                reason="",
                revision_rounds=0,
                successful_agents=2,
                task_mode="summary",
                manager_model="m",
            )

    settings = SimpleNamespace(
        local_api_token="topic-secret",
        web_access_mode="localhost",
        subjects=SUBJECTS,
        max_pdf_bytes=1024 * 1024,
    )
    app = create_app(
        settings=settings,
        database=database,
        academic_manager=ManagerStub(),
        material_service=SimpleNamespace(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/summary",
            json={"subject_code": "PP", "topic": "demokrasi"},
            headers={"Authorization": "Bearer topic-secret"},
        )
        assert response.status_code == 200
        assert seen == {"code": "PP", "topic": "demokrasi"}
