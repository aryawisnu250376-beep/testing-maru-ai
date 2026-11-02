from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.database.database import Database
from app.manager.manager import (
    AcademicManager,
    format_quiz_answer,
    format_telegram_answer,
)
from app.services.material_service import MaterialService
from app.services.video_service import VideoService
from app.services.webfetch import summarize_web
from app.services.youtube_service import (
    InvalidYouTubeUrl,
    YouTubeCaptionsUnavailable,
    fetch_public_captions,
)
from app.settings_update import current_settings_view, update_settings
from app.technician import TechnicianService
from app.web.jobs import VALID_TASKS, JobManager

logger = logging.getLogger(__name__)
LOCAL_WEB_USER_ID = 0


def is_private_lan_address(host: str | None) -> bool:
    """Allow loopback or RFC-private addresses when LAN mode is enabled."""
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private


class ChatRequest(BaseModel):
    subject_code: str = Field(min_length=2, max_length=12)
    question: str = Field(min_length=1, max_length=6000)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class TaskRequest(BaseModel):
    subject_code: str = Field(min_length=2, max_length=12)
    topic: str = Field(default="", max_length=300)


class YouTubeRequest(BaseModel):
    subject_code: str = Field(min_length=2, max_length=12)
    url: str = Field(min_length=1, max_length=500)


class JobRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20)
    subject_code: str = Field(min_length=2, max_length=12)
    topic: str = Field(default="", max_length=300)
    question: str = Field(default="", max_length=6000)


class SettingsPatchRequest(BaseModel):
    updates: dict[str, Any] = Field(min_length=1)


class TechnicianScanRequest(BaseModel):
    mode: str = Field(default="", max_length=10)


class WebRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)


AUDIO_SUFFIXES = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
    ".wave",
    ".webm",
}
AUDIO_MIME_TYPES = {
    ".aac": "audio/aac",
    ".aif": "audio/aiff",
    ".aiff": "audio/aiff",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".oga": "audio/ogg",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".wav": "audio/wav",
    ".wave": "audio/wav",
    ".webm": "audio/webm",
}


