from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.database.database import Database
from app.knowledge.chunker import chunk_pages
from app.knowledge.embeddings import EmbeddingService
from app.knowledge.pdf_processor import extract_pdf_pages
from app.knowledge.vector_store import LocalVectorStore
from app.services.drive_backup import DriveBackupService, backup_database_snapshot

logger = logging.getLogger(__name__)
DownloadToPath = Callable[[Path], Awaitable[None]]


class MaterialService:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        embedding_service: EmbeddingService,
        vector_store: LocalVectorStore | None = None,
        drive_backup: DriveBackupService | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.embedding_service = embedding_service
        self.drive_backup = drive_backup
        self.vector_store = vector_store or LocalVectorStore(
            database,
            settings.vectorstore_dir / "vectors.sqlite",
        )

    async def _backup_to_drive_best_effort(
        self,
        *,
        subject_code: str,
        original_name: str,
        stored_file: Path,
        document_id: str,
        sha256: str,
    ) -> str | None:
        """Upload the ingested PDF to Drive; never fail the ingest on Drive errors."""
        if self.drive_backup is None:
            return None
        try:
            drive_file_id = await self.drive_backup.backup_document(
                subject_code=subject_code,
                original_name=original_name,
                local_path=stored_file,
                document_id=document_id,
                sha256=sha256,
            )
        except Exception as exc:
            logger.warning("[WARN] Backup Drive dilewati (%s): %s", type(exc).__name__, exc)
            return None
        if drive_file_id:
            try:
                await self.database.set_document_drive_id(document_id, drive_file_id)
            except Exception as exc:
                logger.warning("[WARN] Gagal menyimpan Drive file ID (%s)", type(exc).__name__)
        return drive_file_id

    async def _delete_drive_backup_best_effort(
        self, document_id: str, record: dict[str, object]
    ) -> None:
        """Remove the Drive backup; never fail the local delete on Drive errors."""
        if self.drive_backup is None:
            return
        try:
            drive_file_id = record.get("drive_file_id")
            await self.drive_backup.delete_document_backup(
                document_id,
                str(drive_file_id) if drive_file_id else None,
            )
        except Exception as exc:
            logger.warning("[WARN] Hapus backup Drive dilewati (%s): %s", type(exc).__name__, exc)

    async def _backup_database_best_effort(self) -> str | None:
        """Back up a DB snapshot after content milestones; never fail the caller."""
        if self.drive_backup is None:
            return None
        try:
            return await backup_database_snapshot(self.drive_backup, self.database.path)
        except Exception as exc:
            logger.warning(
                "[WARN] Backup database Drive dilewati (%s): %s", type(exc).__name__, exc
            )
            return None

    def _safe_filename(self, original_name: str) -> str:
        basename = original_name.replace("\\", "/").split("/")[-1].strip()
        safe = re.sub(r"[^A-Za-z0-9._ -]", "_", basename).strip(" .")
        if not safe:
            safe = "materi.pdf"
        if not safe.lower().endswith(".pdf"):
            safe += ".pdf"
        return safe

    async def delete_pdf(self, *, subject_code: str, document_id: str) -> dict[str, object] | None:
        metadata = await self.database.get_document(subject_code, document_id)
        if metadata is None:
            # Also clean a possible stale sidecar entry for this ID.
            await self.vector_store.delete_document(subject_code, document_id)
            return None

        stored = Path(str(metadata["stored_path"]))
        path = stored if stored.is_absolute() else self.settings.project_root / stored
        resolved = path.resolve()
        knowledge_root = self.settings.knowledge_dir.resolve()
        if not resolved.is_relative_to(knowledge_root):
            raise ValueError("Path materi di database berada di luar folder knowledge.")

        await self.vector_store.delete_document(subject_code, document_id)
        try:
            record = await self.database.delete_document(subject_code, document_id)
        except Exception:
            # Repair the vector sidecar if the authoritative SQLite delete failed.
            await self.vector_store.sync_from_database()
            raise
        if record is None:
            await self.vector_store.sync_from_database()
            return None
        await self._delete_drive_backup_best_effort(document_id, record)
        try:
            resolved.unlink(missing_ok=True)
        except OSError as exc:
            logger.error("[ERROR] PDF file unlink failed (%s)", type(exc).__name__)
            raise RuntimeError(
                "Record materi terhapus, tetapi file PDF lokal gagal dihapus."
            ) from exc
        await self._backup_database_best_effort()
        return record

    async def ingest_pdf(
        self,
        *,
        subject_code: str,
        original_name: str,
        uploaded_by: int,
        download_to_path: DownloadToPath,
    ) -> dict[str, object]:
        subject = self.settings.subjects.get(subject_code)
        if subject is None:
            raise ValueError("Mata kuliah tidak dikenal.")

        document_id = uuid4().hex
        subject_dir = self.settings.knowledge_dir / subject.directory
        subject_dir.mkdir(parents=True, exist_ok=True)
        stored_file = subject_dir / f"{document_id}_{self._safe_filename(original_name)}"
        persisted = False

        try:
            await download_to_path(stored_file)
            if not stored_file.is_file():
                raise RuntimeError("File PDF tidak berhasil tersimpan ke folder lokal.")
            file_size = stored_file.stat().st_size
            if file_size == 0:
                raise ValueError("File PDF kosong.")
            if file_size > self.settings.max_pdf_bytes:
                max_mb = self.settings.max_pdf_bytes // (1024 * 1024)
                raise ValueError(f"Ukuran PDF melewati batas {max_mb} MB.")

            pages = await asyncio.to_thread(extract_pdf_pages, stored_file)
            text_chunks = chunk_pages(
                document_id=document_id,
                document_name=original_name,
                pages=pages,
            )
            if not text_chunks:
                raise ValueError("PDF tidak menghasilkan potongan teks untuk diindeks.")

            vectors = await self.embedding_service.embed_texts(
                [chunk.content for chunk in text_chunks]
            )
            if len(vectors) != len(text_chunks):
                raise RuntimeError("Jumlah embedding tidak sama dengan jumlah potongan PDF.")

            chunk_rows = [
                {
                    "chunk_id": chunk.chunk_id,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "embedding": vector,
                }
                for chunk, vector in zip(text_chunks, vectors, strict=True)
            ]
            sha256 = await asyncio.to_thread(_sha256_file, stored_file)
            try:
                portable_path = stored_file.relative_to(self.settings.project_root).as_posix()
            except ValueError:
                portable_path = stored_file.as_posix()

            document_record = {
                "id": document_id,
                "subject_code": subject_code,
                "original_name": original_name,
                "stored_path": portable_path,
                "sha256": sha256,
                "embedding_model": self.embedding_service.model,
                "file_size_bytes": file_size,
                "page_count": len(pages),
                "uploaded_by": uploaded_by,
            }
            await self.database.add_document_and_chunks(document_record, chunk_rows)
            persisted = True
            await self.vector_store.index_document(
                subject_code=subject_code,
                document_id=document_id,
                document_name=original_name,
                embedding_model=self.embedding_service.model,
                chunks=chunk_rows,
            )
            drive_file_id = await self._backup_to_drive_best_effort(
                subject_code=subject_code,
                original_name=original_name,
                stored_file=stored_file,
                document_id=document_id,
                sha256=sha256,
            )
            await self._backup_database_best_effort()
            return {
                "id": document_id,
                "original_name": original_name,
                "subject_code": subject_code,
                "page_count": len(pages),
                "chunk_count": len(chunk_rows),
                "file_size_bytes": file_size,
                "drive_file_id": drive_file_id,
            }
        except Exception:
            # A failed index/write must not leave an orphan file or a half-indexed document.
            if persisted:
                try:
                    await self.vector_store.delete_document(subject_code, document_id)
                    await self.database.delete_document(subject_code, document_id)
                except Exception as cleanup_error:
                    logger.error("[ERROR] Upload cleanup failed (%s)", type(cleanup_error).__name__)
                    try:
                        await self.vector_store.sync_from_database()
                    except Exception as sync_error:
                        logger.error(
                            "[ERROR] Upload cleanup resync failed (%s)", type(sync_error).__name__
                        )
            if stored_file.exists():
                try:
                    stored_file.unlink()
                except OSError:
                    pass
            raise


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
