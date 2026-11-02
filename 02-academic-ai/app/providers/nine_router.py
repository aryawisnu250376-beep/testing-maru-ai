from __future__ import annotations

from app.providers.openai_compat import OpenAICompatProvider


class NineRouterProvider(OpenAICompatProvider):
    """OpenAI-compatible provider adapter for a local 9Router instance.

    The default base URL is supplied by Settings and follows 9Router's documented
    local OpenAI-compatible endpoint. Model identifiers are always supplied by config.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        timeout_seconds: float = 90.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key.strip():
            raise ValueError("NINE_ROUTER_API_KEY belum diisi di .env.")
        super().__init__(
            api_key,
            base_url,
            label="9Router",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