def create_app(
    *,
    settings: Settings,
    database: Database,
    academic_manager: AcademicManager,
    material_service: MaterialService,
) -> FastAPI:
    if not settings.local_api_token:
        raise ValueError("LOCAL_API_TOKEN wajib diisi sebelum menjalankan website lokal.")
    html_path = Path(__file__).with_name("index.html")
    video_service = VideoService(settings, academic_manager, database)
    job_manager = JobManager(academic_manager, database, video_service=video_service)
    technician_service = TechnicianService(settings, academic_manager)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await job_manager.start()
        technician_service.start_auto()
        try:
            yield
        finally:
            await technician_service.stop_auto()
            await job_manager.stop()

    app = FastAPI(
        title="Academic AI Local",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.academic_manager = academic_manager
    app.state.material_service = material_service
    app.state.job_manager = job_manager
    app.state.video_service = video_service
    app.state.technician_service = technician_service

    # Browser sessions persist in SQLite (survive restarts); login throttling stays in memory.
    failed_logins: dict[str, list[float]] = {}
    session_ttl_seconds = 12 * 60 * 60
    login_window_seconds = 15 * 60
    max_login_failures = 6

    def ensure_local_client(request: Request) -> None:
        if getattr(settings, "web_access_mode", "localhost") == "lan":
            client_host = request.client.host if request.client else None
            if not is_private_lan_address(client_host):
                raise HTTPException(
                    status_code=403,
                    detail="Mode LAN hanya menerima koneksi dari jaringan lokal/private.",
                )

    async def require_local_token(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> None:
        ensure_local_client(request)
        scheme, _, supplied = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not supplied:
            raise HTTPException(status_code=401, detail="Sesi login tidak valid.")

        # Keep the existing local API token working for scripts/older integrations,
        # while the browser uses a short-lived session returned by /api/login.
        expected = str(getattr(settings, "local_api_token", ""))
        if expected and hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            return

        token_hash = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
        session = await database.get_web_session(token_hash)
        if session and float(session.get("expires_at", 0)) > time.time():
            return
        await database.delete_web_session(token_hash)
        raise HTTPException(
            status_code=401, detail="Sesi login kedaluwarsa atau tidak valid. Masuk kembali."
        )

    def ensure_subject(subject_code: str):
        subject = settings.subjects.get(subject_code.upper())
        if subject is None:
            raise HTTPException(status_code=404, detail="Mata kuliah tidak dikenal.")
        return subject

    @app.get("/", include_in_schema=False)
    async def home() -> FileResponse:
        if not html_path.is_file():
            raise HTTPException(status_code=404, detail="Halaman website tidak ditemukan.")
        return FileResponse(html_path, media_type="text/html; charset=utf-8")

    @app.post("/api/login")
    async def login(request: Request, credentials: LoginRequest) -> dict[str, Any]:
        ensure_local_client(request)
        username_expected = str(getattr(settings, "local_web_username", "")).strip()
        password_expected = str(getattr(settings, "local_web_password", ""))
        if not username_expected or not password_expected.strip():
            raise HTTPException(
                status_code=503,
                detail="Atur LOCAL_WEB_USERNAME dan LOCAL_WEB_PASSWORD di file .env lokal terlebih dahulu.",
            )

        client_host = request.client.host if request.client else "unknown"
        now = time.monotonic()
        recent_failures = [
            timestamp
            for timestamp in failed_logins.get(client_host, [])
            if now - timestamp < login_window_seconds
        ]
        if len(recent_failures) >= max_login_failures:
            failed_logins[client_host] = recent_failures
            raise HTTPException(
                status_code=429,
                detail="Terlalu banyak percobaan login. Tunggu 15 menit lalu coba lagi.",
            )

        username_ok = hmac.compare_digest(
            credentials.username.strip().encode("utf-8"),
            username_expected.encode("utf-8"),
        )
        password_ok = hmac.compare_digest(
            credentials.password.encode("utf-8"),
            password_expected.encode("utf-8"),
        )
        if not (username_ok and password_ok):
            failed_logins[client_host] = [*recent_failures, now]
            raise HTTPException(status_code=401, detail="Nama pengguna atau kata sandi salah.")

        failed_logins.pop(client_host, None)
        expiry = time.time() + session_ttl_seconds
        await database.delete_expired_web_sessions(time.time())
        session_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
        await database.create_web_session(token_hash, username_expected, expiry)
        return {
            "access_token": session_token,
            "token_type": "bearer",
            "expires_in": session_ttl_seconds,
            "username": username_expected,
        }

    @app.post("/api/logout", dependencies=[Depends(require_local_token)])
    async def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
        scheme, _, supplied = (authorization or "").partition(" ")
        if scheme.lower() == "bearer" and supplied:
            token_hash = hashlib.sha256(supplied.encode("utf-8")).hexdigest()
            await database.delete_web_session(token_hash)
        return {"status": "logged_out"}

    @app.get("/api/health", dependencies=[Depends(require_local_token)])
    async def health() -> dict[str, str]:
        scope = (
            "private-lan"
            if getattr(settings, "web_access_mode", "localhost") == "lan"
            else "localhost-only"
        )
        return {"status": "ok", "application": "AI ACADEMIC", "scope": scope}

    @app.get("/api/technician/status", dependencies=[Depends(require_local_token)])
    async def technician_status() -> dict[str, Any]:
        return await technician_service.status()

    @app.post("/api/technician/scan", dependencies=[Depends(require_local_token)])
    async def technician_scan(request: TechnicianScanRequest) -> dict[str, Any]:
        return await technician_service.scan(request.mode or None)

    @app.post("/api/technician/rollback", dependencies=[Depends(require_local_token)])
    async def technician_rollback() -> dict[str, Any]:
        return await technician_service.rollback()

    @app.get("/api/subjects", dependencies=[Depends(require_local_token)])
    async def subjects() -> list[dict[str, str]]:
        return [
            {"code": subject.code, "name": subject.name} for subject in settings.subjects.values()
        ]

    @app.get("/api/stats", dependencies=[Depends(require_local_token)])
    async def stats() -> dict[str, Any]:
        """Read-only dashboard snapshot for n8n/monitoring integrations."""
        subject_rows = []
        for subject in settings.subjects.values():
            document_count, chunk_count = await database.get_subject_counts(subject.code)
            embedding_models = sorted(await database.get_embedding_models_for_subject(subject.code))
            subject_rows.append(
                {
                    "code": subject.code,
                    "name": subject.name,
                    "documents": document_count,
                    "chunks": chunk_count,
                    "embedding_models": embedding_models,
                }
            )
        return {
            "subjects": subject_rows,
            "recent_verifications": await database.get_recent_verifications(limit=20),
            "server_time": datetime.now(UTC).isoformat(),
        }

    @app.get("/api/materials/{subject_code}", dependencies=[Depends(require_local_token)])
    async def materials(subject_code: str) -> list[dict[str, Any]]:
        subject = ensure_subject(subject_code)
        return await database.list_documents(subject.code)

    @app.post("/api/materials", dependencies=[Depends(require_local_token)])
    async def upload_material(
        subject_code: str = Form(...),
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        subject = ensure_subject(subject_code)
        original_name = (file.filename or "materi.pdf").replace("\\", "/").split("/")[-1]
        if not original_name.lower().endswith(".pdf"):
            raise HTTPException(status_code=415, detail="File harus berekstensi .pdf.")
        content = await file.read(settings.max_pdf_bytes + 1)
        if len(content) > settings.max_pdf_bytes:
            raise HTTPException(status_code=413, detail="Ukuran PDF melewati batas konfigurasi.")
        if not content.startswith(b"%PDF"):
            raise HTTPException(status_code=415, detail="Isi file tidak terdeteksi sebagai PDF.")

        async def save_file(path: Path) -> None:
            await asyncio.to_thread(path.write_bytes, content)

        try:
            return await material_service.ingest_pdf(
                subject_code=subject.code,
                original_name=original_name,
                uploaded_by=LOCAL_WEB_USER_ID,
                download_to_path=save_file,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("[ERROR] Local website upload failed (%s)", type(exc).__name__)
            raise HTTPException(
                status_code=502,
                detail="PDF belum berhasil diindeks. Periksa 9Router dan log di CMD.",
            ) from exc

    @app.delete(
        "/api/materials/{subject_code}/{document_id}",
        dependencies=[Depends(require_local_token)],
    )
    async def delete_material(subject_code: str, document_id: str) -> dict[str, str]:
        subject = ensure_subject(subject_code)
        try:
            record = await material_service.delete_pdf(
                subject_code=subject.code,
                document_id=document_id,
            )
        except Exception as exc:
            logger.error("[ERROR] Local website deletion failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=500, detail="PDF belum berhasil dihapus.") from exc
        if record is None:
            raise HTTPException(status_code=404, detail="PDF tidak ditemukan.")
        return {"status": "deleted", "document_id": document_id}

    @app.post("/api/chat", dependencies=[Depends(require_local_token)])
    async def chat(request: ChatRequest) -> dict[str, Any]:
        subject = ensure_subject(request.subject_code)
        conversation_id = await _get_local_conversation(database, subject.code)
        history = await database.get_recent_messages(conversation_id, limit=8)
        question_id = await database.add_message(conversation_id, "user", request.question.strip())
        try:
            result = await academic_manager.answer(
                subject.code,
                request.question.strip(),
                history,
                question_message_id=question_id,
                user_id=LOCAL_WEB_USER_ID,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("[ERROR] Local website chat failed (%s)", type(exc).__name__)
            raise HTTPException(
                status_code=502, detail="Pertanyaan belum berhasil diproses."
            ) from exc
        formatted = format_telegram_answer(result)
        await database.add_message(conversation_id, "assistant", formatted)
        return result.as_dict()

    @app.post("/api/youtube/summary", dependencies=[Depends(require_local_token)])
    async def youtube_summary(request: YouTubeRequest) -> dict[str, Any]:
        ensure_subject(request.subject_code)
        try:
            captions = await asyncio.to_thread(
                fetch_public_captions,
                request.url,
                max_chars=getattr(settings, "max_context_chars", 60_000),
            )
        except InvalidYouTubeUrl as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except YouTubeCaptionsUnavailable as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Caption/transkrip publik tidak tersedia atau gagal diakses. Pastikan video memiliki "
                    "caption publik, lalu coba lagi. AI Study Desk tidak mengunduh audio/video."
                ),
            ) from exc
        except Exception as exc:
            logger.error("[ERROR] YouTube captions failed (%s)", type(exc).__name__)
            raise HTTPException(
                status_code=502,
                detail="Caption YouTube belum berhasil diambil. Coba lagi atau periksa koneksi internet.",
            ) from exc

        source_name = f"Video YouTube ({captions.video_id})"
        try:
            result = await academic_manager.summarize_source_text(
                source_text=captions.text,
                source_name=source_name,
                source_url=captions.url,
                source_language=captions.language,
                truncated=captions.truncated,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("[ERROR] YouTube summary failed (%s)", type(exc).__name__)
            raise HTTPException(
                status_code=502,
                detail="Caption berhasil diambil, tetapi rangkuman belum berhasil dibuat. Periksa MODEL_MANAGER dan endpoint chat Manager.",
            ) from exc
        return result.as_dict()

    @app.post("/api/transcribe", dependencies=[Depends(require_local_token)])
    async def transcribe_audio(
        file: UploadFile = File(...),
        language: str = Form(default="auto"),
    ) -> dict[str, str]:
        original_name = (file.filename or "voice-note.webm").replace("\\", "/").split("/")[-1]
        suffix = Path(original_name).suffix.lower()
        if suffix not in AUDIO_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail="Format audio belum didukung. Gunakan MP3, WAV, M4A, AAC, OGG, OPUS, WEBM, FLAC, atau AIFF.",
            )
        max_audio_bytes = int(getattr(settings, "max_audio_bytes", 25 * 1024 * 1024))
        content = await file.read(max_audio_bytes + 1)
        if not content:
            raise HTTPException(status_code=400, detail="File audio kosong.")
        if len(content) > max_audio_bytes:
            raise HTTPException(status_code=413, detail="Ukuran audio melewati batas MAX_AUDIO_MB.")

        language = language.strip().lower()
        if language != "auto" and not (len(language) in {2, 3} and language.isalpha()):
            raise HTTPException(
                status_code=422,
                detail="Kode bahasa STT harus berupa kode ISO 639-1/639-2 atau auto.",
            )
        model = str(getattr(settings, "stt_model", "")).strip()
        if not model:
            raise HTTPException(
                status_code=503,
                detail="MODEL_STT belum diisi. Pilih ID STT dari katalog 9Router GET /v1/models/stt; model chat tidak otomatis mendukung audio.",
            )
        provider = getattr(academic_manager, "provider", None)
        transcriber = getattr(provider, "transcribe", None)
        if not callable(transcriber):
            raise HTTPException(
                status_code=503, detail="Provider 9Router belum menyediakan fungsi STT."
            )

        content_type = (file.content_type or "").lower().split(";", 1)[0].strip()
        if not content_type.startswith("audio/") or content_type in {
            "audio/x-wav",
            "audio/mp3",
            "audio/x-m4a",
        }:
            content_type = AUDIO_MIME_TYPES[suffix]
        try:
            transcript = await transcriber(
                model,
                content,
                original_name,
                content_type=content_type,
                language=language,
            )
        except Exception as exc:
            logger.error("[ERROR] 9Router transcription failed (%s)", type(exc).__name__)
            raise HTTPException(
                status_code=502,
                detail="Transkripsi 9Router gagal. Periksa MODEL_STT pada katalog /v1/models/stt dan koneksi/provider.",
            ) from exc
        if not transcript.strip():
            raise HTTPException(
                status_code=422, detail="9Router tidak mengembalikan teks transkrip."
            )
        return {"text": transcript.strip(), "model": model, "language": language}

    @app.post("/api/summary", dependencies=[Depends(require_local_token)])
    async def summary(request: TaskRequest) -> dict[str, Any]:
        subject = ensure_subject(request.subject_code)
        conversation_id = await _get_local_conversation(database, subject.code)
        topic_text = request.topic.strip()
        question_id = await database.add_message(
            conversation_id,
            "user",
            f"Rangkum materi {subject.code}" + (f": {topic_text}" if topic_text else ""),
        )
        try:
            result = await academic_manager.summarize(
                subject.code,
                question_message_id=question_id,
                topic=topic_text,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("[ERROR] Local website summary failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Rangkuman belum berhasil dibuat.") from exc
        await database.add_message(conversation_id, "assistant", format_telegram_answer(result))
        return result.as_dict()

    @app.post("/api/quiz", dependencies=[Depends(require_local_token)])
    async def quiz(request: TaskRequest) -> dict[str, Any]:
        subject = ensure_subject(request.subject_code)
        conversation_id = await _get_local_conversation(database, subject.code)
        question_id = await database.add_message(
            conversation_id,
            "user",
            "/kuis " + request.topic.strip(),
        )
        try:
            result = await academic_manager.quiz(
                subject.code,
                question_message_id=question_id,
                topic=request.topic,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            logger.error("[ERROR] Local website quiz failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=502, detail="Kuis belum berhasil dibuat.") from exc
        await database.add_message(conversation_id, "assistant", format_quiz_answer(result))
        return result.as_dict()

    @app.post("/api/jobs", dependencies=[Depends(require_local_token)], status_code=202)
    async def submit_job(request: JobRequest) -> dict[str, Any]:
        subject = ensure_subject(request.subject_code)
        task = request.task.strip().lower()
        if task not in VALID_TASKS:
            raise HTTPException(
                status_code=422,
                detail=f"Tugas job tidak dikenal: {request.task}. Pilih chat, summary, quiz, atau video.",
            )
        question = request.question.strip()
        if task == "chat" and not question:
            raise HTTPException(status_code=422, detail="Pertanyaan wajib diisi untuk job chat.")
        if task == "video" and not request.topic.strip():
            raise HTTPException(status_code=422, detail="Topik wajib diisi untuk job video.")
        job = await job_manager.submit(
            task=task,
            subject_code=subject.code,
            topic=request.topic.strip(),
            question=question,
        )
        return {"job_id": job.id, "status": job.status}

    @app.get("/api/jobs", dependencies=[Depends(require_local_token)])
    async def list_jobs() -> list[dict[str, Any]]:
        return [job.as_dict() for job in job_manager.recent()]

    @app.get("/api/jobs/{job_id}", dependencies=[Depends(require_local_token)])
    async def get_job(job_id: str) -> dict[str, Any]:
        job = job_manager.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job tidak ditemukan.")
        return job.as_dict()

    @app.get("/api/export", dependencies=[Depends(require_local_token)])
    async def export_conversation(subject_code: str, format: str = "md") -> PlainTextResponse:
        subject = ensure_subject(subject_code)
        fmt = format.strip().lower()
        if fmt not in {"md", "txt"}:
            raise HTTPException(status_code=422, detail="Format harus md atau txt.")
        conversation_id = await database.get_subject_conversation_id(
            LOCAL_WEB_USER_ID, subject.code
        )
        if conversation_id is None:
            raise HTTPException(
                status_code=404, detail="Belum ada percakapan untuk mata kuliah ini."
            )
        messages = await database.get_conversation_export(conversation_id)
        if not messages:
            raise HTTPException(
                status_code=404, detail="Belum ada percakapan untuk mata kuliah ini."
            )
        body = _render_export(subject, messages, fmt)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"academic_{subject.code}_{stamp}.{fmt}"
        return PlainTextResponse(
            body, headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    @app.get("/api/videos", dependencies=[Depends(require_local_token)])
    async def list_videos() -> list[dict[str, Any]]:
        return await database.list_videos()

    @app.get("/api/videos/{video_id}/download", dependencies=[Depends(require_local_token)])
    async def download_video(video_id: str):
        record = await database.get_video(video_id)
        if (
            record is None
            or record.get("status") != "done"
            or not Path(record.get("file_path") or "").is_file()
        ):
            raise HTTPException(status_code=404, detail="Video tidak ditemukan.")
        return FileResponse(record["file_path"], media_type="video/mp4", filename=f"{video_id}.mp4")

    @app.post("/api/web", dependencies=[Depends(require_local_token)])
    async def web_summary(request: WebRequest):
        try:
            result = await summarize_web(academic_manager, request.query.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.as_dict()

    @app.get("/api/patterns", dependencies=[Depends(require_local_token)])
    async def list_patterns() -> list[str]:
        from app.knowledge.fabric_patterns import list_patterns as list_prompt_patterns

        return list_prompt_patterns()

    @app.get("/api/settings", dependencies=[Depends(require_local_token)])
    async def get_settings() -> dict[str, Any]:
        return current_settings_view(settings)

    @app.patch("/api/settings", dependencies=[Depends(require_local_token)])
    async def patch_settings(request: SettingsPatchRequest) -> dict[str, Any]:
        try:
            return update_settings(settings, request.updates)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Gagal menyimpan .env: {exc}") from exc

    return app


def _render_export(subject, messages: list[dict[str, str]], fmt: str) -> str:
    lines: list[str] = []
    if fmt == "md":
        lines.append(f"# Riwayat Belajar — {subject.code} ({subject.name})")
        lines.append("")
        for message in messages:
            who = "🧑 Kamu" if message["role"] == "user" else "🤖 Academic AI"
            lines.append(f"## {who} · {message.get('created_at', '')}")
            lines.append("")
            lines.append(message["content"])
            lines.append("")
    else:
        lines.append(f"RIWAYAT BELAJAR - {subject.code} ({subject.name})")
        lines.append("")
        for message in messages:
            who = "KAMU" if message["role"] == "user" else "ACADEMIC AI"
            lines.append(f"[{message.get('created_at', '')}] {who}:")
            lines.append(message["content"])
            lines.append("")
    return "\n".join(lines).strip() + "\n"


async def _get_local_conversation(database: Database, subject_code: str) -> int:
    await database.upsert_user(LOCAL_WEB_USER_ID, "local-web", "Local Web")
    return await database.set_active_subject(LOCAL_WEB_USER_ID, subject_code)
