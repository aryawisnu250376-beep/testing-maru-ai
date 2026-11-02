"""Isi embedding asli untuk chunk hasil ingest offline.

Jalankan SEKALI di laptop setelah .env siap (MODEL_EMBEDDING + provider):
    python tools/backfill_embeddings.py
    python tools/backfill_embeddings.py --subject PP   (satu matkul saja)

Skrip melewati dokumen yang modelnya sudah sama dengan MODEL_EMBEDDING.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import aiosqlite

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings  # noqa: E402
from app.database.database import Database  # noqa: E402
from app.knowledge.embeddings import EmbeddingService  # noqa: E402
from app.knowledge.vector_store import LocalVectorStore  # noqa: E402
from app.providers.router import build_provider  # noqa: E402


async def backfill(subject: str | None) -> int:
    settings = Settings.load(require_telegram=False)
    model = settings.embedding_model
    if not model:
        raise SystemExit("MODEL_EMBEDDING kosong di .env.")
    provider = build_provider(settings)
    service = EmbeddingService(provider, model)
    database = Database(settings.database_path)
    await database.initialize(settings.subjects)
    try:
        async with aiosqlite.connect(str(settings.database_path)) as connection:
            connection.row_factory = aiosqlite.Row
            query = "SELECT id, subject_code, original_name FROM documents WHERE embedding_model != ?"
            params: list[str] = [model]
            if subject:
                query += " AND subject_code = ?"
                params.append(subject)
            cursor = await connection.execute(query, params)
            documents = await cursor.fetchall()
            if not documents:
                print("Tidak ada dokumen yang perlu backfill.")
                return 0
            total_chunks = 0
            for doc in documents:
                cursor = await connection.execute(
                    "SELECT chunk_id, content FROM document_chunks WHERE document_id = ?"
                    " ORDER BY page_number, chunk_index",
                    (doc["id"],),
                )
                rows = await cursor.fetchall()
                print(f"Embedding {doc['subject_code']}/{doc['original_name']} ({len(rows)} chunk)...")
                vectors = await service.embed_texts([row["content"] for row in rows])
                await connection.execute("BEGIN IMMEDIATE")
                try:
                    await connection.executemany(
                        "UPDATE document_chunks SET embedding_json = ? WHERE chunk_id = ?",
                        [
                            (json.dumps(vector, separators=(",", ":")), row["chunk_id"])
                            for row, vector in zip(rows, vectors, strict=True)
                        ],
                    )
                    await connection.execute(
                        "UPDATE documents SET embedding_model = ? WHERE id = ?",
                        (model, doc["id"]),
                    )
                    await connection.commit()
                except Exception:
                    await connection.rollback()
                    raise
                total_chunks += len(rows)
        store = LocalVectorStore(database, settings.vectorstore_dir / "vectors.sqlite")
        synced = await store.sync_from_database({subject} if subject else None)
        print(f"BACKFILL_DONE docs={len(documents)} chunks={total_chunks} synced={synced}")
        return len(documents)
    finally:
        await provider.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill embedding untuk data offline.")
    parser.add_argument("--subject", default=None, help="Kode matkul (opsional).")
    args = parser.parse_args()
    asyncio.run(backfill(args.subject.upper() if args.subject else None))


if __name__ == "__main__":
    main()
