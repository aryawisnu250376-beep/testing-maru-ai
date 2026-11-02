from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.diagnostics import check_live_models
from app.providers.nine_router import NineRouterProvider
from app.providers.openai_compat import OpenAICompatProvider
from app.providers.router import ProviderRouter, build_manager_provider, build_provider


class FakeEndpoint:
    """Minimal AIProvider double that records which role handled each call."""

    def __init__(
        self,
        base_url: str,
        model_ids: list[str] | None = None,
        embedding_ids: list[str] | None = None,
    ) -> None:
        self.base_url = base_url
        self.model_ids = model_ids or ["chat-model"]
        self.embedding_ids = embedding_ids or ["embed-model"]
        self.calls: list[str] = []
        self.closed = 0

    async def chat(self, model, messages, **kwargs):
        self.calls.append(f"chat:{model}")
        return f"chat-ok:{model}"

    async def embed(self, model, texts):
        self.calls.append(f"embed:{model}")
        return [[0.1, 0.2] for _ in texts]

    async def transcribe(self, model, audio_bytes, filename, **kwargs):
        self.calls.append(f"transcribe:{model}")
        return "transcript-ok"

    async def list_models(self):
        self.calls.append("list_models")
        return list(self.model_ids)

    async def list_embedding_models(self):
        self.calls.append("list_embedding_models")
        return list(self.embedding_ids)

    async def close(self):
        self.closed += 1


