"""Web fetch: Scrapling when installed, httpx fallback. Powers /web (no API key)."""

from __future__ import annotations

import asyncio
import html as html_lib
import logging
import re
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

_TAG = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.DOTALL)
_DDG = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)


def _scrapling_get(url: str, timeout: int) -> str | None:
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError:
        return None
    try:
        page = StealthyFetcher().get(url, timeout=timeout * 1000)
    except Exception as exc:
        logger.warning("[WARN] Scrapling gagal (%s); fallback httpx.", type(exc).__name__)
        return None
    status = getattr(page, "status", getattr(page, "status_code", 0))
    body = getattr(page, "body", None)
    if body is None:
        body = getattr(page, "text", "")
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    if status != 200 or not body:
        return None
    return body


def download_html(url: str, timeout: int = 20) -> str:
    body = _scrapling_get(url, timeout)
    if body is not None:
        return body
    try:
        response = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "AcademicAI/2 (study bot)"},
        )
        response.raise_for_status()
        return response.text
    except Exception as exc:
        raise ValueError(f"Gagal mengunduh halaman: {exc}") from exc


def html_to_text(body: str, limit: int = 6000) -> str:
    text = _TAG.sub(" ", body)
    text = html_lib.unescape(text)
    return " ".join(text.split())[:limit]


def fetch_text(url: str, timeout: int = 20) -> str:
    return html_to_text(download_html(url, timeout))


def duckduckgo_links(query: str, limit: int = 3) -> list[tuple[str, str]]:
    """Top web hits via DuckDuckGo HTML (no key). Returns (title, url)."""
    body = download_html(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}")
    hits: list[tuple[str, str]] = []
    for href, raw_title in _DDG.findall(body):
        title = " ".join(html_lib.unescape(re.sub(r"<[^>]+>", "", raw_title)).split())
        href = href.strip()
        if href.startswith("//"):
            href = "https:" + href
        if href.startswith("http") and title and (title, href) not in hits:
            hits.append((title[:120], href))
        if len(hits) >= limit:
            break
    return hits


async def summarize_web(manager, query: str):
    """Top DDG hit -> fetch -> summary labeled as a web source."""
    query = (query or "").strip()
    if not query:
        raise ValueError("Kata kunci web kosong.")
    hits = await asyncio.to_thread(duckduckgo_links, query, 3)
    if not hits:
        raise ValueError("Tidak ada hasil web untuk kata kunci ini.")
    last_error: ValueError | None = None
    for title, url in hits:
        try:
            text = await asyncio.to_thread(fetch_text, url)
        except ValueError as exc:
            last_error = exc
            continue
        if len(text) < 200:
            continue
        return await manager.summarize_source_text(
            source_text=text, source_name=f"[web] {title}", source_url=url
        )
    raise last_error or ValueError("Isi halaman web terlalu pendek.")
