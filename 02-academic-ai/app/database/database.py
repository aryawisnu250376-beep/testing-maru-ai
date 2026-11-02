from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import Subject

SCHEMA = """
CREATE TABLE IF NOT EXISTS subjects (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    directory TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    active_subject_code TEXT REFERENCES subjects(code) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    subject_code TEXT NOT NULL REFERENCES subjects(code),
    original_name TEXT NOT NULL,
    stored_path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    uploaded_by INTEGER NOT NULL REFERENCES users(telegram_id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL REFERENCES subjects(code),
    document_name TEXT NOT NULL,
    page_number INTEGER NOT NULL CHECK(page_number >= 1),
    chunk_index INTEGER NOT NULL CHECK(chunk_index >= 0),
    content TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, page_number, chunk_index)
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL REFERENCES subjects(code),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL REFERENCES subjects(code),
    agent_name TEXT NOT NULL,
    model_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS verification_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL DEFAULT 0 CHECK(round_number >= 0),
    decision TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    revision_instruction TEXT,
    answer_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(question_message_id, round_number)
);

CREATE TABLE IF NOT EXISTS revision_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    verification_id INTEGER REFERENCES verification_runs(id) ON DELETE SET NULL,
    round_number INTEGER NOT NULL CHECK(round_number >= 1),
    agent_a_response TEXT,
    agent_b_response TEXT,
    manager_response TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(question_message_id, round_number)
);

CREATE TABLE IF NOT EXISTS web_sessions (
    token_hash TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_subject
    ON documents(subject_code, created_at);
CREATE INDEX IF NOT EXISTS idx_chunks_subject
    ON document_chunks(subject_code, document_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_active
    ON conversations(telegram_id, is_active, updated_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_question
    ON agent_runs(question_message_id);
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    subject_code TEXT NOT NULL,
    topic TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    file_path TEXT NOT NULL DEFAULT '',
    duration_sec REAL NOT NULL DEFAULT 0,
    scene_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    error TEXT NOT NULL DEFAULT '',
    decision_log TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    fact TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS answer_skills (
    name TEXT PRIMARY KEY,
    subject_code TEXT NOT NULL DEFAULT '',
    task_mode TEXT NOT NULL DEFAULT '',
    hint TEXT NOT NULL,
    uses INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_facts_user ON user_facts(user_id);
"""


