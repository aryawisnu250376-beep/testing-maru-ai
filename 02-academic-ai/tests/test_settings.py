from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import Subject, update_env_file
from app.settings_update import (
    apply_updates,
    current_settings_view,
    set_local_password,
    update_settings,
    validate_updates,
)
from app.web.api import create_app

SUBJECTS = {
    "PP": Subject("PP", "Pendidikan Pancasila", "pp"),
    "KAP": Subject("KAP", "Kapita Selekta", "kap"),
}


def _settings(env_file: Path) -> SimpleNamespace:
    return SimpleNamespace(
        env_file=env_file,
        subjects=SUBJECTS,
        models={
            "subjects": {"PP": {"agent_a": "a1", "agent_b": "b1"}},
            "manager": {"model": "m1"},
            "embeddings": {"model": "e1"},
            "fallbacks": {"agent_a": ["f1"], "agent_b": [], "manager": []},
        },
        stt_model="",
        rag_top_k=6,
        rag_min_score=0.12,
        rag_query_variants=3,
        max_output_tokens=1500,
        max_revision_rounds=1,
        max_context_chars=60000,
        max_pdf_bytes=25 * 1024 * 1024,
        max_audio_bytes=10 * 1024 * 1024,
        log_level="INFO",
        local_web_username="admin",
        local_web_password="lama-rahasia",
        local_api_token="token-lama-yang-cukup-panjang",
        nine_router_api_key="router-key",
        nine_router_base_url="https://router",
        nine_router_timeout_seconds=60.0,
        nine_router_max_retries=2,
        chat_base_url="",
        chat_api_key="",
        manager_chat_base_url="",
        manager_chat_api_key="",
        embedding_base_url="",
        embedding_api_key="",
        stt_base_url="",
        stt_api_key="",
        web_access_mode="localhost",
        web_host="127.0.0.1",
        web_port=8000,
        data_dir=Path("data"),
        telegram_token="",
        allowed_user_ids=frozenset({1}),
        gdrive_backup_enabled=False,
        gdrive_credentials_file=Path("c.json"),
        gdrive_token_file=Path("t.json"),
        gdrive_root_folder="AcademicAI",
    )


