"""PageIndex-inspired structure-aware retrieval (lexical, no LLM, no SDK).

Builds a section tree from chunk rows (headings -> sections -> pages), then
picks sections by query overlap. Vectorless: no embeddings at query time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.knowledge.vector_store import RetrievedChunk

_NUMBERED = re.compile(r"^(\d+(\.\d+)*)\s+\S+")
_BAB = re.compile(r"^(bab|bagian|chapter|unit|modul)\b", re.IGNORECASE)
_WORD = re.compile(r"[a-zA-Z0-9]{4,}")


@dataclass
class Section:
    title: str
    document: str
    page_start: int
    page_end: int
    rows: list = field(default_factory=list)


def _is_heading(text: str) -> bool:
    head = text.strip().split("\n")[0][:90].strip()
    if not head or len(head) > 80:
        return False
    if _NUMBERED.match(head) or _BAB.match(head):
        return True
    if head.isupper() and len(head.split()) <= 10 and not head.endswith("."):
        return True
    return False


def build_tree(rows: list[dict]) -> list[Section]:
    """Group chunk rows into sections. Rows need document_name/page_number/content."""
    sections: list[Section] = []
    current: Section | None = None
    for row in sorted(rows, key=lambda r: (str(r["document_name"]), int(r["page_number"]))):
        content = str(row["content"])
        if _is_heading(content) or current is None or current.document != str(row["document_name"]):
            current = Section(
                title=content.strip().split("\n")[0][:90] or "Bagian",
                document=str(row["document_name"]),
                page_start=int(row["page_number"]),
                page_end=int(row["page_number"]),
            )
            sections.append(current)
        current.page_end = int(row["page_number"])
        current.rows.append(row)
    return sections


def _tokens(text: str) -> set[str]:
    return set(match.group(0).lower() for match in _WORD.finditer(text))


def pick_sections(sections: list[Section], query: str, limit: int = 3) -> list[Section]:
    wanted = _tokens(query)
    if not wanted:
        return sections[:limit]
    scored: list[tuple[float, Section]] = []
    for section in sections:
        title_hits = len(_tokens(section.title) & wanted)
        body = " ".join(str(row["content"])[:400] for row in section.rows[:3])
        body_hits = len(_tokens(body) & wanted)
        scored.append((title_hits * 3.0 + body_hits, section))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [section for score, section in scored[:limit] if score > 0] or sections[:1]


async def retrieve_with_tree(database, settings, subject_code: str, query: str):
    """Tree-guided chunks for a subject. Mirrors embedding-model guards."""
    embedding_model = settings.embedding_model
    if not embedding_model:
        raise ValueError("MODEL_EMBEDDING belum diisi di .env.")
    indexed = await database.get_embedding_models_for_subject(subject_code)
    if embedding_model not in indexed:
        raise ValueError(
            "MODEL_EMBEDDING berbeda dari model saat PDF diindeks. Gunakan model lama atau unggah ulang PDF."
        )
    rows = await database.list_chunks_for_subject(subject_code, embedding_model)
    if not rows:
        return []
    sections = build_tree([dict(row) for row in rows])
    top_k = max(1, getattr(settings, "rag_top_k", 5))
    chunks: list[RetrievedChunk] = []
    for section in pick_sections(sections, query):
        for row in section.rows:
            chunks.append(
                RetrievedChunk(
                    chunk_id=str(row["chunk_id"]),
                    subject_code=subject_code,
                    document_name=str(row["document_name"]),
                    page_number=int(row["page_number"]),
                    content=str(row["content"]),
                    score=0.9,
                )
            )
            if len(chunks) >= top_k:
                return chunks
    return chunks
