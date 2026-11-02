"""Alat riset opsional: SearXNG, Crawl4AI, MarkItDown, transkrip YouTube.

Semua opsional. Jika tidak terpasang/ tidak dikonfigurasi, fungsi mengembalikan
error yang jujur, bukan mengarang hasil. Patuhi robots.txt & batasi kecepatan.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def searxng_search(query: str, limit: int = 5) -> dict:
    base = os.getenv("SEARXNG_URL", "")
    if not base:
        return {"ok": False, "error": "SEARXNG_URL belum diisi"}
    url = base.rstrip("/") + "/search?" + urllib.parse.urlencode({"q": query, "format": "json"})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NaraStudio/2.1"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        results = [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content")}
                   for x in data.get("results", [])[:limit]]
        return {"ok": True, "results": results}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def crawl_page(url: str) -> dict:
    """Ambil isi halaman jadi Markdown. Crawl4AI opsional; fallback urllib+strip."""
    try:
        from crawl4ai import AsyncWebCrawler  # type: ignore
        import asyncio

        async def _run():
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url)
                return result.markdown or ""
        md = asyncio.run(_run())
        return {"ok": bool(md), "markdown": md, "engine": "crawl4ai"}
    except ImportError:
        pass
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    # fallback sederhana
    try:
        import re
        req = urllib.request.Request(url, headers={"User-Agent": "NaraStudio/2.1"})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode(errors="ignore")
        text = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {"ok": True, "markdown": text[:20000], "engine": "urllib-strip"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def read_document(path: str) -> dict:
    """MarkItDown untuk docx/pptx/xlsx/html; pypdf untuk PDF."""
    from pathlib import Path
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        from .skills4 import _read_pages
        pages = _read_pages(p)
        return {"ok": True, "markdown": "\n\n".join(f"[hal. {x['page']}]\n{x['text']}" for x in pages)}
    try:
        from markitdown import MarkItDown
        result = MarkItDown().convert(str(p))
        return {"ok": True, "markdown": result.text_content}
    except ImportError:
        if p.suffix.lower() in (".md", ".txt"):
            return {"ok": True, "markdown": p.read_text(encoding="utf-8")}
        return {"ok": False, "error": "MarkItDown belum terpasang; pip install markitdown"}


def youtube_transcript(video_id: str) -> dict:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["id", "en"])
        text = " ".join(snippet.text for snippet in fetched)
        return {"ok": True, "text": text}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def sumber_md(content_id: str, sources: list[dict]) -> str:
    """Simpan sumber per konten agar pemilik bisa memeriksa sebelum menyetujui."""
    from .config import ROOT
    from . import queue4
    d = ROOT / "antrean" / content_id
    d.mkdir(parents=True, exist_ok=True)
    lines = [f"# Sumber — {content_id}", f"Diakses: {queue4.now()}", ""]
    for s in sources:
        lines.append(f"- {s.get('title','')} — {s.get('url','')} (diakses {s.get('accessed', queue4.now())})")
    path = d / "sumber.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)