def test_update_env_file_preserves_comments_and_appends(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# Komentar\nRAG_TOP_K=6\n\n# Akhir\n", encoding="utf-8")
    update_env_file(env_file, {"RAG_TOP_K": "8", "MODEL_BARU": "x y#z"})
    text = env_file.read_text(encoding="utf-8")
    assert text.splitlines() == [
        "# Komentar",
        "RAG_TOP_K=8",
        "",
        "# Akhir",
        'MODEL_BARU="x y#z"',
    ]


def test_validate_updates_accepts_runtime_model_and_restart() -> None:
    settings = _settings(Path("dummy.env"))
    validated = validate_updates(
        settings,
        {
            "rag_top_k": "8",
            "rag_min_score": 0.2,
            "log_level": "debug",
            "local_web_username": "  guru  ",
            "model_pp_b": "b2",
            "model_fallback_agent_b": "f2",
            "fallback_model": "gf",
            "nine_router_timeout": "90",
            "gdrive_backup_enabled": True,
        },
    )
    assert validated["RAG_TOP_K"] == "8"
    assert validated["LOG_LEVEL"] == "DEBUG"
    assert validated["LOCAL_WEB_USERNAME"] == "guru"
    assert validated["FALLBACK_MODEL"] == "gf"
    assert validated["GDRIVE_BACKUP_ENABLED"] == "true"


def test_validate_updates_collects_all_problems() -> None:
    settings = _settings(Path("dummy.env"))
    with pytest.raises(ValueError, match=r"RAG_TOP_K.*MODEL_PP_A.*KUNCI_ASING"):
        validate_updates(
            settings,
            {"rag_top_k": "99", "model_pp_a": "", "kunci_asing": "x", "web_port": "abc"},
        )


def test_update_settings_applies_runtime_and_persists(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("RAG_TOP_K=6\n", encoding="utf-8")
    settings = _settings(env_file)
    report = update_settings(
        settings,
        {
            "rag_top_k": 8,
            "max_pdf_mb": 30,
            "model_pp_b": "b2",
            "local_api_token": "token-baru-yang-jelas-panjang",
            "web_port": 9000,
        },
    )
    assert settings.rag_top_k == 8
    assert settings.max_pdf_bytes == 30 * 1024 * 1024
    assert settings.models["subjects"]["PP"]["agent_b"] == "b2"
    assert report["needs_restart"] == ["WEB_PORT"]
    assert report["updated"]["LOCAL_API_TOKEN"] == "***"
    assert "token-baru" in env_file.read_text(encoding="utf-8")


def test_apply_updates_merges_global_fallback_and_masks_secrets() -> None:
    settings = _settings(Path("dummy.env"))
    report = apply_updates(
        settings, {"FALLBACK_MODEL": "gf", "LOCAL_WEB_PASSWORD": "baru-rahasia-1"}
    )
    assert settings.models["fallbacks"]["agent_a"] == ["f1", "gf"]
    assert settings.models["fallbacks"]["manager"] == ["gf"]
    assert report["updated"] == {"FALLBACK_MODEL": "gf", "LOCAL_WEB_PASSWORD": "***"}
    assert settings.local_web_password == "baru-rahasia-1"


def test_manager_endpoint_settings_are_persisted_and_secret_is_masked(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    settings = _settings(env_file)
    report = update_settings(
        settings,
        {
            "manager_chat_base_url": "http://localhost:11434/v1",
            "manager_chat_api_key": "ollama",
        },
    )
    assert report["needs_restart"] == ["MANAGER_CHAT_BASE_URL", "MANAGER_CHAT_API_KEY"]
    assert settings.manager_chat_base_url == ""
    assert "MANAGER_CHAT_API_KEY=ollama" in env_file.read_text(encoding="utf-8")
    pending_view = current_settings_view(settings)
    assert pending_view["values"]["MANAGER_CHAT_BASE_URL"] == ""
    assert pending_view["values"]["MANAGER_CHAT_API_KEY"] == ""
    # After restart, loaded values are visible but the API key is masked.
    settings.manager_chat_base_url = "http://localhost:11434/v1"
    settings.manager_chat_api_key = "ollama"
    view = current_settings_view(settings)
    assert view["values"]["MANAGER_CHAT_BASE_URL"] == "http://localhost:11434/v1"
    assert view["values"]["MANAGER_CHAT_API_KEY"] == "***"
    assert view["meta"]["MANAGER_CHAT_BASE_URL"]["runtime"] is False
    assert view["meta"]["MANAGER_CHAT_API_KEY"]["secret"] is True


def test_current_settings_view_masks_secrets_and_flags_restart() -> None:
    view = current_settings_view(_settings(Path("dummy.env")))
    assert view["values"]["LOCAL_WEB_PASSWORD"] == "***"
    assert view["values"]["NINE_ROUTER_API_KEY"] == "***"
    assert view["values"]["RAG_TOP_K"] == "6"
    assert view["values"]["MAX_PDF_MB"] == "25"
    assert view["values"]["MODEL_PP_B"] == "b1"
    assert view["meta"]["RAG_TOP_K"] == {"runtime": True, "secret": False}
    assert view["meta"]["WEB_PORT"] == {"runtime": False, "secret": False}
    assert view["meta"]["CHAT_API_KEY"]["secret"] is True


def test_set_local_password_validates_length(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LOCAL_WEB_PASSWORD=lama\n", encoding="utf-8")
    with pytest.raises(ValueError, match="8-256"):
        set_local_password(env_file, "pendek")
    set_local_password(env_file, "baru-yang-aman")
    assert "LOCAL_WEB_PASSWORD=baru-yang-aman" in env_file.read_text(encoding="utf-8")


def test_settings_api_roundtrip(tmp_path: Path) -> None:
    import asyncio

    from app.database.database import Database

    async def _database() -> Database:
        database = Database(tmp_path / "s.db")
        await database.initialize(SUBJECTS)
        return database

    settings = _settings(tmp_path / ".env")
    app = create_app(
        settings=settings,
        database=asyncio.run(_database()),
        academic_manager=SimpleNamespace(provider=SimpleNamespace(close=lambda: None)),
        material_service=SimpleNamespace(),
    )
    headers = {"Authorization": "Bearer token-lama-yang-cukup-panjang"}
    with TestClient(app) as client:
        current = client.get("/api/settings", headers=headers)
        assert current.status_code == 200
        assert current.json()["values"]["LOCAL_API_TOKEN"] == "***"
        bad = client.patch("/api/settings", json={"updates": {"rag_top_k": 99}}, headers=headers)
        assert bad.status_code == 422
        good = client.patch(
            "/api/settings",
            json={"updates": {"rag_top_k": 7, "nine_router_timeout": 90}},
            headers=headers,
        )
        assert good.status_code == 200
        assert good.json()["needs_restart"] == ["NINE_ROUTER_TIMEOUT"]
        assert settings.rag_top_k == 7
        assert "RAG_TOP_K=7" in (tmp_path / ".env").read_text(encoding="utf-8")
