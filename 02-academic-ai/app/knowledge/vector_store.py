from __future__ import annotations

import asyncio
import json
import logging
import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

from app.database.database import Database

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    subject_code: str
    document_name: str
    page_number: int
    content: str
    score: float


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class LocalVectorStore:
    """Persistent SQLite cosine index kept in ``data/vectorstore/vectors.sqlite``.

    The main Academic AI database remains the source of truth. This separate local
    index is rebuilt from it at bot startup, so interrupted uploads/deletions can be
    repaired without leaking chunks across subject boundaries.
    """

    def __init__(self, database: Database, index_path: Path | None = None) -> None:
        self.database = database
        self.path = index_path or database.path.parent / "vectorstore" / "vectors.sqlite"
        self._initialized = False
        self._initialize_lock = asyncio.Lock()

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[aiosqlite.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self.path)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
        finally:
            await connection.close()

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            async with self._connection() as connection:
                await connection.execute("PRAGMA journal_mode = WAL")
                await connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS vectors (
                        chunk_id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL,
                        subject_code TEXT NOT NULL,
                        document_name TEXT NOT NULL,
                        page_number INTEGER NOT NULL CHECK(page_number >= 1),
                        chunk_index INTEGER NOT NULL CHECK(chunk_index >= 0),
                        content TEXT NOT NULL,
                        embedding_model TEXT NOT NULL,
                        embedding_json TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_vectors_subject_model
                        ON vectors(subject_code, embedding_model);
                    CREATE INDEX IF NOT EXISTS idx_vectors_document
                        ON vectors(subject_code, document_id);
                    """
                )
                await connection.commit()
            self._initialized = True

    async def sync_from_database(self, subject_codes: set[str] | None = None) -> int:
        """Rebuild the persistent index from committed SQLite material rows.

        When ``subject_codes`` is None every subject is rebuilt. When a set is
        given, only those subjects are deleted and re-inserted; vectors of other
        subjects are left untouched. An explicitly empty set rebuilds nothing.
        """
        await self.initialize()
        if subject_codes is None:
            subjects = set(await self.database.get_subject_codes())
            scoped_delete = False
        else:
            subjects = set(subject_codes)
            scoped_delete = True
        all_rows: list[tuple[Any, ...]] = []
        for subject_code in sorted(subjects):
            for row in await self.database.list_chunks_for_subject(subject_code):
                all_rows.append(
                    (
                        row["chunk_id"],
                        row["document_id"],
                        row["subject_code"],
                        row["document_name"],
                        row["page_number"],
                        row["chunk_index"],
                        row["content"],
                        row.get("embedding_model", ""),
                        row["embedding_json"],
                    )
                )
        async with self._connection() as connection:
            await connection.execute("BEGIN IMMEDIATE")
            try:
                if not scoped_delete:
                    await connection.execute("DELETE FROM vectors")
                elif subjects:
                    placeholders = ",".join("?" for _ in subjects)
                    await connection.execute(
                        f"DELETE FROM vectors WHERE subject_code IN ({placeholders})",  # noqa: S608
                        sorted(subjects),
                    )
                if all_rows:
                    await connection.executemany(
                        """INSERT INTO vectors(
                             chunk_id, document_id, subject_code, document_name,
                             page_number, chunk_index, content, embedding_model, embedding_json
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        all_rows,
                    )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
        logger.info("[INFO] Persistent vector index synced (%s chunks)", len(all_rows))
        return len(all_rows)

    async def index_document(
        self,
        *,
        subject_code: str,
        document_id: str,
        document_name: str,
        embedding_model: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        await self.initialize()
        rows = [
            (
                str(chunk["chunk_id"]),
                document_id,
                subject_code,
                document_name,
                int(chunk["page_number"]),
                int(chunk["chunk_index"]),
                str(chunk["content"]),
                embedding_model,
                json.dumps(chunk["embedding"], separators=(",", ":")),
            )
            for chunk in chunks
        ]
        async with self._connection() as connection:
            await connection.execute("BEGIN IMMEDIATE")
            try:
                await connection.executemany(
                    """INSERT INTO vectors(
                         chunk_id, document_id, subject_code, document_name,
                         page_number, chunk_index, content, embedding_model, embedding_json
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    rows,
                )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

    async def delete_document(self, subject_code: str, document_id: str) -> None:
        await self.initialize()
        async with self._connection() as connection:
            await connection.execute(
                "DELETE FROM vectors WHERE subject_code = ? AND document_id = ?",
                (subject_code, document_id),
            )
            await connection.commit()

    async def search(
        self,
        subject_code: str,
        query_vector: list[float],
        *,
        top_k: int = 5,
        min_score: float = 0.12,
        embedding_model: str | None = None,
    ) -> list[RetrievedChunk]:
        await self.initialize()
        async with self._connection() as connection:
            if embedding_model:
                cursor = await connection.execute(
                    """SELECT chunk_id, subject_code, document_name, page_number,
                              content, embedding_json
                       FROM vectors
                       WHERE subject_code = ? AND embedding_model = ?
                       ORDER BY document_id, page_number, chunk_index""",
                    (subject_code, embedding_model),
                )
            else:
                cursor = await connection.execute(
                    """SELECT chunk_id, subject_code, document_name, page_number,
                              content, embedding_json
                       FROM vectors
                       WHERE subject_code = ?
                       ORDER BY document_id, page_number, chunk_index""",
                    (subject_code,),
                )
            rows = await cursor.fetchall()

        ranked: list[RetrievedChunk] = []
        for row in rows:
            try:
                embedding = [float(value) for value in json.loads(row["embedding_json"])]
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            score = cosine_similarity(query_vector, embedding)
            if score < min_score:
                continue
            ranked.append(
                RetrievedChunk(
                    chunk_id=str(row["chunk_id"]),
                    subject_code=str(row["subject_code"]),
                    document_name=str(row["document_name"]),
                    page_number=int(row["page_number"]),
                    content=str(row["content"]),
                    score=score,
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[: max(1, top_k)]