def _settings(**overrides):
    values = {
        "nine_router_api_key": "router-key",
        "nine_router_base_url": "http://localhost:20128/v1",
        "nine_router_timeout_seconds": 90.0,
        "nine_router_max_retries": 0,
        "chat_base_url": "http://localhost:20128/v1",
        "chat_api_key": "router-key",
        "manager_chat_base_url": "",
        "manager_chat_api_key": "",
        "embedding_base_url": "http://localhost:20128/v1",
        "embedding_api_key": "router-key",
        "stt_base_url": "http://localhost:20128/v1",
        "stt_api_key": "router-key",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_build_provider_returns_single_nine_router_by_default() -> None:
    provider = build_provider(_settings())
    assert isinstance(provider, NineRouterProvider)
    assert not isinstance(provider, ProviderRouter)
    assert provider.base_url == "http://localhost:20128/v1"
    asyncio.run(provider.close())


def test_build_provider_routes_chat_to_ollama_while_embedding_stays() -> None:
    provider = build_provider(
        _settings(chat_base_url="http://localhost:11434/v1", chat_api_key="ollama")
    )
    assert isinstance(provider, ProviderRouter)
    assert provider.describe_endpoints() == {
        "chat": "http://localhost:11434/v1",
        "embedding": "http://localhost:20128/v1",
        "stt": "http://localhost:20128/v1",
    }
    asyncio.run(provider.close())


def test_manager_override_uses_ollama_without_changing_specialist_provider() -> None:
    settings = _settings(
        manager_chat_base_url="http://localhost:11434/v1",
        manager_chat_api_key="ollama",
    )
    specialist_provider = build_provider(settings)
    manager_provider = build_manager_provider(settings, specialist_provider)

    assert isinstance(specialist_provider, NineRouterProvider)
    assert specialist_provider.base_url == "http://localhost:20128/v1"
    assert isinstance(manager_provider, OpenAICompatProvider)
    assert manager_provider.base_url == "http://localhost:11434/v1"
    assert manager_provider is not specialist_provider
    asyncio.run(specialist_provider.close())
    asyncio.run(manager_provider.close())


def test_manager_without_override_reuses_default_provider() -> None:
    settings = _settings()
    provider = build_provider(settings)
    assert build_manager_provider(settings, provider) is provider
    asyncio.run(provider.close())


def test_router_delegates_each_operation_to_its_role() -> None:
    chat = FakeEndpoint("http://chat/v1")
    embedding = FakeEndpoint("http://emb/v1")
    stt = FakeEndpoint("http://stt/v1")
    router = ProviderRouter(chat=chat, embedding=embedding, transcribe=stt)

    async def run():
        assert await router.chat("m", []) == "chat-ok:m"
        assert await router.embed("e", ["x"]) == [[0.1, 0.2]]
        assert await router.transcribe("s", b"a", "f.webm") == "transcript-ok"
        assert await router.list_models() == ["chat-model"]
        assert await router.list_embedding_models() == ["embed-model"]
        await router.close()

    asyncio.run(run())
    assert chat.calls == ["chat:m", "list_models"]
    assert embedding.calls == ["embed:e", "list_embedding_models"]
    assert stt.calls == ["transcribe:s"]
    assert (chat.closed, embedding.closed, stt.closed) == (1, 1, 1)


def test_live_check_uses_manager_catalog_separately_from_specialist_catalog(capsys) -> None:
    settings = SimpleNamespace(
        manager_model="hermes3:latest",
        subjects={"PP": object()},
        models={
            "subjects": {"PP": {"agent_a": "kr/claude-haiku-4.5", "agent_b": "kr/glm-5"}},
            "fallbacks": {},
        },
        embedding_model="gemini/text-embedding-005",
        chat_base_url="http://localhost:20128/v1",
        manager_chat_base_url="http://localhost:11434/v1",
        embedding_base_url="http://localhost:20128/v1",
        fallback_models_for=lambda _role: [],
    )
    specialist_provider = FakeEndpoint(
        "http://localhost:20128/v1",
        model_ids=["kr/claude-haiku-4.5", "kr/glm-5"],
        embedding_ids=["gemini/text-embedding-005"],
    )
    manager_provider = FakeEndpoint("http://localhost:11434/v1", model_ids=["hermes3:latest"])

    status = asyncio.run(check_live_models(settings, specialist_provider, manager_provider))
    output = capsys.readouterr().out

    assert status == 0
    assert "Katalog chat spesialis : http://localhost:20128/v1" in output
    assert "Katalog chat Manager   : http://localhost:11434/v1" in output
    assert "OK         Manager: hermes3:latest" in output
    assert "OK         PP Agent A: kr/claude-haiku-4.5" in output
    assert "OK         PP Agent B: kr/glm-5" in output
    assert specialist_provider.calls == ["list_models", "list_embedding_models"]
    assert manager_provider.calls == ["list_models"]


def test_router_shares_and_closes_shared_provider_once() -> None:
    shared = FakeEndpoint("http://shared/v1")
    router = ProviderRouter(chat=shared, embedding=shared, transcribe=shared)
    asyncio.run(router.close())
    assert shared.closed == 1


def test_embedding_catalog_falls_back_to_generic_model_list() -> None:
    class FailingCatalogClient:
        async def get(self, *args, **kwargs):
            raise RuntimeError("404 from plain OpenAI server")

        async def list_models(self):
            return ["nomic-embed-text", "hermes3"]

    provider = OpenAICompatProvider.__new__(OpenAICompatProvider)
    provider.label = "Chat"
    provider._max_retries = 0

    async def fake_models_list():
        return SimpleNamespace(data=[SimpleNamespace(id="nomic-embed-text")])

    provider._client = SimpleNamespace(
        get=FailingCatalogClient().get,
        models=SimpleNamespace(list=fake_models_list),
    )
    assert asyncio.run(provider.list_embedding_models()) == ["nomic-embed-text"]


def test_embedding_catalog_errors_propagate_when_endpoint_down() -> None:
    async def failing(*args, **kwargs):
        raise ConnectionError("endpoint down")

    provider = OpenAICompatProvider.__new__(OpenAICompatProvider)
    provider.label = "Chat"
    provider._max_retries = 0
    provider._client = SimpleNamespace(get=failing, models=SimpleNamespace(list=failing))
    try:
        asyncio.run(provider.list_embedding_models())
    except ConnectionError:
        return
    raise AssertionError("expected the real connection error to propagate")
