from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.agents.base import AgentDraft
from app.config import Subject
from app.database.database import Database
from app.manager.manager import AcademicManager, AcademicResult
from app.manager.verifier import VerificationResult
from app.web.api import create_app

SUBJECTS = {"PP": Subject("PP", "Pendidikan Pancasila", "pp")}


def _verified_result() -> AcademicResult:
    return AcademicResult(
        status="VERIFIED",
        answer="Jawaban job.",
        sources=[{"document": "M.pdf", "page": 1}],
        confidence=0.9,
        reason="ok",
        revision_rounds=0,
        successful_agents=2,
        task_mode="answer",
        manager_model="m",
    )


class StubManager:
    provider = SimpleNamespace(close=lambda: None)

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.progress_calls: list[tuple[str, str]] = []

    async def _maybe_fail(self, progress_callback=None) -> None:
        if progress_callback is not None:
            progress_callback("verify", "ronde 0")
            self.progress_calls.append(("verify", "ronde 0"))
        if self.fail_with is not None:
            raise self.fail_with

    async def answer(self, code, question, history=None, **kwargs):
        await self._maybe_fail(kwargs.get("progress_callback"))
        return _verified_result()

    async def summarize(self, code, **kwargs):
        await self._maybe_fail(kwargs.get("progress_callback"))
        return _verified_result()

    async def quiz(self, code, **kwargs):
        await self._maybe_fail(kwargs.get("progress_callback"))
        return _verified_result()


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        local_api_token="job-secret",
        web_access_mode="localhost",
        subjects=SUBJECTS,
        max_pdf_bytes=1024 * 1024,
    )


def _poll_done(client: TestClient, headers: dict, job_id: str) -> dict:
    deadline = time.time() + 10
    payload: dict = {}
    while time.time() < deadline:
        payload = client.get(f"/api/jobs/{job_id}", headers=headers).json()
        if payload["status"] in {"done", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} stuck: {payload!r}")


def test_job_lifecycle_submit_poll_result(tmp_path: Path) -> None:
    async def _database() -> Database:
        database = Database(tmp_path / "jobs.db")
        await database.initialize(SUBJECTS)
        return database

    database = asyncio.run(_database())
    app = create_app(
        settings=_settings(),
        database=database,
        academic_manager=StubManager(),
        material_service=SimpleNamespace(),
    )
    headers = {"Authorization": "Bearer job-secret"}
    with TestClient(app) as client:
        submit = client.post(
            "/api/jobs",
            json={"task": "chat", "subject_code": "PP", "question": "Apa itu?"},
            headers=headers,
        )
        assert submit.status_code == 202
        job_id = submit.json()["job_id"]
        payload = _poll_done(client, headers, job_id)
        assert payload["status"] == "done"
        assert payload["result"]["answer"] == "Jawaban job."
        assert payload["stage"] == "done"
        listing = client.get("/api/jobs", headers=headers).json()
        assert any(item["job_id"] == job_id for item in listing)
        assert client.get("/api/jobs/tidak-ada", headers=headers).status_code == 404
        assert (
            client.post(
                "/api/jobs",
                json={"task": "chat", "subject_code": "PP", "question": "  "},
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/jobs",
                json={"task": "translate", "subject_code": "PP"},
                headers=headers,
            ).status_code
            == 422
        )


def test_job_failure_records_actionable_error(tmp_path: Path) -> None:
    async def _database() -> Database:
        database = Database(tmp_path / "jobfail.db")
        await database.initialize(SUBJECTS)
        return database

    database = asyncio.run(_database())
    app = create_app(
        settings=_settings(),
        database=database,
        academic_manager=StubManager(fail_with=ValueError("MODEL_MANAGER belum diisi.")),
        material_service=SimpleNamespace(),
    )
    headers = {"Authorization": "Bearer job-secret"}
    with TestClient(app) as client:
        job_id = client.post(
            "/api/jobs",
            json={"task": "summary", "subject_code": "PP"},
            headers=headers,
        ).json()["job_id"]
        payload = _poll_done(client, headers, job_id)
        assert payload["status"] == "failed"
        assert "MODEL_MANAGER" in payload["error"]


def test_answer_reports_retrieve_and_evidence_progress() -> None:
    stages: list[tuple[str, str]] = []
    calls: dict = {}

    async def fake_workflow(**kwargs):
        calls["callback"] = kwargs.get("progress_callback")
        return _verified_result()

    manager = AcademicManager.__new__(AcademicManager)
    manager._subject = lambda code: SimpleNamespace(code=code, name="PP")
    manager.database = SimpleNamespace(
        get_subject_counts=lambda code: asyncio.sleep(0, result=(1, 3))
    )

    async def fake_retrieve(code: str, question: str):
        return ["c1", "c2"]

    manager._retrieve = fake_retrieve
    manager._run_workflow = fake_workflow
    result = asyncio.run(
        manager.answer(
            "PP",
            "Apa itu demokrasi?",
            [],
            progress_callback=lambda stage, detail="": stages.append((stage, detail)),
        )
    )
    assert result.status == "VERIFIED"
    assert ("retrieve", "mencari bukti") in stages
    assert ("evidence", "2 chunk") in stages
    assert callable(calls["callback"])


def test_run_workflow_reports_draft_verify_done_rounds() -> None:
    stages: list[tuple[str, str]] = []

    async def fake_run_agents(*args, **kwargs):
        return [
            AgentDraft("PP_AGENT_A", "A", "m", "jawaban", [{"document": "M", "page": 1}], 0.8),
            AgentDraft("PP_AGENT_B", "B", "m", "jawaban", [{"document": "M", "page": 1}], 0.7),
        ]

    async def fake_verify(**kwargs):
        return VerificationResult(
            decision="APPROVED",
            confidence=0.9,
            reason="ok",
            revision_instruction=None,
            answer="final",
            sources=[{"document": "M", "page": 1}],
            model_id="m",
        )

    manager = AcademicManager.__new__(AcademicManager)
    manager.settings = SimpleNamespace(subjects={"PP": SimpleNamespace(code="PP")})
    manager.provider = SimpleNamespace()
    manager._run_agents = fake_run_agents
    manager.verifier = SimpleNamespace(verify=fake_verify)
    manager.database = SimpleNamespace()
    result = asyncio.run(
        manager._run_workflow(
            subject=SimpleNamespace(code="PP"),
            question="q",
            task_mode="answer",
            task_instruction="t",
            chunks=[],
            history=[],
            question_message_id=None,
            progress_callback=lambda stage, detail="": stages.append((stage, detail)),
        )
    )
    assert result.status == "VERIFIED"
    assert stages == [("draft", "ronde 0"), ("verify", "ronde 0"), ("done", "APPROVED")]
