from __future__ import annotations

import logging
import re

from app.config import Settings
from app.database.database import Database
from app.knowledge.embeddings import EmbeddingService
from app.knowledge.vector_store import LocalVectorStore, RetrievedChunk

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset(
    """
    apa apakah bagaimana berapakah berapa kapan kapankah mengapa mengapakah
    siapa siapakah mana yang yaitu yakni adalah ialah di ke dari pada untuk
    dengan dan atau tetapi tapi namun sedangkan sementara jika kalau bila
    apabila karena sehingga agar supaya ini itu tersebut sangat lebih paling
    kurang tidak bukan belum sudah telah akan sedang masih juga hanya saja
    pun lah kah tah tolong mohon jelaskan uraikan sebutkan berikan tentang
    mengenai dalam antara setiap semua seluruh tiap sebagai oleh arti apa
    what when where which who whom whose why how is are was were be been
    the a an of and or in on to for with by from as at it its this that
    these those explain describe tell give about meaning define list
    """.split()
)

_WORD = re.compile(r"[A-Za-zÀ-ÿ0-9']+")


def build_query_variants(question: str, max_variants: int) -> list[str]:
    """Original question plus cheap rule-based reformulations (deduped).

    Extra variants only cost local embedding + local vector search — no chat
    quota — while catching chunks a single phrasing would miss.
    """
    cleaned = " ".join(question.split())
    if not cleaned:
        return [question]
    variants = [cleaned]
    keywords = " ".join(
        word for word in _WORD.findall(cleaned) if len(word) > 2 and word.lower() not in _STOPWORDS
    )
    if keywords and keywords.lower() != cleaned.lower():
        variants.append(keywords)
    if len(cleaned) > 120:
        for sentence in re.split(r"[.?!\n]+", cleaned):
            if len(sentence.strip()) > 40:
                variants.append(sentence.strip())
            if len(variants) >= max(1, max_variants):
                break
    return list(dict.fromkeys(variants))[: max(1, max_variants)]


class Researcher:
    """Finds relevant evidence only inside the selected subject knowledge base."""

    def __init__(
        self,
        settings: Settings,
        database: Database,
        embedding_service: EmbeddingService,
        vector_store: LocalVectorStore,
    ) -> None:
        self.settings = settings
        self.database = database
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.last_query_variants: list[str] = []

    async def find_evidence(self, subject_code: str, question: str) -> list[RetrievedChunk]:
        embedding_model = self.settings.embedding_model
        if not embedding_model:
            raise ValueError("MODEL_EMBEDDING belum diisi di .env.")
        indexed_models = await self.database.get_embedding_models_for_subject(subject_code)
        if embedding_model not in indexed_models:
            raise ValueError(
                "MODEL_EMBEDDING berbeda dari model yang dipakai saat PDF diindeks. "
                "Gunakan model embedding lama atau unggah ulang PDF."
            )
        variants = build_query_variants(question, self.settings.rag_query_variants)
        self.last_query_variants = list(variants)
        vectors = await self.embedding_service.embed_texts(variants)
        merged: dict[str, RetrievedChunk] = {}
        cross_subject = 0
        for query_vector in vectors:
            found = await self.vector_store.search(
                subject_code,
                query_vector,
                top_k=self.settings.rag_top_k,
                min_score=self.settings.rag_min_score,
                embedding_model=embedding_model,
            )
            for chunk in found:
                # Defence in depth: even a malformed/stale index cannot cross subjects.
                if chunk.subject_code != subject_code:
                    cross_subject += 1
                    continue
                previous = merged.get(chunk.chunk_id)
                if previous is None or chunk.score > previous.score:
                    merged[chunk.chunk_id] = chunk
        if cross_subject:
            logger.error("[ERROR] Researcher discarded cross-subject vector results")
        merged_cap = self.settings.rag_top_k + max(0, len(variants) - 1) * 2
        scoped = sorted(merged.values(), key=lambda item: item.score, reverse=True)[:merged_cap]
        logger.info(
            "[INFO] Researcher: %s varian kueri -> %s chunk bukti untuk %s",
            len(variants),
            len(scoped),
            subject_code,
        )
        return scoped
