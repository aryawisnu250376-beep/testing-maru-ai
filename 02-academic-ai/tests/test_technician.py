from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from app.technician.checks import Issue, run_health_checks
from app.technician.coder import (
    apply_patch_file,
    diagnose_and_fix,
    rollback_batch,
    rollback_last,
)
from app.technician.collector import ErrorCollector, ErrorEvent
from app.technician.fixers import apply_safe_fixes, read_journal
from app.technician.service import TechnicianService


def _settings(tmp_path: Path) -> SimpleNamespace:
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_MANAGER=lama-model\nNINE_ROUTER_TIMEOUT=90\n", encoding="utf-8")
    return SimpleNamespace(
        project_root=tmp_path,
        env_file=env_file,
        data_dir=tmp_path / "data",
        manager_model="lama-model",
        embedding_model="emb-1",
        models={"subjects": {"PP": {"agent_a": "a-1", "agent_b": "b-1", "agent_c": "c-1"}}},
        subjects={"PP": SimpleNamespace(code="PP", name="Pancasila")},
        nine_router_timeout_seconds=90.0,
        technician_enabled=True,
        technician_auto=True,
        technician_mode="safe",
        technician_interval_min=30,
        technician_code_fix=True,
    )


class FakeCatalogProvider:
    def __init__(self, chat_models: list[str], embedding_models: list[str] | None = None) -> None:
        self.chat_models = chat_models
        self.embedding_models = embedding_models or []

    async def list_models(self):
        return list(self.chat_models)

    async def list_embedding_models(self):
        return list(self.embedding_models)

    async def chat(self, model, messages, **kwargs):
        return (
            '{"diagnosis":"typo","patches":[{"file":"app/demo.py","find_text":"salah = 1",'
            '"replace_text":"benar = 1"}],"explanation":"perbaikan kecil","needs_restart":false}'
        ), model


def test_collector_recognizes_known_signatures() -> None:
    event = ErrorEvent("t", "ERROR", "x", "HTTP Request: POST ... 404 Not Found + Manager verification failed", "log")
    assert "VERIFIER_GAGAL" in event.codes
    assert "MODEL_TIDAK_DITEMUKAN" in event.codes
    collector = ErrorCollector(limit=5)
    collector.events.append(event)
    assert collector.runtime_events()[0].message.endswith("failed")


