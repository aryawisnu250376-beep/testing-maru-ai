from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Subject:
    code: str
    name: str
    directory: str
    expertise: str = ""


@dataclass
class Settings:  # mutable: PATCH /api/settings applies validated runtime keys in place
    project_root: Path
    env_file: Path
    telegram_token: str
    allowed_user_ids: frozenset[int]
    nine_router_api_key: str
    nine_router_base_url: str
    nine_router_timeout_seconds: float
    nine_router_max_retries: int
    chat_base_url: str
    chat_api_key: str
    manager_chat_base_url: str
    manager_chat_api_key: str
    embedding_base_url: str
    embedding_api_key: str
    stt_base_url: str
    stt_api_key: str
    gdrive_backup_enabled: bool
    gdrive_credentials_file: Path
    gdrive_token_file: Path
    gdrive_root_folder: str
    stt_model: str
    local_api_token: str
    local_web_username: str
    local_web_password: str
    web_access_mode: str
    web_host: str
    web_port: int
    data_dir: Path
    database_path: Path
    knowledge_dir: Path
    vectorstore_dir: Path
    subjects: dict[str, Subject]
    models: dict[str, Any]
    max_pdf_bytes: int
    max_audio_bytes: int
    rag_top_k: int
    rag_min_score: float
    rag_query_variants: int
    max_output_tokens: int
    max_revision_rounds: int
    max_context_chars: int
    log_level: str
    tts_provider: str
    tts_voice: str
    video_max_scenes: int
    videos_dir: Path
    rag_mode: str
    memory_enabled: bool
    skills_learn_enabled: bool
    web_research_enabled: bool
    technician_enabled: bool
    technician_auto: bool
    technician_mode: str
    technician_interval_min: int
    technician_code_fix: bool

    @classmethod
    def load(cls, *, require_telegram: bool = True, require_router: bool = True) -> Settings:
        load_dotenv(PROJECT_ROOT / ".env")

        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        router_key = os.getenv("NINE_ROUTER_API_KEY", "").strip()
        router_base_url = os.getenv("NINE_ROUTER_BASE_URL", "").strip()
        chat_base_url = os.getenv("CHAT_BASE_URL", "").strip() or router_base_url
        chat_api_key = os.getenv("CHAT_API_KEY", "").strip() or router_key
        manager_chat_base_url = os.getenv("MANAGER_CHAT_BASE_URL", "").strip()
        manager_chat_api_key = os.getenv("MANAGER_CHAT_API_KEY", "").strip()
        embedding_base_url = os.getenv("EMBEDDING_BASE_URL", "").strip() or router_base_url
        embedding_api_key = os.getenv("EMBEDDING_API_KEY", "").strip() or router_key
        stt_base_url = os.getenv("STT_BASE_URL", "").strip() or router_base_url
        stt_api_key = os.getenv("STT_API_KEY", "").strip() or router_key
        raw_allowed = os.getenv("ALLOWED_USER_IDS", "").strip()
        allowed_ids = _parse_allowed_ids(raw_allowed)

        missing: list[str] = []
        if require_telegram:
            if not telegram_token:
                missing.append("TELEGRAM_BOT_TOKEN")
            if not allowed_ids:
                missing.append("ALLOWED_USER_IDS (minimal satu numeric Telegram user ID)")
        if require_router:
            if not router_key:
                missing.append("NINE_ROUTER_API_KEY")
            if not router_base_url:
                missing.append("NINE_ROUTER_BASE_URL")
        if missing:
            raise ValueError("Isi variabel berikut di .env: " + ", ".join(missing))

        subjects = _load_subjects(PROJECT_ROOT / "config" / "subjects.yaml")
        models = _load_models(PROJECT_ROOT / "config" / "models.yaml")
        # The attached example uses one FALLBACK_MODEL; keep that shorthand supported
        # while allowing separate fallbacks for A, B, and Manager.
        fallbacks = models.setdefault("fallbacks", {})
        global_fallback = os.getenv("FALLBACK_MODEL", "").strip()
        if global_fallback:
            for role in ("agent_a", "agent_b", "agent_c", "manager"):
                raw_fallbacks = fallbacks.get(role, "")
                values = (
                    raw_fallbacks
                    if isinstance(raw_fallbacks, list)
                    else str(raw_fallbacks).split(",")
                )
                cleaned = [str(value).strip() for value in values if str(value).strip()]
                if global_fallback not in cleaned:
                    cleaned.append(global_fallback)
                fallbacks[role] = cleaned
        data_setting = Path(os.getenv("DATA_DIR", "data")).expanduser()
        data_dir = data_setting if data_setting.is_absolute() else PROJECT_ROOT / data_setting
        gdrive_backup_enabled = os.getenv("GDRIVE_BACKUP_ENABLED", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }
        gdrive_credentials_file = Path(
            os.getenv("GDRIVE_CREDENTIALS_FILE", "data/drive_credentials.json")
        ).expanduser()
        if not gdrive_credentials_file.is_absolute():
            gdrive_credentials_file = PROJECT_ROOT / gdrive_credentials_file
        gdrive_token_file = Path(
            os.getenv("GDRIVE_TOKEN_FILE", "data/drive_token.json")
        ).expanduser()
        if not gdrive_token_file.is_absolute():
            gdrive_token_file = PROJECT_ROOT / gdrive_token_file
        gdrive_root_folder = os.getenv("GDRIVE_ROOT_FOLDER", "Academic_AI").strip() or "Academic_AI"
        tts_provider = os.getenv("TTS_PROVIDER", "auto").strip().lower() or "auto"
        if tts_provider not in {"auto", "piper", "edge"}:
            raise ValueError("TTS_PROVIDER harus auto, piper, atau edge.")
        tts_voice = os.getenv("TTS_VOICE", "id_ID-fajri-medium").strip() or "id_ID-fajri-medium"
        rag_mode = os.getenv("RAG_MODE", "vector").strip().lower() or "vector"
        if rag_mode not in {"vector", "tree", "hybrid"}:
            raise ValueError("RAG_MODE harus vector, tree, atau hybrid.")
        truthy = {"1", "true", "yes", "y", "on"}
        memory_enabled = os.getenv("MEMORY_ENABLED", "true").strip().lower() in truthy
        skills_learn_enabled = os.getenv("SKILLS_LEARN_ENABLED", "true").strip().lower() in truthy
        web_research_enabled = os.getenv("WEB_RESEARCH_ENABLED", "").strip().lower() in truthy
        web_access_mode = os.getenv("WEB_ACCESS_MODE", "localhost").strip().lower() or "localhost"
        if web_access_mode not in {"localhost", "lan"}:
            raise ValueError("WEB_ACCESS_MODE harus localhost atau lan.")
        configured_web_host = os.getenv("WEB_HOST", "127.0.0.1").strip() or "127.0.0.1"
        if web_access_mode == "localhost":
            if configured_web_host not in {"127.0.0.1", "localhost"}:
                raise ValueError(
                    "Mode localhost hanya boleh menggunakan WEB_HOST=127.0.0.1 atau localhost."
                )
            web_host = configured_web_host
        else:
            # LAN mode binds to interfaces so a phone on the same trusted LAN can connect.
            # The API separately rejects non-private client addresses and still requires its bearer token.
            web_host = "0.0.0.0"  # noqa: S104

        try:
            max_pdf_mb = max(1, int(os.getenv("MAX_PDF_MB", "20")))
            max_audio_mb = max(1, int(os.getenv("MAX_AUDIO_MB", "25")))
            rag_top_k = max(1, min(20, int(os.getenv("RAG_TOP_K", "8"))))
            rag_min_score = float(os.getenv("RAG_MIN_SCORE", "0.12"))
            rag_query_variants = max(1, min(5, int(os.getenv("RAG_QUERY_VARIANTS", "4"))))
            max_output_tokens = max(100, int(os.getenv("MAX_OUTPUT_TOKENS", "2500")))
            max_revision_rounds = max(0, min(2, int(os.getenv("MAX_REVISION_ROUNDS", "2"))))
            max_context_chars = max(6000, int(os.getenv("MAX_CONTEXT_CHARS", "60000")))
            video_max_scenes = max(1, min(10, int(os.getenv("VIDEO_MAX_SCENES", "6"))))
            web_port = int(os.getenv("WEB_PORT", "8765"))
            nine_router_timeout_seconds = max(
                5.0, min(300.0, float(os.getenv("NINE_ROUTER_TIMEOUT", "90")))
            )
            nine_router_max_retries = max(0, min(5, int(os.getenv("NINE_ROUTER_MAX_RETRIES", "3"))))
        except ValueError as exc:
            raise ValueError(
                "MAX_PDF_MB, RAG_TOP_K, RAG_MIN_SCORE, RAG_QUERY_VARIANTS, MAX_OUTPUT_TOKENS, "
                "MAX_AUDIO_MB, MAX_REVISION_ROUNDS, MAX_CONTEXT_CHARS, WEB_PORT, NINE_ROUTER_TIMEOUT, "
                "VIDEO_MAX_SCENES, dan NINE_ROUTER_MAX_RETRIES harus berupa angka."
            ) from exc
        if not 1 <= web_port <= 65535:
            raise ValueError("WEB_PORT harus berada pada rentang 1–65535.")  # noqa: RUF001

        technician_enabled = os.getenv("TECHNICIAN_ENABLED", "true").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        technician_auto = os.getenv("TECHNICIAN_AUTO", "true").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        technician_mode = (
            os.getenv("TECHNICIAN_MODE", "safe").strip().lower() or "safe"
        )
        if technician_mode not in {"safe", "full"}:
            technician_mode = "safe"
        try:
            technician_interval_min = max(5, min(1440, int(os.getenv("TECHNICIAN_INTERVAL_MIN", "30"))))
        except ValueError as exc:
            raise ValueError("TECHNICIAN_INTERVAL_MIN harus berupa angka.") from exc
        technician_code_fix = os.getenv("TECHNICIAN_CODE_FIX", "true").strip().lower() in {
            "1",
            "true",
            "yes",
        }

        return cls(
            project_root=PROJECT_ROOT,
            env_file=PROJECT_ROOT / ".env",
            telegram_token=telegram_token,
            allowed_user_ids=frozenset(allowed_ids),
            nine_router_api_key=router_key,
            nine_router_base_url=router_base_url.rstrip("/"),
            nine_router_timeout_seconds=nine_router_timeout_seconds,
            nine_router_max_retries=nine_router_max_retries,
            chat_base_url=chat_base_url.rstrip("/"),
            chat_api_key=chat_api_key,
            manager_chat_base_url=manager_chat_base_url.rstrip("/"),
            manager_chat_api_key=manager_chat_api_key,
            embedding_base_url=embedding_base_url.rstrip("/"),
            embedding_api_key=embedding_api_key,
            stt_base_url=stt_base_url.rstrip("/"),
            stt_api_key=stt_api_key,
            gdrive_backup_enabled=gdrive_backup_enabled,
            gdrive_credentials_file=gdrive_credentials_file,
            gdrive_token_file=gdrive_token_file,
            gdrive_root_folder=gdrive_root_folder,
            stt_model=os.getenv("MODEL_STT", "").strip(),
            local_api_token=os.getenv("LOCAL_API_TOKEN", "").strip(),
            local_web_username=os.getenv("LOCAL_WEB_USERNAME", "").strip(),
            local_web_password=os.getenv("LOCAL_WEB_PASSWORD", ""),
            web_access_mode=web_access_mode,
            web_host=web_host,
            web_port=web_port,
            data_dir=data_dir,
            database_path=data_dir / "academic_ai.db",
            knowledge_dir=data_dir / "knowledge",
            vectorstore_dir=data_dir / "vectorstore",
            subjects=subjects,
            models=models,
            max_pdf_bytes=max_pdf_mb * 1024 * 1024,
            max_audio_bytes=max_audio_mb * 1024 * 1024,
            rag_top_k=rag_top_k,
            rag_min_score=rag_min_score,
            rag_query_variants=rag_query_variants,
            max_output_tokens=max_output_tokens,
            max_revision_rounds=max_revision_rounds,
            max_context_chars=max_context_chars,
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            tts_provider=tts_provider,
            tts_voice=tts_voice,
            video_max_scenes=video_max_scenes,
            videos_dir=data_dir / "videos",
            rag_mode=rag_mode,
            memory_enabled=memory_enabled,
            skills_learn_enabled=skills_learn_enabled,
            web_research_enabled=web_research_enabled,
            technician_enabled=technician_enabled,
            technician_auto=technician_auto,
            technician_mode=technician_mode,
            technician_interval_min=technician_interval_min,
            technician_code_fix=technician_code_fix,
        )

    @property
    def embedding_model(self) -> str:
        return str(self.models.get("embeddings", {}).get("model", "")).strip()

    @property
    def manager_model(self) -> str:
        return str(self.models.get("manager", {}).get("model", "")).strip()

    def model_for(self, subject_code: str, agent: str = "agent_a") -> str:
        subject_models = self.models.get("subjects", {}).get(subject_code, {})
        model = str(subject_models.get(agent, "")).strip()
        if not model:
            agent_suffix = {"agent_a": "A", "agent_b": "B", "agent_c": "C"}.get(agent, agent.upper())
            if agent == "manager":
                raise ValueError("MODEL_MANAGER belum diisi di .env.")
            raise ValueError(
                f"Model untuk {subject_code} {agent} belum diisi. "
                f"Isi MODEL_{subject_code}_{agent_suffix} di .env."
            )
        return model

    def fallback_models_for(self, role: str) -> list[str]:
        raw = self.models.get("fallbacks", {}).get(role, "")
        if isinstance(raw, list):
            values = raw
        else:
            values = str(raw).split(",")
        return [str(value).strip() for value in values if str(value).strip()]

    def prepare_local_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.vectorstore_dir.mkdir(parents=True, exist_ok=True)
        for subject in self.subjects.values():
            (self.knowledge_dir / subject.directory).mkdir(parents=True, exist_ok=True)


