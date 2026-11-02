from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.manager.manager import format_quiz_answer, format_telegram_answer

logger = logging.getLogger(__name__)

LOCAL_WEB_USER_ID = 0  # same single local user as the web API
MAX_STORED_JOBS = 50
VALID_TASKS = ("chat", "summary", "quiz", "video")


@dataclass
class Job:
    id: str
    task: str
    subject_code: str
    topic: str = ""
    question: str = ""
    status: str = "queued"  # queued | running | done | failed
    stage: str = "queued"
    detail: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    result: dict[str, Any] | None = None
    error: str = ""

    def touch(
        self,
        *,
        status: str | None = None,
        stage: str | None = None,
        detail: str | None = None,
    ) -> None:
        if status is not None:
            self.status = status
        if stage is not None:
            self.stage = stage
        if detail is not None:
            self.detail = detail
        self.updated_at = time.time()

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "task": self.task,
            "subject_code": self.subject_code,
            "topic": self.topic,
            "question": self.question,
            "status": self.status,
            "stage": self.stage,
            "detail": self.detail,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "error": self.error,
        }


class JobManager:
    """Sequential in-process background jobs for slow AI tasks (local use).

    One worker processes jobs FIFO so SQLite and memory stay safe. Job records
    live in memory; restarting the web app drops them (conversation history in
    SQLite is unaffected).
    """

    def __init__(
        self, academic_manager, database, *, max_stored: int = MAX_STORED_JOBS, video_service=None
    ) -> None:
        self.academic_manager = academic_manager
        self.database = database
        self.video_service = video_service
        self.max_stored = max(10, max_stored)
        self.jobs: dict[str, Job] = {}
        # Created lazily: an asyncio.Queue binds to the loop that first uses it,
        # and app objects may outlive a loop (tests, reloads).
        self.queue: asyncio.Queue[str] | None = None
        self._worker: asyncio.Task | None = None

    async def submit(
        self, *, task: str, subject_code: str, topic: str = "", question: str = ""
    ) -> Job:
        if task not in VALID_TASKS:
            raise ValueError(f"Tugas job tidak dikenal: {task}")
        job = Job(
            id=uuid4().hex[:12],
            task=task,
            subject_code=subject_code,
            topic=topic,
            question=question,
        )
        self.jobs[job.id] = job
        self._trim()
        await self._ensure_queue().put(job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def recent(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda item: item.created_at, reverse=True)

    def _trim(self) -> None:
        if len(self.jobs) <= self.max_stored:
            return
        finished = sorted(
            (job for job in self.jobs.values() if job.status in {"done", "failed"}),
            key=lambda job: job.created_at,
        )
        for job in finished[: len(self.jobs) - self.max_stored]:
            del self.jobs[job.id]

    def _ensure_queue(self) -> asyncio.Queue[str]:
        if self.queue is None:
            self.queue = asyncio.Queue()
        return self.queue

    async def start(self) -> None:
        self._ensure_queue()
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._worker_loop(), name="academic-ai-jobs")

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None
        self.queue = None
        for job in self.jobs.values():
            if job.status in {"queued", "running"}:
                job.touch(status="failed", stage="failed")
                if not job.error:
                    job.error = "Server dihentikan sebelum job selesai."

    async def _worker_loop(self) -> None:
        queue = self._ensure_queue()
        while True:
            job_id = await queue.get()
            job: Job | None = None
            try:
                job = self.jobs.get(job_id)
                if job is not None:
                    await self._run(job)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("[ERROR] Job worker gagal (%s)", type(exc).__name__)
                if job is not None and job.status not in {"done", "failed"}:
                    job.touch(status="failed", stage="failed")
                    job.error = f"Kesalahan internal worker: {type(exc).__name__}"
            finally:
                queue.task_done()

    async def _run(self, job: Job) -> None:
        job.touch(status="running", stage="start", detail=(job.topic or job.question)[:80])

        def progress(stage: str, detail: str = "") -> None:
            job.touch(stage=stage, detail=detail)

        try:
            await self.database.upsert_user(LOCAL_WEB_USER_ID, "local-web", "Local Web")
            conversation_id = await self.database.set_active_subject(
                LOCAL_WEB_USER_ID, job.subject_code
            )
            if job.task == "chat":
                history = await self.database.get_recent_messages(conversation_id, limit=8)
                question_id = await self.database.add_message(conversation_id, "user", job.question)
                result = await self.academic_manager.answer(
                    job.subject_code,
                    job.question,
                    history,
                    question_message_id=question_id,
                    progress_callback=progress,
                )
                formatted = format_telegram_answer(result)
            elif job.task == "summary":
                label = f"Rangkum materi {job.subject_code}" + (
                    f": {job.topic}" if job.topic else ""
                )
                question_id = await self.database.add_message(conversation_id, "user", label)
                result = await self.academic_manager.summarize(
                    job.subject_code,
                    question_message_id=question_id,
                    topic=job.topic,
                    progress_callback=progress,
                )
                formatted = format_telegram_answer(result)
            elif job.task == "video":
                if not job.topic:
                    raise ValueError("Topik wajib diisi untuk job video.")
                if self.video_service is None:
                    raise ValueError("Layanan video belum siap.")
                question_id = await self.database.add_message(
                    conversation_id, "user", "/video " + job.topic
                )
                video_meta = await self.video_service.build_video(
                    subject_code=job.subject_code,
                    topic=job.topic,
                    question_message_id=question_id,
                    progress=progress,
                )
                formatted = (
                    f"Video: {video_meta['title']} ({video_meta['scene_count']} adegan,"
                    f" {video_meta['duration_sec']} dtk) {video_meta['download_url']}"
                )
                await self.database.add_message(conversation_id, "assistant", formatted)
                job.result = video_meta
                job.touch(status="done", stage="done")
                return
            else:  # quiz
                question_id = await self.database.add_message(
                    conversation_id, "user", "/kuis " + job.topic
                )
                result = await self.academic_manager.quiz(
                    job.subject_code,
                    question_message_id=question_id,
                    topic=job.topic,
                    progress_callback=progress,
                )
                formatted = format_quiz_answer(result)
        except ValueError as exc:
            job.touch(status="failed", stage="failed")
            job.error = str(exc)
            return
        except Exception as exc:
            logger.error("[ERROR] Job %s gagal (%s)", job.id, type(exc).__name__)
            job.touch(status="failed", stage="failed")
            job.error = "Tugas belum berhasil diproses. Lihat data/logs/web.log."
            return
        await self.database.add_message(conversation_id, "assistant", formatted)
        job.result = result.as_dict()
        job.touch(status="done", stage="done")
