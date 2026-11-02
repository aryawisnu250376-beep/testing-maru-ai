"""Headroom-style context shaping: dedupe, budget, rolling history. Lossless-safe."""

from __future__ import annotations

import dataclasses
from typing import Any


def _with_content(chunk, content: str):
    if content == getattr(chunk, "content", None):
        return chunk
    try:
        return dataclasses.replace(chunk, content=content)
    except Exception:
        chunk.content = content
        return chunk


def compress_chunks(chunks: list, max_chars: int) -> tuple[list, dict[str, int]]:
    """Dedupe by chunk_id, normalize whitespace, drop whole chunks past budget."""
    seen: set[str] = set()
    kept: list = []
    used, dropped = 0, 0
    for chunk in chunks:
        key = getattr(chunk, "chunk_id", None) or str(len(seen))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        content = " ".join(str(getattr(chunk, "content", "")).split())
        if used + len(content) > max_chars and kept:
            dropped += 1
            continue
        kept.append(_with_content(chunk, content))
        used += len(content)
    return kept, {"kept": len(kept), "dropped": dropped, "chars": used}


def rolling_history(history: list[dict[str, Any]], max_items: int = 12) -> list[dict[str, Any]]:
    """Keep the opening user message (topic anchor) + the most recent turns."""
    clean = [item for item in history if str(item.get("content", "")).strip()]
    if len(clean) <= max_items:
        return clean
    first_user = next((item for item in clean if item.get("role") == "user"), None)
    tail = clean[-(max_items - 1) :]
    if first_user is not None and first_user not in tail:
        return [first_user, *tail]
    return clean[-max_items:]


def estimate_saved(before_chars: int, after_chars: int) -> dict[str, Any]:
    saved = max(0, before_chars - after_chars)
    return {
        "before_chars": before_chars,
        "after_chars": after_chars,
        "saved_chars": saved,
        "saved_pct": round(100.0 * saved / max(1, before_chars), 1),
    }
