from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class AIProvider(Protocol):
    async def chat(
        self,
        model: str,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str: ...

    async def embed(self, model: str, texts: Sequence[str]) -> list[list[float]]: ...

    async def transcribe(
        self,
        model: str,
        audio_bytes: bytes,
        filename: str,
        *,
        content_type: str = "audio/webm",
        language: str = "auto",
    ) -> str: ...

    async def list_models(self) -> list[str]: ...

    async def list_embedding_models(self) -> list[str]: ...

    async def close(self) -> None: ...