def _parse_allowed_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            ids.add(int(value))
        except ValueError as exc:
            raise ValueError("ALLOWED_USER_IDS harus berisi angka yang dipisahkan koma.") from exc
    return ids


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"File konfigurasi tidak ditemukan: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Format YAML tidak valid: {path}")
    return data


def _load_subjects(path: Path) -> dict[str, Subject]:
    raw = _load_yaml(path).get("subjects", {})
    if not isinstance(raw, dict) or not raw:
        raise ValueError("config/subjects.yaml harus berisi daftar mata kuliah.")
    subjects: dict[str, Subject] = {}
    for code, details in raw.items():
        if not isinstance(details, dict):
            raise ValueError(f"Konfigurasi subject {code} tidak valid.")
        subject_code = str(code).upper().strip()
        subjects[subject_code] = Subject(
            code=subject_code,
            name=str(details.get("name", subject_code)).strip(),
            directory=str(details.get("directory", subject_code.lower())).strip(),
            expertise=str(details.get("expertise", "")).strip(),
        )
    return subjects


def _expand_environment_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_environment_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_environment_values(item) for item in value]
    if isinstance(value, str):
        match = re.fullmatch(r"\$\{([A-Z0-9_]+)\}", value.strip())
        if match:
            return os.getenv(match.group(1), "").strip()
    return value


def _load_models(path: Path) -> dict[str, Any]:
    raw = _load_yaml(path)
    expanded = _expand_environment_values(raw)
    if not isinstance(expanded, dict):
        raise ValueError("config/models.yaml tidak valid.")
    return expanded


def _is_plain_env_key(key: str) -> bool:
    return bool(key) and key == key.upper() and key.replace("_", "").isalnum()


def _quote_env_value(value: str) -> str:
    if value == "":
        return ""
    if any(char.isspace() or char in "#\"'\\" for char in value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def update_env_file(env_path: Path, updates: dict[str, str]) -> None:
    """Rewrite .env values in place, preserving comments, order, and blank lines."""
    raw_lines = (
        env_path.read_text(encoding="utf-8").splitlines(keepends=True) if env_path.is_file() else []
    )
    replaced: set[str] = set()
    output: list[str] = []
    for line in raw_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates and key not in replaced and _is_plain_env_key(key):
                output.append(f"{key}={_quote_env_value(updates[key])}\n")
                replaced.add(key)
                continue
        output.append(line)
    for key, value in updates.items():
        if key not in replaced:
            output.append(f"{key}={_quote_env_value(value)}\n")
    env_path.write_text("".join(output), encoding="utf-8")