class Database:
    """Small async SQLite data layer. All database files remain under data/."""

    def __init__(self, database_path: Path) -> None:
        self.path = database_path

    def snapshot_to(self, dest: Path) -> Path:
        """Write a consistent copy of the live database via the online backup API."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        source = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        try:
            target = sqlite3.connect(str(dest))
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
        return dest

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[aiosqlite.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = await aiosqlite.connect(self.path)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA busy_timeout = 5000")
        await connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            await connection.close()

    async def initialize(self, subjects: dict[str, Subject]) -> None:
        async with self._connection() as connection:
            await connection.execute("PRAGMA journal_mode = WAL")
            await connection.executescript(SCHEMA)
            await self._ensure_column(
                connection, "documents", "embedding_model", "TEXT NOT NULL DEFAULT ''"
            )
            await self._ensure_column(
                connection, "verification_runs", "answer_json", "TEXT NOT NULL DEFAULT '{}'"
            )
            await self._ensure_column(connection, "documents", "drive_file_id", "TEXT DEFAULT NULL")
            for subject in subjects.values():
                await connection.execute(
                    """INSERT INTO subjects(code, name, directory)
                       VALUES (?, ?, ?)
                       ON CONFLICT(code) DO UPDATE SET
                         name = excluded.name,
                         directory = excluded.directory""",
                    (subject.code, subject.name, subject.directory),
                )
            await connection.commit()

    @staticmethod
    async def _ensure_column(
        connection: aiosqlite.Connection,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        cursor = await connection.execute(f"PRAGMA table_info({table_name})")
        columns = {str(row["name"]) for row in await cursor.fetchall()}
        if column_name not in columns:
            await connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            )

    async def upsert_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
    ) -> None:
        async with self._connection() as connection:
            await connection.execute(
                """INSERT INTO users(telegram_id, username, first_name)
                   VALUES (?, ?, ?)
                   ON CONFLICT(telegram_id) DO UPDATE SET
                     username = excluded.username,
                     first_name = excluded.first_name,
                     updated_at = CURRENT_TIMESTAMP""",
                (telegram_id, username, first_name),
            )
            await connection.commit()

    async def set_active_subject(self, telegram_id: int, subject_code: str) -> int:
        async with self._connection() as connection:
            await connection.execute(
                """UPDATE users
                   SET active_subject_code = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE telegram_id = ?""",
                (subject_code, telegram_id),
            )
            cursor = await connection.execute(
                """SELECT id FROM conversations
                   WHERE telegram_id = ? AND subject_code = ? AND is_active = 1
                   ORDER BY id DESC LIMIT 1""",
                (telegram_id, subject_code),
            )
            row = await cursor.fetchone()
            if row is not None:
                await connection.commit()
                return int(row["id"])

            await connection.execute(
                "UPDATE conversations SET is_active = 0 WHERE telegram_id = ?",
                (telegram_id,),
            )
            cursor = await connection.execute(
                """INSERT INTO conversations(telegram_id, subject_code, is_active)
                   VALUES (?, ?, 1)""",
                (telegram_id, subject_code),
            )
            await connection.commit()
            return int(cursor.lastrowid)

    async def get_active_subject_code(self, telegram_id: int) -> str | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "SELECT active_subject_code FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            row = await cursor.fetchone()
            return str(row["active_subject_code"]) if row and row["active_subject_code"] else None

    async def get_active_conversation_id(self, telegram_id: int) -> int | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """SELECT id FROM conversations
                   WHERE telegram_id = ? AND is_active = 1
                   ORDER BY id DESC LIMIT 1""",
                (telegram_id,),
            )
            row = await cursor.fetchone()
            return int(row["id"]) if row else None

    async def reset_conversation(self, telegram_id: int) -> int | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "SELECT active_subject_code FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            user_row = await cursor.fetchone()
            if user_row is None or not user_row["active_subject_code"]:
                return None
            subject_code = str(user_row["active_subject_code"])
            await connection.execute(
                "UPDATE conversations SET is_active = 0 WHERE telegram_id = ?",
                (telegram_id,),
            )
            cursor = await connection.execute(
                """INSERT INTO conversations(telegram_id, subject_code, is_active)
                   VALUES (?, ?, 1)""",
                (telegram_id, subject_code),
            )
            await connection.commit()
            return int(cursor.lastrowid)

    async def add_message(self, conversation_id: int, role: str, content: str) -> int:
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Role pesan tidak valid: {role}")
        async with self._connection() as connection:
            cursor = await connection.execute(
                "INSERT INTO messages(conversation_id, role, content) VALUES (?, ?, ?)",
                (conversation_id, role, content),
            )
            await connection.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,),
            )
            await connection.commit()
            return int(cursor.lastrowid)

    async def get_recent_messages(
        self,
        conversation_id: int,
        limit: int = 8,
    ) -> list[dict[str, str]]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """SELECT role, content FROM messages
                   WHERE conversation_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (conversation_id, max(0, limit)),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in reversed(rows)]

    async def get_subject_conversation_id(self, telegram_id: int, subject_code: str) -> int | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """SELECT id FROM conversations
                   WHERE telegram_id = ? AND subject_code = ?
                   ORDER BY updated_at DESC, id DESC LIMIT 1""",
                (telegram_id, subject_code),
            )
            row = await cursor.fetchone()
            return int(row["id"]) if row else None

    async def get_conversation_export(
        self, conversation_id: int, limit: int = 500
    ) -> list[dict[str, str]]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """SELECT role, content, created_at FROM messages
                   WHERE conversation_id = ? ORDER BY id ASC LIMIT ?""",
                (conversation_id, max(1, min(2000, limit))),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_document_and_chunks(
        self,
        document: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> None:
        """Persist one PDF and all its page-aware embedded chunks atomically."""
        async with self._connection() as connection:
            await connection.execute("BEGIN IMMEDIATE")
            try:
                await connection.execute(
                    """INSERT INTO documents(
                         id, subject_code, original_name, stored_path, sha256,
                         embedding_model, file_size_bytes, page_count, uploaded_by
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        document["id"],
                        document["subject_code"],
                        document["original_name"],
                        document["stored_path"],
                        document["sha256"],
                        document["embedding_model"],
                        document["file_size_bytes"],
                        document["page_count"],
                        document["uploaded_by"],
                    ),
                )
                chunk_rows = [
                    (
                        chunk["chunk_id"],
                        document["id"],
                        document["subject_code"],
                        document["original_name"],
                        chunk["page_number"],
                        chunk["chunk_index"],
                        chunk["content"],
                        json.dumps(chunk["embedding"], separators=(",", ":")),
                    )
                    for chunk in chunks
                ]
                await connection.executemany(
                    """INSERT INTO document_chunks(
                         chunk_id, document_id, subject_code, document_name,
                         page_number, chunk_index, content, embedding_json
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    chunk_rows,
                )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

    async def list_documents(self, subject_code: str) -> list[dict[str, Any]]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """SELECT id, original_name, page_count, file_size_bytes, created_at
                   FROM documents WHERE subject_code = ?
                   ORDER BY created_at, original_name""",
                (subject_code,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_document(self, subject_code: str, document_id: str) -> dict[str, Any] | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """SELECT id, subject_code, original_name, stored_path, drive_file_id
                   FROM documents WHERE id = ? AND subject_code = ?""",
                (document_id, subject_code),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def delete_document(self, subject_code: str, document_id: str) -> dict[str, Any] | None:
        """Delete document metadata and cascade-delete its chunks; return file metadata."""
        async with self._connection() as connection:
            await connection.execute("BEGIN IMMEDIATE")
            cursor = await connection.execute(
                """SELECT id, original_name, stored_path, drive_file_id FROM documents
                   WHERE id = ? AND subject_code = ?""",
                (document_id, subject_code),
            )
            row = await cursor.fetchone()
            if row is None:
                await connection.rollback()
                return None
            record = dict(row)
            await connection.execute(
                "DELETE FROM documents WHERE id = ? AND subject_code = ?",
                (document_id, subject_code),
            )
            await connection.commit()
            return record

    async def set_document_drive_id(self, document_id: str, drive_file_id: str) -> None:
        """Record the Google Drive backup file ID for one document."""
        async with self._connection() as connection:
            await connection.execute(
                "UPDATE documents SET drive_file_id = ? WHERE id = ?",
                (drive_file_id, document_id),
            )
            await connection.commit()

    async def list_chunks_for_subject(
        self,
        subject_code: str,
        embedding_model: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return chunks from exactly one subject and, when given, one embedding model."""
        async with self._connection() as connection:
            if embedding_model:
                cursor = await connection.execute(
                    """SELECT c.chunk_id, c.document_id, c.subject_code, c.document_name,
                              c.page_number, c.chunk_index, c.content, c.embedding_json,
                              d.embedding_model
                       FROM document_chunks AS c
                       JOIN documents AS d ON d.id = c.document_id
                       WHERE c.subject_code = ? AND d.embedding_model = ?
                       ORDER BY d.created_at, c.page_number, c.chunk_index""",
                    (subject_code, embedding_model),
                )
            else:
                cursor = await connection.execute(
                    """SELECT c.chunk_id, c.document_id, c.subject_code, c.document_name,
                              c.page_number, c.chunk_index, c.content, c.embedding_json,
                              d.embedding_model
                       FROM document_chunks AS c
                       JOIN documents AS d ON d.id = c.document_id
                       WHERE c.subject_code = ?
                       ORDER BY d.created_at, c.page_number, c.chunk_index""",
                    (subject_code,),
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_chunks_by_ids(
        self,
        subject_code: str,
        embedding_model: str,
        chunk_ids: list[str],
    ) -> list[dict[str, Any]]:
        unique_ids = list(dict.fromkeys(chunk_ids))
        if not unique_ids:
            return []
        placeholders = ",".join("?" for _ in unique_ids)
        # Only generated "?" placeholders are interpolated; all values stay bound parameters.
        query = (
            "SELECT c.chunk_id, c.document_id, c.subject_code, c.document_name,"  # noqa: S608
            " c.page_number, c.chunk_index, c.content, d.embedding_model"
            " FROM document_chunks AS c"
            " JOIN documents AS d ON d.id = c.document_id"
            " WHERE c.subject_code = ? AND d.embedding_model = ?"
            f" AND c.chunk_id IN ({placeholders})"
        )
        async with self._connection() as connection:
            cursor = await connection.execute(
                query,
                [subject_code, embedding_model, *unique_ids],
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_embedding_models_for_subject(self, subject_code: str) -> set[str]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "SELECT DISTINCT embedding_model FROM documents WHERE subject_code = ?",
                (subject_code,),
            )
            rows = await cursor.fetchall()
            return {str(row["embedding_model"]) for row in rows}

    async def get_subject_codes(self) -> set[str]:
        async with self._connection() as connection:
            cursor = await connection.execute("SELECT code FROM subjects ORDER BY code")
            rows = await cursor.fetchall()
            return {str(row["code"]) for row in rows}

    async def get_subject_counts(self, subject_code: str) -> tuple[int, int]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "SELECT COUNT(*) AS total FROM documents WHERE subject_code = ?",
                (subject_code,),
            )
            documents_row = await cursor.fetchone()
            cursor = await connection.execute(
                "SELECT COUNT(*) AS total FROM document_chunks WHERE subject_code = ?",
                (subject_code,),
            )
            chunks_row = await cursor.fetchone()
            return int(documents_row["total"]), int(chunks_row["total"])

    async def record_verification_run(
        self,
        question_message_id: int,
        round_number: int,
        decision: str,
        confidence: float,
        reason: str,
        revision_instruction: str | None,
        result: dict[str, Any],
    ) -> int:
        async with self._connection() as connection:
            cursor = await connection.execute(
                """INSERT INTO verification_runs(
                     question_message_id, round_number, decision, confidence,
                     reason, revision_instruction, answer_json
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    question_message_id,
                    round_number,
                    decision,
                    confidence,
                    reason,
                    revision_instruction,
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            await connection.commit()
            return int(cursor.lastrowid)

    async def record_revision_run(
        self,
        question_message_id: int,
        verification_id: int | None,
        round_number: int,
        agent_a_response: str | None,
        agent_b_response: str | None,
        manager_response: str | None,
    ) -> None:
        async with self._connection() as connection:
            await connection.execute(
                """INSERT INTO revision_runs(
                     question_message_id, verification_id, round_number,
                     agent_a_response, agent_b_response, manager_response
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    question_message_id,
                    verification_id,
                    round_number,
                    agent_a_response,
                    agent_b_response,
                    manager_response,
                ),
            )
            await connection.commit()

    async def record_agent_run(
        self,
        question_message_id: int,
        subject_code: str,
        agent_name: str,
        model_id: str,
        status: str,
        result: dict[str, Any],
    ) -> None:
        async with self._connection() as connection:
            await connection.execute(
                """INSERT INTO agent_runs(
                     question_message_id, subject_code, agent_name,
                     model_id, status, result_json
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    question_message_id,
                    subject_code,
                    agent_name,
                    model_id,
                    status,
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            await connection.commit()

    async def get_recent_verifications(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the newest manager verification decisions for dashboards/eval loops."""
        async with self._connection() as connection:
            cursor = await connection.execute(
                """SELECT question_message_id, round_number, decision,
                          confidence, reason, created_at
                   FROM verification_runs
                   ORDER BY id DESC LIMIT ?""",
                (max(1, min(100, limit)),),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def create_web_session(self, token_hash: str, username: str, expires_at: float) -> None:
        async with self._connection() as connection:
            await connection.execute(
                """INSERT INTO web_sessions(token_hash, username, expires_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(token_hash) DO UPDATE SET
                     username = excluded.username,
                     expires_at = excluded.expires_at""",
                (token_hash, username, expires_at),
            )
            await connection.commit()

    async def get_web_session(self, token_hash: str) -> dict[str, Any] | None:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "SELECT token_hash, username, expires_at FROM web_sessions WHERE token_hash = ?",
                (token_hash,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def delete_web_session(self, token_hash: str) -> None:
        async with self._connection() as connection:
            await connection.execute("DELETE FROM web_sessions WHERE token_hash = ?", (token_hash,))
            await connection.commit()

    async def delete_expired_web_sessions(self, now: float) -> int:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "DELETE FROM web_sessions WHERE expires_at <= ?", (now,)
            )
            await connection.commit()
            return cursor.rowcount or 0

    async def create_video(
        self, *, video_id: str, subject_code: str, topic: str, title: str
    ) -> None:
        async with self._connection() as connection:
            await connection.execute(
                "INSERT INTO videos(id, subject_code, topic, title) VALUES (?, ?, ?, ?)",
                (video_id, subject_code, topic, title),
            )
            await connection.commit()

    async def update_video_status(self, video_id: str, status: str, **fields) -> None:
        allowed = {"file_path", "duration_sec", "scene_count", "error", "decision_log"}
        updates = ["status = ?"]
        values: list = [status]
        for key, value in fields.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)
        values.append(video_id)
        async with self._connection() as connection:
            query = f"UPDATE videos SET {', '.join(updates)} WHERE id = ?"  # noqa: S608 - allowlist
            await connection.execute(query, values)
            await connection.commit()

    async def get_video(self, video_id: str) -> dict | None:
        async with self._connection() as connection:
            cursor = await connection.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_videos(self, limit: int = 50) -> list[dict]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "SELECT id, subject_code, topic, title, duration_sec, scene_count,"
                " status, error, created_at FROM videos ORDER BY created_at DESC LIMIT ?",
                (max(1, min(200, limit)),),
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def add_fact(self, user_id: int, fact: str) -> None:
        async with self._connection() as connection:
            await connection.execute(
                "INSERT INTO user_facts(user_id, fact) VALUES (?, ?)", (user_id, fact)
            )
            await connection.commit()

    async def list_facts(self, user_id: int) -> list[dict]:
        async with self._connection() as connection:
            cursor = await connection.execute(
                "SELECT fact FROM user_facts WHERE user_id = ? ORDER BY id ASC", (user_id,)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def trim_facts(self, user_id: int, keep: int) -> None:
        async with self._connection() as connection:
            await connection.execute(
                "DELETE FROM user_facts WHERE user_id = ? AND id NOT IN"
                " (SELECT id FROM user_facts WHERE user_id = ? ORDER BY id DESC LIMIT ?)",
                (user_id, user_id, max(1, keep)),
            )
            await connection.commit()

    async def upsert_skill(
        self, name: str, *, subject_code: str, task_mode: str, hint: str, won: bool
    ) -> None:
        async with self._connection() as connection:
            await connection.execute(
                "INSERT INTO answer_skills(name, subject_code, task_mode, hint, uses, wins)"
                " VALUES (?, ?, ?, ?, 1, ?) ON CONFLICT(name) DO UPDATE SET"
                " hint = excluded.hint, uses = uses + 1, wins = wins + ?",
                (name, subject_code, task_mode, hint, 1 if won else 0, 1 if won else 0),
            )
            await connection.commit()

    async def get_skill(self, name: str) -> dict | None:
        async with self._connection() as connection:
            cursor = await connection.execute("SELECT * FROM answer_skills WHERE name = ?", (name,))
            row = await cursor.fetchone()
            return dict(row) if row else None
