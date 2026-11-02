from __future__ import annotations

from collections.abc import Sequence

from app.providers.base import AIProvider
from app.providers.nine_router import NineRouterProvider
from app.providers.openai_compat import OpenAICompatProvider


class ProviderRouter:
    """Route each AI operation to its configured endpoint.

    Default setup sends everything to 9Router (a single provider, unchanged
    behavior). When the CHAT_/EMBEDDING_/STT_ endpoint overrides differ, chat
    can run on a local model such as Hermes via Ollama while embeddings and
    speech-to-text stay on 9Router or another endpoint.
    """

    def __init__(
        self,
        *,
        chat: AIProvider,
        embedding: AIProvider | None = None,
        transcribe: AIProvider | None = None,
    ) -> None:
        self._chat = chat
        self._embedding = embedding or chat
        self._transcribe = transcribe or chat

    @property
    def base_url(self) -> str:
        """Primary (chat) endpoint, for log messages."""
        return str(getattr(self._chat, "base_url", "?"))

    def describe_endpoints(self) -> dict[str, str]:
        return {
            "chat": str(getattr(self._chat, "base_url", "?")),
            "embedding": str(getattr(self._embedding, "base_url", "?")),
            "stt": str(getattr(self._transcribe, "base_url", "?")),
        }

    async def chat(
        self,
        model: str,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        return await self._chat.chat(
            model, messages, temperature=temperature, max_tokens=max_tokens
        )

    async def embed(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        return await self._embedding.embed(model, texts)

    async def transcribe(
        self,
        model: str,
        audio_bytes: bytes,
        filename: str,
        *,
        content_type: str = "audio/webm",
        language: str = "auto",
    ) -> str:
        return await self._transcribe.transcribe(
            model,
            audio_bytes,
            filename,
            content_type=content_type,
            language=language,
        )

    async def list_models(self) -> list[str]:
        """List chat models from the chat endpoint catalog."""
        return await self._chat.list_models()

    async def list_embedding_models(self) -> list[str]:
        """List embedding models from the embedding endpoint catalog."""
        return await self._embedding.list_embedding_models()

    async def close(self) -> None:
        seen: set[int] = set()
        for provider in (self._chat, self._embedding, self._transcribe):
            if id(provider) in seen:
                continue
            seen.add(id(provider))
            await provider.close()


def build_provider(settings) -> AIProvider:
    """Build a single provider (default) or a router (custom endpoints).

    When CHAT_/EMBEDDING_/STT_ overrides are empty, every role uses
    NINE_ROUTER_BASE_URL and this returns one NineRouterProvider, exactly like
    before. Otherwise per-role OpenAI-compatible providers are created and
    wrapped in a ProviderRouter (or returned directly when all roles share one
    custom endpoint).
    """
    nine_url = settings.nine_router_base_url.rstrip("/")
    nine_key = settings.nine_router_api_key
    timeout = settings.nine_router_timeout_seconds
    retries = settings.nine_router_max_retries

    chat_url = (getattr(settings, "chat_base_url", "") or nine_url).rstrip("/")
    chat_key = getattr(settings, "chat_api_key", "") or ""
    embedding_url = (getattr(settings, "embedding_base_url", "") or nine_url).rstrip("/")
    embedding_key = getattr(settings, "embedding_api_key", "") or ""
    stt_url = (getattr(settings, "stt_base_url", "") or nine_url).rstrip("/")
    stt_key = getattr(settings, "stt_api_key", "") or ""

    def _make(label: str, url: str, key: str) -> AIProvider:
        if url == nine_url and key == nine_key:
            return NineRouterProvider(
                api_key=key,
                base_url=url,
                timeout_seconds=timeout,
                max_retries=retries,
            )
        return OpenAICompatProvider(
            api_key=key,
            base_url=url,
            label=label,
            timeout_seconds=timeout,
            max_retries=retries,
        )

    chat = _make("Chat", chat_url, chat_key or nine_key)
    embedding = (
        chat
        if (embedding_url, embedding_key or nine_key) == (chat_url, chat_key or nine_key)
        else _make("Embedding", embedding_url, embedding_key or nine_key)
    )
    transcribe = (
        chat
        if (stt_url, stt_key or nine_key) == (chat_url, chat_key or nine_key)
        else _make("STT", stt_url, stt_key or nine_key)
    )
    if embedding is chat and transcribe is chat:
        return chat
    return ProviderRouter(chat=chat, embedding=embedding, transcribe=transcribe)


def build_manager_provider(settings, default_provider: AIProvider | None = None) -> AIProvider:
    """Build the Manager-only chat client.

    With no MANAGER_CHAT_* override, Manager follows the existing chat provider,
    preserving the old one-endpoint behavior. When an override is set (for
    example Ollama/Hermes), only calls explicitly made through this provider use
    that endpoint; specialist agents continue using ``default_provider``.
    """
    base_url = str(getattr(settings, "manager_chat_base_url", "") or "").strip().rstrip("/")
    if not base_url:
        return default_provider if default_provider is not None else build_provider(settings)

    router_url = str(getattr(settings, "nine_router_base_url", "") or "").strip().rstrip("/")
    router_key = str(getattr(settings, "nine_router_api_key", "") or "").strip()
    chat_url = str(getattr(settings, "chat_base_url", "") or router_url).strip().rstrip("/")
    chat_key = str(getattr(settings, "chat_api_key", "") or "").strip()
    api_key = str(getattr(settings, "manager_chat_api_key", "") or "").strip()

    if not api_key:
        if base_url == router_url:
            api_key = router_key
        elif base_url == chat_url:
            api_key = chat_key or router_key

    timeout = float(getattr(settings, "nine_router_timeout_seconds", 90.0))
    retries = int(getattr(settings, "nine_router_max_retries", 3))
    if base_url == router_url:
        return NineRouterProvider(
            api_key=api_key or router_key,
            base_url=base_url,
            timeout_seconds=timeout,
            max_retries=retries,
        )
    return OpenAICompatProvider(
        api_key=api_key,
        base_url=base_url,
        label="AI Manager",
        timeout_seconds=timeout,
        max_retries=retries,
    )
