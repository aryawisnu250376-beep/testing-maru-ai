from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.database.database import Database
from app.knowledge.embeddings import EmbeddingService
from app.knowledge.vector_store import LocalVectorStore, RetrievedChunk
from app.research.librarian import Librarian
from app.research.researcher import Researcher


@dataclass(frozen=True)
class EvidencePacket:
    subject_code: str
    question: str
    chunks: list[RetrievedChunk]
    query_variants: tuple[str, ...] = ()

    @property
    def sources(self) -> list[dict[str, Any]]:
        seen: set[tuple[str, int]] = set()
        sources: list[dict[str, Any]] = []
        for chunk in self.chunks:
            key = (chunk.document_name, chunk.page_number)
            if key not in seen:
                seen.add(key)
                sources.append({"document": chunk.document_name, "page": chunk.page_number})
        return sources


class ResearchLibrarianTeam:
    """Two auditable local roles: semantic research, then citation librarianship.

    These roles use embeddings and SQLite rather than an extra chat-model call. That
    preserves free chat-model quota for the subject specialists and AI Manager.
    """

    def __init__(
        self,
        settings: Settings,
        database: Database,
        embedding_service: EmbeddingService,
        vector_store: LocalVectorStore,
    ) -> None:
        self.researcher = Researcher(settings, database, embedding_service, vector_store)
        self.librarian = Librarian(database)
        self.settings = settings

    async def collect_evidence(self, subject_code: str, question: str) -> EvidencePacket:
        raw = await self.researcher.find_evidence(subject_code, question)
        validated = await self.librarian.validate_evidence(
            subject_code,
            self.settings.embedding_model,
            raw,
        )
        return EvidencePacket(
            subject_code=subject_code,
            question=question,
            chunks=validated,
            query_variants=tuple(self.researcher.last_query_variants),
        )
