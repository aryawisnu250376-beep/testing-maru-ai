from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.providers.base import AIProvider

logger = logging.getLogger(__name__)


def configured_chat_models(settings: Settings) -> list[tuple[str, str, str]]:
    """Return (label, model ID, route) where route is ``agents`` or ``manager``."""
    result: list[tuple[str, str, str]] = []
    if settings.manager_model:
        result.append(("Manager", settings.manager_model, "manager"))
    for code in settings.subjects:
        models = settings.models.get("subjects", {}).get(code, {})
        for key, label in (("agent_a", "Agent A"), ("agent_b", "Agent B"), ("agent_c", "Agent C")):
            model = str(models.get(key, "")).strip()
            if model:
                result.append((f"{code} {label}", model, "agents"))
    for role in ("agent_a", "agent_b", "agent_c", "manager"):
        route = "manager" if role == "manager" else "agents"
        for index, model in enumerate(settings.fallback_models_for(role), start=1):
            result.append((f"Fallback {role} {index}", model, route))
    return result


def _endpoint(provider: AIProvider, fallback: str) -> str:
    return str(getattr(provider, "base_url", fallback))


def check_local_config(settings: Settings) -> int:
    issues: list[str] = []
    if not settings.embedding_model:
        issues.append("MODEL_EMBEDDING belum diisi (gunakan ID dari /v1/models/embedding).")
    if not settings.manager_model:
        issues.append("MODEL_MANAGER belum diisi.")
    for code in settings.subjects:
        models = settings.models.get("subjects", {}).get(code, {})
        for key, suffix in (("agent_a", "A"), ("agent_b", "B"), ("agent_c", "C")):
            if not str(models.get(key, "")).strip():
                issues.append(f"MODEL_{code}_{suffix} belum diisi.")
    manager_url = getattr(settings, "manager_chat_base_url", "") or settings.chat_base_url
    print("Academic AI — pemeriksaan konfigurasi lokal")
    print("Telegram token: terisi (nilainya tidak ditampilkan)")
    print("9Router key: terisi (nilainya tidak ditampilkan)")
    print(f"Endpoint chat spesialis : {settings.chat_base_url}")
    print(f"Endpoint chat Manager   : {manager_url}")
    print(f"Endpoint embedding      : {settings.embedding_base_url}")
    print(f"Endpoint STT            : {settings.stt_base_url}")
    print(f"Mata kuliah: {len(settings.subjects)}")
    print(f"Model embedding: {settings.embedding_model or 'BELUM DIISI'}")
    print(f"Model chat/manager/fallback terisi: {len(configured_chat_models(settings))}")
    if issues:
        print("\nYang perlu diperbaiki:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Konfigurasi lokal lengkap. Pemeriksaan ini belum menghubungi endpoint AI.")
    return 0


async def check_live_models(
    settings: Settings,
    provider: AIProvider,
    manager_provider: AIProvider | None = None,
) -> int:
    manager_provider = manager_provider if manager_provider is not None else provider
    try:
        chat_ids = set(await provider.list_models())
        manager_chat_ids = (
            chat_ids if manager_provider is provider else set(await manager_provider.list_models())
        )
        embedding_list: Any = getattr(provider, "list_embedding_models", None)
        if not callable(embedding_list):
            raise RuntimeError("Provider adapter belum mendukung daftar model embedding.")
        embedding_ids = set(await embedding_list())
    except Exception as exc:
        logger.error("[ERROR] Katalog model live tidak dapat dibaca (%s)", type(exc).__name__)
        print(
            "Gagal membaca katalog live. Pastikan endpoint chat Manager/spesialis dan embedding hidup, "
            "key benar, dan URL sesuai."
        )
        return 2

    manager_url = getattr(settings, "manager_chat_base_url", "") or settings.chat_base_url
    print("\nPemeriksaan katalog model live")
    print(f"Katalog chat spesialis : {_endpoint(provider, settings.chat_base_url)}")
    print(f"Katalog chat Manager   : {_endpoint(manager_provider, manager_url)}")
    print(f"Katalog embedding      : {settings.embedding_base_url}")
    missing: list[str] = []
    for label, model, route in configured_chat_models(settings):
        available_ids = manager_chat_ids if route == "manager" else chat_ids
        available = model in available_ids
        print(f"{'OK' if available else 'TIDAK ADA':10} {label}: {model}")
        if not available:
            missing.append(f"{label}={model}")
    embedding = settings.embedding_model
    if embedding:
        available = embedding in embedding_ids
        print(f"{'OK' if available else 'TIDAK ADA':10} Embedding: {embedding}")
        if not available:
            missing.append(f"MODEL_EMBEDDING={embedding}")
    else:
        missing.append("MODEL_EMBEDDING belum diisi")
    if missing:
        print(
            "\nPilih ID persis dari katalog endpoint yang sesuai (9Router untuk spesialis, "
            "endpoint Manager untuk Manager, katalog embedding untuk embedding) dan pastikan penggunaan diizinkan."
        )
        print(
            "Jangan mengandalkan OpenCode Free/oc/auto: ada laporan 403 dan pembatasan penggunaan lewat router pihak ketiga."
        )
        if not embedding or embedding not in embedding_ids:
            candidates = sorted(embedding_ids)[:30]
            print("ID embedding yang tersedia (maksimum 30):")
            for candidate in candidates:
                print(f"- {candidate}")
        return 1
    print(
        "Semua model terkonfigurasi ditemukan di katalog live. Ini belum menguji completion/embedding berbiaya atau kuota."
    )
    return 0
