from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any, TypeVar

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    RateLimitError,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


class OpenAICompatProvider:
    """Generic OpenAI-compatible chat/embedding/STT client.

    Works with 9Router, Ollama (``/v1``), vLLM, LM Studio, OpenRouter, or any
    other endpoint that speaks the OpenAI REST dialect. ``label`` only affects
    log messages. ``api_key`` may be empty for local endpoints that ignore it
    (Ollama); a placeholder is substituted because the SDK requires a value.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        label: str = "AI",
        timeout_seconds: float = 90.0,
        max_retries: int = 3,
    ) -> None:
        if not base_url.strip():
            raise ValueError(f"{label}: base URL belum diisi di .env.")
        self.base_url = base_url.rstrip("/")
        self.label = label
        self._client = AsyncOpenAI(
            api_key=api_key.strip() or "not-needed-for-local-endpoint",
            base_url=self.base_url,
            timeout=max(5.0, min(300.0, timeout_seconds)),
            max_retries=0,
        )
        self._max_retries = max(0, max_retries)

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        if isinstance(error, (APIConnectionError, RateLimitError)):
            return True
        if isinstance(error, APIStatusError):
            return error.status_code >= 500
        return False

    async def _with_retries(self, operation: str, request: Any) -> Any:
        for attempt in range(self._max_retries + 1):
            try:
                return await request()
            except Exception as error:
                if attempt >= self._max_retries or not self._is_retryable(error):
                    raise
                delay_seconds = 0.8 * (2**attempt)
                logger.warning(
                    "[WARN] %s %s gagal sementara; retry %s/%s dalam %.1f detik (%s)",
                    getattr(self, "label", "AI"),
                    operation,
                    attempt + 1,
                    self._max_retries,
                    delay_seconds,
                    type(error).__name__,
                )
                await asyncio.sleep(delay_seconds)
        raise RuntimeError("Retry loop berakhir tanpa hasil.")

    async def chat(
        self,
        model: str,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        if not model.strip():
            raise ValueError("Model chat belum dikonfigurasi di config/models.yaml dan .env.")

        response = await self._with_retries(
            "chat completion",
            lambda: self._client.chat.completions.create(
                model=model,
                messages=list(messages),
                temperature=temperature,
                max_tokens=max_tokens,
            ),
        )
        content = response.choices[0].message.content
        if isinstance(content, str):
            return content.strip()
        if content is None:
            return ""
        # A few OpenAI-compatible routers return a list of text blocks.
        text_parts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(str(part.get("text", "")))
            else:
                text_value = getattr(part, "text", None)
                if text_value:
                    text_parts.append(str(text_value))
        return "\n".join(part for part in text_parts if part).strip()

    async def embed(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        if not model.strip():
            raise ValueError("MODEL_EMBEDDING belum diisi di .env.")
        if not texts:
            return []

        response = await self._with_retries(
            "embeddings",
            lambda: self._client.embeddings.create(
                model=model,
                input=list(texts),
            ),
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [list(item.embedding) for item in ordered]
        if len(vectors) != len(texts):
            raise RuntimeError(
                f"{self.label} mengembalikan {len(vectors)} embedding untuk {len(texts)} teks."
            )
        return vectors

    async def transcribe(
        self,
        model: str,
        audio_bytes: bytes,
        filename: str,
        *,
        content_type: str = "audio/webm",
        language: str = "auto",
    ) -> str:
        """Send uploaded/recorded audio to an OpenAI-compatible STT endpoint."""
        if not model.strip():
            raise ValueError(
                "MODEL_STT belum diisi. Pilih model STT dari katalog endpoint yang dipakai "
                "(misalnya GET /v1/models/stt pada 9Router)."
            )
        if not audio_bytes:
            raise ValueError("File audio kosong.")

        request_options: dict[str, Any] = {
            "model": model,
            "file": (filename, audio_bytes, content_type),
        }
        if language.strip().lower() not in {"", "auto"}:
            request_options["language"] = language.strip().lower()
        response = await self._with_retries(
            "audio transcription",
            lambda: self._client.audio.transcriptions.create(**request_options),
        )
        if isinstance(response, str):
            return response.strip()
        text = getattr(response, "text", None)
        if text is None and isinstance(response, dict):
            text = response.get("text", "")
        return str(text or "").strip()

    async def list_models(self) -> list[str]:
        response = await self._with_retries("model list", self._client.models.list)
        return [str(item.id) for item in response.data]

    async def list_embedding_models(self) -> list[str]:
        try:
            response = await self._with_retries(
                "embedding model list",
                lambda: self._client.get("/models/embedding", cast_to=httpx.Response),
            )
        except Exception:
            # Plain OpenAI-compatible servers (Ollama, vLLM, ...) do not expose
            # 9Router's dedicated embedding catalog; fall back to the generic
            # model list so diagnostics can still run. If the endpoint itself is
            # down, list_models() below raises the real connection error.
            logger.info(
                "[INFO] %s: katalog /models/embedding tidak tersedia; memakai katalog /models umum.",
                self.label,
            )
            return await self.list_models()
        payload = response.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(data, list):
            raise RuntimeError(
                f"{self.label} mengirim katalog embedding dengan format tidak dikenal."
            )
        return [str(item["id"]) for item in data if isinstance(item, dict) and item.get("id")]

    async def close(self) -> None:
        await self._client.close()
