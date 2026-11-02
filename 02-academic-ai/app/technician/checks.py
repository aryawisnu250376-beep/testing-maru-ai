"""Pemeriksaan kesehatan AI Teknisi: katalog model, endpoint, konfigurasi, error terkini."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.technician.collector import ErrorCollector

logger = logging.getLogger(__name__)

SUBJECT_SLOTS = ("agent_a", "agent_b", "agent_c")


@dataclass
class Issue:
    code: str
    severity: str  # "error" | "warning" | "info"
    title: str
    detail: str
    fixable: bool = False
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


async def _safe_list(list_models, default: list[str] | None = None) -> list[str] | None:
    try:
        models = await list_models()
        return sorted(str(item) for item in models)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TECH] Gagal membaca katalog (%s)", type(exc).__name__)
        return default


def _pick_replacement(current: str, catalog: list[str], taken: set[str]) -> str:
    """Pilih model pengganti dari katalog: varian nama sama > prefix kr/ > bebas."""
    base = current.split(":")[0].split("/")[-1].lower()
    candidates = [m for m in catalog if m not in taken]
    if not candidates:
        return ""
    for model in candidates:
        if base and base in model.lower():
            return model
    for model in candidates:
        if model.startswith("kr/"):
            return model
    return candidates[0]


async def run_health_checks(
    *,
    settings: Any,
    provider: Any,
    manager_provider: Any,
    collector: ErrorCollector,
) -> list[Issue]:
    issues: list[Issue] = []
    taken: set[str] = set()

    chat_catalog = await _safe_list(lambda: provider.list_models())
    manager_catalog = (
        chat_catalog
        if manager_provider is provider
        else await _safe_list(lambda: manager_provider.list_models())
    )
    embedding_lister = getattr(provider, "list_embedding_models", None)
    embedding_catalog = (
        await _safe_list(embedding_lister) if callable(embedding_lister) else None
    )

    if chat_catalog is None and manager_catalog is None:
        issues.append(
            Issue(
                code="ENDPOINT_TIDAK_TERJANGKAU",
                severity="error",
                title="Endpoint AI tidak dapat dihubungi",
                detail=(
                    "Katalog model tidak terbaca. Pastikan 9Router (dan Ollama bila dipakai) "
                    "berjalan, lalu jalankan: python tools/probe_models.py"
                ),
            )
        )
        return issues

    # 1. Manager model
    manager_model = getattr(settings, "manager_model", "")
    if not manager_model:
        issues.append(
            Issue(
                code="MODEL_MANAGER_KOSONG",
                severity="error",
                title="MODEL_MANAGER belum diisi",
                detail="Isi MODEL_MANAGER di .env atau jalankan tools/probe_models.py --patch-env.",
                fixable=bool(manager_catalog),
                data={"catalog": (manager_catalog or [])[:10]},
            )
        )
    elif manager_catalog is not None and manager_model not in manager_catalog:
        replacement = _pick_replacement(manager_model, manager_catalog, taken)
        issues.append(
            Issue(
                code="MODEL_MANAGER_TIDAK_DITEMUKAN",
                severity="error",
                title="MODEL_MANAGER tidak ada di katalog endpoint Manager",
                detail=(
                    f"'{manager_model}' tidak ditemukan di katalog — inilah penyebab "
                    "HTTP 404 'AI Manager gagal melakukan verifikasi'. "
                    f"Pengganti yang tersedia: {replacement or '(tidak ada)'}"
                ),
                fixable=bool(replacement),
                data={"current": manager_model, "replacement": replacement},
            )
        )
        if replacement:
            taken.add(replacement)

    # 2. Model specialist A/B/C
    missing_agents: list[dict[str, str]] = []
    for code in getattr(settings, "subjects", {}):
        subject_models = getattr(settings, "models", {}).get("subjects", {}).get(code, {})
        for slot in SUBJECT_SLOTS:
            model = str(subject_models.get(slot, "")).strip()
            if not model:
                missing_agents.append({"key": f"MODEL_{code}_{slot[-1].upper()}", "current": ""})
                continue
            if chat_catalog is not None and model not in chat_catalog:
                replacement = _pick_replacement(model, chat_catalog, taken)
                missing_agents.append(
                    {
                        "key": f"MODEL_{code}_{slot[-1].upper()}",
                        "current": model,
                        "replacement": replacement,
                    }
                )
                if replacement:
                    taken.add(replacement)
    if missing_agents:
        issues.append(
            Issue(
                code="MODEL_SPECIALIST_TIDAK_DITEMUKAN",
                severity="error",
                title=f"{len(missing_agents)} model specialist tidak valid",
                detail="Model specialist tidak ada di katalog 9Router: "
                + ", ".join(f"{m['key']}={m.get('current') or '(kosong)'}" for m in missing_agents[:8]),
                fixable=any(m.get("replacement") for m in missing_agents),
                data={"models": missing_agents},
            )
        )

    # 3. Embedding
    embedding_model = getattr(settings, "embedding_model", "")
    if not embedding_model:
        issues.append(
            Issue(
                code="MODEL_EMBEDDING_KOSONG",
                severity="error",
                title="MODEL_EMBEDDING belum diisi",
                detail="PDF tidak bisa diindeks tanpa model embedding.",
                fixable=bool(embedding_catalog),
                data={"catalog": (embedding_catalog or [])[:10]},
            )
        )
    elif embedding_catalog is not None and embedding_model not in embedding_catalog:
        replacement = _pick_replacement(embedding_model, embedding_catalog, set())
        issues.append(
            Issue(
                code="MODEL_EMBEDDING_TIDAK_DITEMUKAN",
                severity="error",
                title="MODEL_EMBEDDING tidak ada di katalog embedding",
                detail=f"'{embedding_model}' tidak ditemukan. Pengganti: {replacement or '(tidak ada)'}",
                fixable=bool(replacement),
                data={"current": embedding_model, "replacement": replacement},
            )
        )

    # 4. Timeout
    timeout_now = float(getattr(settings, "nine_router_timeout_seconds", 0) or 0)
    if timeout_now < 120:
        issues.append(
            Issue(
                code="TIMEOUT_TERLALU_PENDEK",
                severity="warning",
                title="NINE_ROUTER_TIMEOUT di bawah 120 detik",
                detail=(
                    "Payload verifikasi besar mudah timeout; naikkan ke 300 detik "
                    "(batas aplikasi) agar Manager sempat menyelesaikan jawaban."
                ),
                fixable=True,
                data={"current": str(int(timeout_now)), "replacement": "300"},
            )
        )

    # 5. Error terkini dari log/runtime
    recent = collector.unique_recent(_log_dir(settings), limit=12)
    code_counts: dict[str, int] = {}
    for event in recent:
        for code in event.codes:
            code_counts[code] = code_counts.get(code, 0) + 1
    if code_counts:
        top = sorted(code_counts.items(), key=lambda item: -item[1])
        detail = "; ".join(f"{code}×{count}" for code, count in top[:6])
        latest = recent[0]
        issues.append(
            Issue(
                code="ERROR_TERKINI",
                severity="warning",
                title=f"{len(recent)} jenis error tercatat di log/runtime",
                detail=f"{detail} — terakhir: [{latest.ts}] {latest.message[:160]}",
                data={
                    "events": [
                        {"ts": e.ts, "level": e.level, "message": e.message[:200], "codes": e.codes}
                        for e in recent[:8]
                    ]
                },
            )
        )
    return issues


def _log_dir(settings: Any):
    return Path(getattr(settings, "data_dir", Path("data"))) / "logs"