def test_health_checks_flag_missing_models_and_timeout(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    provider = FakeCatalogProvider(["model-lain"], ["emb-1"])
    issues = asyncio.run(
        run_health_checks(
            settings=settings,
            provider=provider,
            manager_provider=provider,
            collector=ErrorCollector(),
        )
    )
    codes = {issue.code for issue in issues}
    assert "MODEL_MANAGER_TIDAK_DITEMUKAN" in codes
    assert "MODEL_SPECIALIST_TIDAK_DITEMUKAN" in codes
    assert "TIMEOUT_TERLALU_PENDEK" in codes
    manager_issue = next(i for i in issues if i.code == "MODEL_MANAGER_TIDAK_DITEMUKAN")
    assert manager_issue.fixable and manager_issue.data["replacement"] == "model-lain"


def test_apply_safe_fixes_updates_env(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    issue = Issue(
        code="MODEL_MANAGER_TIDAK_DITEMUKAN",
        severity="error",
        title="x",
        detail="x",
        fixable=True,
        data={"current": "lama-model", "replacement": "hermes3:latest"},
    )
    timeout_issue = Issue(
        code="TIMEOUT_TERLALU_PENDEK",
        severity="warning",
        title="x",
        detail="x",
        fixable=True,
        data={"current": "90"},
    )
    records = apply_safe_fixes(settings, [issue, timeout_issue])
    assert len(records) == 2
    text = Path(settings.env_file).read_text(encoding="utf-8")
    assert "MODEL_MANAGER=hermes3:latest" in text
    assert "NINE_ROUTER_TIMEOUT=300" in text
    journal = read_journal(Path(settings.data_dir))
    assert any(item.get("code") == "MODEL_MANAGER_TIDAK_DITEMUKAN" for item in journal)


def test_apply_patch_and_rollback(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    (project / "app").mkdir(parents=True)
    target = project / "app" / "demo.py"
    target.write_text("nilai = salah\nprint(nilai)\n", encoding="utf-8")
    backup = project / "data" / "patches" / "b1" / "originals"

    result = apply_patch_file(project, backup, "app/demo.py", "nilai = salah", "nilai = benar")
    assert result.applied
    assert "nilai = benar" in target.read_text(encoding="utf-8")
    assert (backup / "app" / "demo.py").is_file()

    restored = rollback_batch(project, backup)
    assert restored == ["app/demo.py"]
    assert "nilai = salah" in target.read_text(encoding="utf-8")


def test_apply_patch_rejects_bad_targets(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    (project / "app").mkdir(parents=True)
    (project / "app" / "demo.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    backup = project / "bak"
    assert not apply_patch_file(project, backup, "../etc/passwd.py", "a", "b").applied
    assert not apply_patch_file(project, backup, ".env", "a", "b").applied
    assert not apply_patch_file(project, backup, "rahasia.py", "a", "b").applied
    dup = apply_patch_file(project, backup, "app/demo.py", "x = 1", "x = 2")
    assert not dup.applied and "2x" in dup.reason


def test_diagnose_and_fix_keeps_when_tests_pass(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    project = tmp_path / "proj"
    (project / "app").mkdir(parents=True)
    (project / "app" / "demo.py").write_text("salah = 1\n", encoding="utf-8")
    provider = FakeCatalogProvider(["model-ok"])

    report = asyncio.run(
        diagnose_and_fix(
            settings=settings,
            provider=provider,
            errors=[{"ts": "t", "message": "bug di app/demo.py"}],
            project_root=project,
            test_command=[sys.executable, "-c", "raise SystemExit(0)"],
        )
    )
    assert report.kept and report.tests_passed is True
    assert "benar = 1" in (project / "app" / "demo.py").read_text(encoding="utf-8")


def test_diagnose_and_fix_rolls_back_when_tests_fail(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    project = tmp_path / "proj"
    (project / "app").mkdir(parents=True)
    (project / "app" / "demo.py").write_text("salah = 1\n", encoding="utf-8")
    provider = FakeCatalogProvider(["model-ok"])

    report = asyncio.run(
        diagnose_and_fix(
            settings=settings,
            provider=provider,
            errors=[{"ts": "t", "message": "bug di app/demo.py"}],
            project_root=project,
            test_command=[sys.executable, "-c", "raise SystemExit(1)"],
        )
    )
    assert not report.kept and report.tests_passed is False
    assert "salah = 1" in (project / "app" / "demo.py").read_text(encoding="utf-8")


def test_rollback_last_requires_manifest(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    outcome = rollback_last(settings, tmp_path / "proj")
    assert outcome["ok"] is False


def test_service_scan_and_status_with_stub_manager(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    provider = FakeCatalogProvider(["model-lain"], ["emb-1"])
    manager = SimpleNamespace(provider=provider, manager_provider=provider)

    service = TechnicianService(settings, manager)

    async def scenario() -> None:
        status = await service.status()
        assert status["mode"] == "safe"
        scan = await service.scan("safe")
        assert scan["ok"] is True
        assert scan["issues"] and scan["summary"]
        assert any(fix["code"] == "MODEL_MANAGER_TIDAK_DITEMUKAN" for fix in scan["fixes"])

    asyncio.run(scenario())


def test_technician_web_api_status_scan_and_rollback(tmp_path) -> None:
    import asyncio as _asyncio
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.config import Subject
    from app.database.database import Database
    from app.web.api import create_app

    subjects = {"PP": Subject("PP", "Pendidikan Pancasila", "pp")}

    class _Manager:
        provider = SimpleNamespace(close=lambda: None)

        async def generate(self, *args, **kwargs):
            return "ok"

    database = Database(tmp_path / "api.db")
    _asyncio.run(database.initialize(subjects))
    settings = SimpleNamespace(
        local_api_token="tech-secret",
        web_access_mode="localhost",
        subjects=subjects,
        max_pdf_bytes=1024,
        log_dir=tmp_path / "logs",
        data_dir=tmp_path / "data",
    )
    app = create_app(
        settings=settings,
        database=database,
        academic_manager=_Manager(),
        material_service=SimpleNamespace(),
    )
    with TestClient(app) as client:
        assert client.get("/api/technician/status").status_code == 401
        headers = {"Authorization": "Bearer tech-secret"}
        status = client.get("/api/technician/status", headers=headers)
        assert status.status_code == 200
        assert status.json()["enabled"] is True
        assert "journal" in status.json()
        scan = client.post(
            "/api/technician/scan", headers=headers, json={"mode": "safe"}
        )
        assert scan.status_code == 200
        assert "issues" in scan.json()
        assert "fixes" in scan.json()
        assert "summary" in scan.json()
        rollback = client.post("/api/technician/rollback", headers=headers)
        assert rollback.status_code == 200
        assert "ok" in rollback.json()
