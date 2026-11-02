from __future__ import annotations

import logging

from app.database.database import Database
from app.knowledge.vector_store import RetrievedChunk

logger = logging.getLogger(__name__)


class Librarian:
    """Checks document/page/chunk citations against authoritative SQLite records."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def validate_evidence(
        self,
        subject_code: str,
        embedding_model: str,
        retrieved: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        if not retrieved:
            return []
        rows = await self.database.get_chunks_by_ids(
            subject_code,
            embedding_model,
            [chunk.chunk_id for chunk in retrieved],
        )
        records = {str(row["chunk_id"]): row for row in rows}
        validated: list[RetrievedChunk] = []
        for chunk in retrieved:
            record = records.get(chunk.chunk_id)
            if record is None:
                logger.warning("[WARN] Librarian discarded an unknown or cross-subject chunk")
                continue
            if (
                str(record["subject_code"]) != subject_code
                or str(record["document_name"]) != chunk.document_name
                or int(record["page_number"]) != chunk.page_number
            ):
                logger.warning("[WARN] Librarian discarded chunk with mismatched source metadata")
                continue
            validated.append(
                RetrievedChunk(
                    chunk_id=str(record["chunk_id"]),
                    subject_code=subject_code,
                    document_name=str(record["document_name"]),
                    page_number=int(record["page_number"]),
                    content=str(record["content"]),
                    score=chunk.score,
                )
            )
        logger.info(
            "[INFO] Librarian validated %s/%s evidence chunks", len(validated), len(retrieved)
        )
        return validated
