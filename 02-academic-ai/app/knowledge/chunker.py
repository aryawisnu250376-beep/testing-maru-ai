from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    page_number: int
    chunk_index: int
    content: str


def _split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    if max_chars < 100:
        raise ValueError("max_chars minimal 100 agar potongan materi tetap berguna.")
    overlap_chars = max(0, min(overlap_chars, max_chars // 2))

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start, end)
            if boundary > start + max_chars // 2:
                end = boundary

        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(normalized):
            break

        next_start = max(start + 1, end - overlap_chars)
        # Start the next chunk at a word boundary where possible.
        next_space = normalized.find(" ", next_start, min(next_start + 80, len(normalized)))
        if next_space != -1:
            next_start = next_space + 1
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks


def chunk_pages(
    *,
    document_id: str,
    document_name: str,
    pages: list[tuple[int, str]],
    max_chars: int = 1000,
    overlap_chars: int = 200,
) -> list[TextChunk]:
    """Chunk each PDF page separately so citation page metadata stays exact."""
    del document_name  # Name is stored in DB metadata, not duplicated in the chunk ID.
    chunks: list[TextChunk] = []
    for page_number, page_text in pages:
        page_chunks = _split_text(page_text, max_chars, overlap_chars)
        for chunk_index, content in enumerate(page_chunks):
            chunks.append(
                TextChunk(
                    chunk_id=f"{document_id}:p{page_number}:c{chunk_index}",
                    page_number=page_number,
                    chunk_index=chunk_index,
                    content=content,
                )
            )
    return chunks
