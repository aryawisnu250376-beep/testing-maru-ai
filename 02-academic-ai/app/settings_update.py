"""Validated runtime settings updates (web UI + API), persisted to .env.

Runtime keys apply instantly to the live process AND are written to .env.
Restart keys are only written to .env (the provider/server is built at startup).
Unknown keys are rejected. Secrets are masked in every response.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, update_env_file

logger = logging.getLogger(__name__)

SECRET_HINTS = ("TOKEN", "PASSWORD", "API_KEY", "SECRET")
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

# env key -> (Settings attr, min, max)
RUNTIME_INT_KEYS = {
    "RAG_TOP_K": ("rag_top_k", 1, 20),
    "RAG_QUERY_VARIANTS": ("rag_query_variants", 1, 5),
    "MAX_OUTPUT_TOKENS": ("max_output_tokens", 100, 32000),
    "MAX_REVISION_ROUNDS": ("max_revision_rounds", 0, 2),
    "MAX_CONTEXT_CHARS": ("max_context_chars", 6000, 500000),
    "VIDEO_MAX_SCENES": ("video_max_scenes", 1, 10),
}
RUNTIME_MB_KEYS = {"MAX_PDF_MB": "max_pdf_bytes", "MAX_AUDIO_MB": "max_audio_bytes"}
RUNTIME_FLOAT_KEYS = {"RAG_MIN_SCORE": ("rag_min_score", 0.0, 1.0)}
# env key -> (Settings attr, min_len, max_len)
RUNTIME_STR_KEYS = {
    "LOCAL_WEB_USERNAME": ("local_web_username", 1, 100),
    "LOCAL_WEB_PASSWORD": ("local_web_password", 8, 256),
    "LOCAL_API_TOKEN": ("local_api_token", 16, 256),
}
RESTART_KEYS = frozenset(
    {
        "NINE_ROUTER_API_KEY",
        "NINE_ROUTER_BASE_URL",
        "NINE_ROUTER_TIMEOUT",
        "NINE_ROUTER_MAX_RETRIES",
        "CHAT_BASE_URL",
        "CHAT_API_KEY",
        "MANAGER_CHAT_BASE_URL",
        "MANAGER_CHAT_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_API_KEY",
        "STT_BASE_URL",
        "STT_API_KEY",
        "WEB_ACCESS_MODE",
        "WEB_HOST",
        "WEB_PORT",
        "DATA_DIR",
        "TELEGRAM_BOT_TOKEN",
        "ALLOWED_USER_IDS",
        "GDRIVE_BACKUP_ENABLED",
        "GDRIVE_CREDENTIALS_FILE",
        "GDRIVE_TOKEN_FILE",
        "GDRIVE_ROOT_FOLDER",
        "MODEL_EMBEDDING",
    }
)
# Restart env key -> Settings attr for the read-only view (None = computed).
RESTART_VIEW_ATTRS: dict[str, tuple[str | None, bool]] = {
    "NINE_ROUTER_API_KEY": ("nine_router_api_key", True),
    "NINE_ROUTER_BASE_URL": ("nine_router_base_url", False),
    "NINE_ROUTER_TIMEOUT": ("nine_router_timeout_seconds", False),
    "NINE_ROUTER_MAX_RETRIES": ("nine_router_max_retries", False),
    "CHAT_BASE_URL": ("chat_base_url", False),
    "CHAT_API_KEY": ("chat_api_key", True),
    "MANAGER_CHAT_BASE_URL": ("manager_chat_base_url", False),
    "MANAGER_CHAT_API_KEY": ("manager_chat_api_key", True),
    "EMBEDDING_BASE_URL": ("embedding_base_url", False),
    "EMBEDDING_API_KEY": ("embedding_api_key", True),
    "STT_BASE_URL": ("stt_base_url", False),
    "STT_API_KEY": ("stt_api_key", True),
    "WEB_ACCESS_MODE": ("web_access_mode", False),
    "WEB_HOST": ("web_host", False),
    "WEB_PORT": ("web_port", False),
    "DATA_DIR": ("data_dir", False),
    "TELEGRAM_BOT_TOKEN": ("telegram_token", True),
    "ALLOWED_USER_IDS": (None, False),
    "GDRIVE_BACKUP_ENABLED": (None, False),
    "GDRIVE_CREDENTIALS_FILE": ("gdrive_credentials_file", False),
    "GDRIVE_TOKEN_FILE": ("gdrive_token_file", False),
    "GDRIVE_ROOT_FOLDER": ("gdrive_root_folder", False),
    "MODEL_EMBEDDING": (None, False),
}
_FALLBACK_ENV_TO_ROLE = {
    "MODEL_FALLBACK_AGENT_A": "agent_a",
    "MODEL_FALLBACK_AGENT_B": "agent_b",
    "MODEL_FALLBACK_MANAGER": "manager",
}


def mask_value(key: str, value: str) -> str:
    if value and any(hint in key for hint in SECRET_HINTS):
        return "***"
    return value


def _model_key_kind(key: str, subjects: dict) -> tuple[str, Any] | None:
    """Classify MODEL_* keys: (kind, payload) or None when not a model key."""
    if key == "MODEL_MANAGER":
        return ("manager", None)
    if key == "MODEL_STT":
        return ("stt", None)
    if key == "FALLBACK_MODEL":
        return ("global_fallback", None)
    if key in _FALLBACK_ENV_TO_ROLE:
        return ("fallback", _FALLBACK_ENV_TO_ROLE[key])
    if key.startswith("MODEL_") and (key.endswith("_A") or key.endswith("_B")):
        code = key[len("MODEL_") : -2]
        slot = "agent_a" if key.endswith("_A") else "agent_b"
        if code in subjects:
            return ("subject", (code, slot))
    return None


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("harus bilangan bulat")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("+-").isdigit():
        return int(value.strip())
    raise ValueError("harus bilangan bulat")


def _as_float(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("harus angka")
    try:
        number = float(value) if not isinstance(value, str) else float(value.strip())
    except (TypeError, ValueError):
        raise ValueError("harus angka") from None
    if not math.isfinite(number):
        raise ValueError("harus angka berhingga")
    return number


def _as_bool_text(value: Any) -> str:
    text = str(value).strip().lower() if not isinstance(value, bool) else str(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return "true"
    if text in {"0", "false", "no", "n", "off", ""}:
        return "false"
    raise ValueError("harus true/false")


def validate_updates(settings, updates: dict[str, Any]) -> dict[str, str]:
    """Validate every entry; raise ValueError listing all problems.

    Returns normalized string values ready for .env and runtime apply.
    """
    if not isinstance(updates, dict) or not updates:
        raise ValueError("Tidak ada perubahan yang dikirim.")
    subjects = getattr(settings, "subjects", {}) or {}
    problems: list[str] = []
    validated: dict[str, str] = {}

    for raw_key, raw_value in updates.items():
        key = str(raw_key).strip().upper()
        try:
            validated[key] = _validate_one(key, raw_value, subjects)
        except ValueError as exc:
            problems.append(f"{key}: {exc}")
    if problems:
        raise ValueError("Pengaturan tidak valid — " + "; ".join(problems))
    return validated


def _validate_one(key: str, raw_value: Any, subjects: dict) -> str:
    if key in RUNTIME_INT_KEYS:
        _, low, high = RUNTIME_INT_KEYS[key]
        number = _as_int(raw_value)
        if not low <= number <= high:
            raise ValueError(f"harus {low}-{high}")
        return str(number)
    if key in RUNTIME_MB_KEYS:
        number = _as_int(raw_value)
        if not 1 <= number <= 500:
            raise ValueError("harus 1-500")
        return str(number)
    if key in RUNTIME_FLOAT_KEYS:
        _, low, high = RUNTIME_FLOAT_KEYS[key]
        number = _as_float(raw_value)
        if not low <= number <= high:
            raise ValueError(f"harus {low}-{high}")
        return str(number)
    if key == "TTS_PROVIDER":
        text = str(raw_value).strip().lower()
        if text not in {"auto", "piper", "edge"}:
            raise ValueError("harus auto, piper, atau edge")
        return text
    if key == "TTS_VOICE":
        text = str(raw_value).strip()
        if not 1 <= len(text) <= 100:
            raise ValueError("panjang harus 1-100 karakter")
        return text
    if key == "RAG_MODE":
        text = str(raw_value).strip().lower()
        if text not in {"vector", "tree", "hybrid"}:
            raise ValueError("harus vector, tree, atau hybrid")
        return text
    if key in {"MEMORY_ENABLED", "SKILLS_LEARN_ENABLED", "WEB_RESEARCH_ENABLED"}:
        return _as_bool_text(raw_value)
    if key == "LOG_LEVEL":
        level = str(raw_value).strip().upper()
        if level not in LOG_LEVELS:
            raise ValueError(f"harus salah satu dari {', '.join(LOG_LEVELS)}")
        return level
    if key in RUNTIME_STR_KEYS:
        _, low, high = RUNTIME_STR_KEYS[key]
        text = str(raw_value) if key == "LOCAL_WEB_PASSWORD" else str(raw_value).strip()
        if not low <= len(text) <= high:
            raise ValueError(f"panjang harus {low}-{high} karakter")
        return text
    model_kind = _model_key_kind(key, subjects)
    if model_kind is not None:
        kind, _ = model_kind
        text = "" if raw_value is None else str(raw_value).strip()
        if kind in {"fallback", "global_fallback", "stt"}:
            return text  # empty disables
        if not text:
            raise ValueError("tidak boleh kosong")
        return text
    if key in RESTART_KEYS:
        return _validate_restart_value(key, raw_value)
    known_hint = "Lihat GET /api/settings untuk daftar kunci yang didukung."
    raise ValueError(f"kunci tidak dikenal. {known_hint}")


def _validate_restart_value(key: str, raw_value: Any) -> str:
    text = "" if raw_value is None else str(raw_value)
    stripped = text.strip()
    if key == "WEB_PORT":
        number = _as_int(raw_value)
        if not 1 <= number <= 65535:
            raise ValueError("harus 1-65535")
        return str(number)
    if key == "NINE_ROUTER_MAX_RETRIES":
        number = _as_int(raw_value)
        if not 0 <= number <= 5:
            raise ValueError("harus 0-5")
        return str(number)
    if key == "NINE_ROUTER_TIMEOUT":
        number = _as_float(raw_value)
        if not 5.0 <= number <= 300.0:
            raise ValueError("harus 5-300")
        return str(number)
    if key == "WEB_ACCESS_MODE":
        if stripped not in {"localhost", "lan"}:
            raise ValueError("harus localhost atau lan")
        return stripped
    if key == "ALLOWED_USER_IDS":
        for part in stripped.split(","):
            part = part.strip()
            if part and not part.isdigit():
                raise ValueError("harus angka yang dipisahkan koma")
        return stripped
    if key == "GDRIVE_BACKUP_ENABLED":
        return _as_bool_text(raw_value)
    if key in {
        "CHAT_BASE_URL",
        "CHAT_API_KEY",
        "MANAGER_CHAT_BASE_URL",
        "MANAGER_CHAT_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_API_KEY",
        "STT_BASE_URL",
        "STT_API_KEY",
        "TELEGRAM_BOT_TOKEN",
    }:
        return stripped  # empty = unset/fallback
    if not stripped:
        raise ValueError("tidak boleh kosong")
    return stripped


def apply_updates(settings, validated: dict[str, str]) -> dict[str, Any]:
    """Mutate live settings for runtime keys; report what needs a restart."""
    updated: dict[str, str] = {}
    needs_restart: list[str] = []
    warnings: list[str] = []
    for key, value in validated.items():
        if key in RUNTIME_INT_KEYS:
            attr, _, _ = RUNTIME_INT_KEYS[key]
            setattr(settings, attr, int(value))
        elif key in RUNTIME_MB_KEYS:
            setattr(settings, RUNTIME_MB_KEYS[key], int(value) * 1024 * 1024)
        elif key in RUNTIME_FLOAT_KEYS:
            setattr(settings, RUNTIME_FLOAT_KEYS[key][0], float(value))
        elif key in {"TTS_PROVIDER", "TTS_VOICE", "RAG_MODE"}:
            setattr(settings, key.lower(), value)
        elif key in {"MEMORY_ENABLED", "SKILLS_LEARN_ENABLED", "WEB_RESEARCH_ENABLED"}:
            setattr(settings, key.lower(), value == "true")
        elif key == "LOG_LEVEL":
            settings.log_level = value
            logging.getLogger().setLevel(getattr(logging, value, logging.INFO))
        elif key in RUNTIME_STR_KEYS:
            setattr(settings, RUNTIME_STR_KEYS[key][0], value)
        elif _model_key_kind(key, getattr(settings, "subjects", {}) or {}) is not None:
            _apply_model_value(settings, key, value)
        else:
            needs_restart.append(key)
        updated[key] = mask_value(key, value)
    if "MODEL_EMBEDDING" in validated:
        warnings.append(
            "MODEL_EMBEDDING berubah: unggah ulang PDF atau kembalikan model lama; "
            "index lama tidak cocok dengan model baru."
        )
    if "LOCAL_API_TOKEN" in validated:
        warnings.append("LOCAL_API_TOKEN berubah: perbarui skrip/n8n yang memakai token lama.")
    logger.info("[INFO] Pengaturan diperbarui: %s", ", ".join(sorted(validated)))
    return {"updated": updated, "needs_restart": needs_restart, "warnings": warnings}


def _apply_model_value(settings, key: str, value: str) -> None:
    models = settings.models
    kind, payload = _model_key_kind(key, getattr(settings, "subjects", {}) or {})
    if kind == "manager":
        models.setdefault("manager", {})["model"] = value
    elif kind == "stt":
        settings.stt_model = value
    elif kind == "subject":
        code, slot = payload
        models.setdefault("subjects", {}).setdefault(code, {})[slot] = value
    elif kind == "fallback":
        models.setdefault("fallbacks", {})[payload] = [value] if value else []
    elif kind == "global_fallback":
        fallbacks = models.setdefault("fallbacks", {})
        for role in ("agent_a", "agent_b", "manager"):
            raw = fallbacks.get(role, "")
            values = list(raw) if isinstance(raw, list) else str(raw).split(",")
            cleaned = [item.strip() for item in values if item.strip()]
            if value and value not in cleaned:
                cleaned.append(value)
            fallbacks[role] = cleaned


def update_settings(settings, updates: dict[str, Any]) -> dict[str, Any]:
    """Validate, persist to .env, then apply runtime keys. Returns the report."""
    validated = validate_updates(settings, updates)
    env_path = getattr(settings, "env_file", None) or (PROJECT_ROOT / ".env")
    update_env_file(Path(env_path), validated)
    report = apply_updates(settings, validated)
    report["persisted_to"] = str(env_path)
    return report


def set_local_password(env_path: Path, password: str) -> None:
    """Validate and persist a new web password (CLI use)."""
    if len(password) < 8 or len(password) > 256:
        raise ValueError("Password harus 8-256 karakter.")
    update_env_file(Path(env_path), {"LOCAL_WEB_PASSWORD": password})


def current_settings_view(settings) -> dict[str, Any]:
    """Read-only snapshot of every settable key (secrets masked)."""
    values: dict[str, str] = {}
    meta: dict[str, dict[str, bool]] = {}

    def put(key: str, value: Any, *, runtime: bool, secret: bool = False) -> None:
        values[key] = mask_value(key, "" if value is None else str(value))
        meta[key] = {"runtime": runtime, "secret": secret}

    for key, (attr, _, _) in RUNTIME_INT_KEYS.items():
        put(key, getattr(settings, attr, ""), runtime=True)
    for key, attr in RUNTIME_MB_KEYS.items():
        raw = getattr(settings, attr, 0) or 0
        put(key, int(raw) // (1024 * 1024), runtime=True)
    for key, (attr, _, _) in RUNTIME_FLOAT_KEYS.items():
        put(key, getattr(settings, attr, ""), runtime=True)
    for key, (attr, _, _) in RUNTIME_STR_KEYS.items():
        put(key, getattr(settings, attr, ""), runtime=True, secret=True)
    put("LOG_LEVEL", getattr(settings, "log_level", "INFO"), runtime=True)
    put("TTS_PROVIDER", getattr(settings, "tts_provider", "auto"), runtime=True)
    put("TTS_VOICE", getattr(settings, "tts_voice", ""), runtime=True)
    put("RAG_MODE", getattr(settings, "rag_mode", "vector"), runtime=True)
    for _bool_key in ("MEMORY_ENABLED", "SKILLS_LEARN_ENABLED", "WEB_RESEARCH_ENABLED"):
        put(
            _bool_key,
            "true" if getattr(settings, _bool_key.lower(), False) else "false",
            runtime=True,
        )
    models = getattr(settings, "models", {}) or {}
    put("MODEL_MANAGER", models.get("manager", {}).get("model", ""), runtime=True)
    put("MODEL_STT", getattr(settings, "stt_model", ""), runtime=True)
    for code in sorted(getattr(settings, "subjects", {}) or {}):
        entry = models.get("subjects", {}).get(code, {})
        put(f"MODEL_{code}_A", entry.get("agent_a", ""), runtime=True)
        put(f"MODEL_{code}_B", entry.get("agent_b", ""), runtime=True)
    fallbacks = models.get("fallbacks", {})
    for env_key, role in sorted(_FALLBACK_ENV_TO_ROLE.items()):
        raw = fallbacks.get(role, "")
        text = ", ".join(raw) if isinstance(raw, list) else str(raw)
        put(env_key, text, runtime=True)
    for key, (attr, secret) in RESTART_VIEW_ATTRS.items():
        put(key, _restart_view_value(settings, key, attr), runtime=False, secret=secret)
    return {"values": values, "meta": meta}


ANSWER_PRESETS: dict[str, dict[str, str]] = {
    "singkat": {"RAG_TOP_K": "3", "MAX_OUTPUT_TOKENS": "800"},
    "seimbang": {"RAG_TOP_K": "6", "MAX_OUTPUT_TOKENS": "1500"},
    "mendalam": {"RAG_TOP_K": "10", "MAX_OUTPUT_TOKENS": "2500"},
}
PRESET_LABELS = {"singkat": "Singkat", "seimbang": "Seimbang", "mendalam": "Mendalam"}


def detect_answer_preset(settings) -> str:
    top_k = str(getattr(settings, "rag_top_k", ""))
    tokens = str(getattr(settings, "max_output_tokens", ""))
    for name, values in ANSWER_PRESETS.items():
        if values["RAG_TOP_K"] == top_k and values["MAX_OUTPUT_TOKENS"] == tokens:
            return name
    return "kustom"


def apply_answer_preset(settings, name: str) -> dict[str, Any]:
    key = name.strip().lower()
    if key not in ANSWER_PRESETS:
        raise ValueError(f"Mode tidak dikenal: {name}. Pilih singkat, seimbang, atau mendalam.")
    return update_settings(settings, dict(ANSWER_PRESETS[key]))


def _restart_view_value(settings, key: str, attr: str | None) -> str:
    if key == "ALLOWED_USER_IDS":
        return ",".join(str(item) for item in sorted(getattr(settings, "allowed_user_ids", set())))
    if key == "GDRIVE_BACKUP_ENABLED":
        return "true" if getattr(settings, "gdrive_backup_enabled", False) else "false"
    if key == "MODEL_EMBEDDING":
        return str(getattr(settings, "models", {}).get("embeddings", {}).get("model", ""))
    return "" if attr is None else str(getattr(settings, attr, ""))
