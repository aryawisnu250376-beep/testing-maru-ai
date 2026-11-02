from __future__ import annotations

from app.providers.base import AIProvider


class EmbeddingService:
    """Create embeddings through the configured 9Router-compatible provider."""

    def __init__(
        self,
        provider: AIProvider,
        model: str,
        *,
        batch_size: int = 32,
    ) -> None:
        self.provider = provider
        self.model = model.strip()
        self.batch_size = max(1, batch_size)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self.model:
            raise ValueError(
                "MODEL_EMBEDDING belum diisi. Pilih model embeddings yang tersedia di 9Router."
            )
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors = await self.provider.embed(self.model, batch)
            if len(vectors) != len(batch):
                raise RuntimeError("Jumlah embedding dari 9Router tidak sesuai jumlah teks.")
            all_vectors.extend(vectors)

        expected_dimensions = len(all_vectors[0]) if all_vectors else 0
        if expected_dimensions == 0 or any(
            len(vector) != expected_dimensions for vector in all_vectors
        ):
            raise RuntimeError("Dimensi embedding kosong atau tidak konsisten.")
        return all_vectors

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        if not vectors:
            raise RuntimeError("9Router tidak mengembalikan embedding untuk pertanyaan.")
        return vectors[0]
