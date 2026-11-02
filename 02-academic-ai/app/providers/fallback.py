from __future__ import annotations

import logging
from collections.abc import Sequence

from app.providers.base import AIProvider

logger = logging.getLogger(__name__)


async def chat_with_fallback(
    provider: AIProvider,
    model_ids: Sequence[str],
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    role_label: str,
) -> tuple[str, str]:
    """Try configured model IDs in order; the provider itself handles retries/backoff."""
    last_error: Exception | None = None
    unique_models = list(dict.fromkeys(model.strip() for model in model_ids if model.strip()))
    if not unique_models:
        raise ValueError(f"Belum ada model yang dikonfigurasi untuk {role_label}.")

    for index, model_id in enumerate(unique_models):
        try:
            text = await provider.chat(
                model_id,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if not text.strip():
                raise ValueError("Model mengirim output kosong.")
            return text, model_id
        except Exception as exc:
            last_error = exc
            if index < len(unique_models) - 1:
                logger.warning(
                    "[WARN] %s model gagal (%s); mencoba model fallback berikutnya.",
                    role_label,
                    type(exc).__name__,
                )
    raise RuntimeError(
        f"Semua model yang dikonfigurasi untuk {role_label} gagal ({type(last_error).__name__ if last_error else 'unknown'})."
    ) from last_error
