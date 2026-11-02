"""Skill Hermes versi mandiri: ringkas-modul, naskah-video, cek-mutu, usul-jadwal.

Jika 9Router tersedia, skill memakai model lewat router9. Jika tidak, fallback
deterministik tetap berfungsi dan diberi label jujur. Skill tidak pernah mengubah
status persetujuan dan tidak memanggil Ootto.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import router9

TZ = ZoneInfo("Asia/Jakarta")
MAX_REVISION_ROUNDS = 2


def _read_pages(path: Path) -> list[dict]:
    """Baca PDF per halaman atau teks biasa. PDF scan butuh OCR tambahan."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf belum terpasang; pip install pypdf") from exc
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or "").strip()
            pages.append({"page": i, "text": text})
        return pages
    if suffix in (".md", ".txt", ".markdown"):
        text = path.read_text(encoding="utf-8")
        return [{"page": 1, "text": text}]
    # MarkItDown opsional untuk docx/pptx/xlsx/html
    try:
        from markitdown import MarkItDown
        result = MarkItDown().convert(str(path))
        return [{"page": 1, "text": result.text_content}]
    except ImportError as exc:
        raise RuntimeError(f"Format {suffix} butuh MarkItDown; pip install markitdown") from exc


def ringkas_modul(path: str | Path, max_points: int = 8) -> dict:
    path = Path(path)
    pages = _read_pages(path)
    if not any(p["text"] for p in pages):
        raise ValueError("Dokumen kosong atau PDF scan tanpa OCR")
    cfg = router9.RouterConfig.from_env()
    if cfg.configured:
        try:
            joined = "\n\n".join(f"[Halaman {p['page']}]\n{p['text'][:6000]}" for p in pages[:20])
            answer = router9.chat([
                {"role": "system", "content": "Ringkas bahan kuliah dalam Bahasa Indonesia. Setiap poin wajib menyebut nomor halaman sumber, format [hal. N]. Jangan menambah fakta di luar bahan."},
                {"role": "user", "content": joined[:24000]},
            ], cfg, max_tokens=1200)
            points = [ln.strip() for ln in answer.splitlines() if ln.strip()]
            return {"ok": True, "generator": "9router", "points": points[:max_points], "pages": len(pages)}
        except Exception:
            pass  # fallback jujur di bawah
    points = []
    for p in pages:
        sentences = re.split(r"(?<=[.!?])\s+", p["text"])
        for s in sentences[:2]:
            s = s.strip()
            if len(s.split()) >= 5:
                points.append(f"{s} [hal. {p['page']}]")
            if len(points) >= max_points:
                break
        if len(points) >= max_points:
            break
    return {"ok": bool(points), "generator": "fallback-extractive", "points": points, "pages": len(pages)}


def naskah_video(summary: dict, topic: str = "") -> dict:
    points = summary.get("points") or []
    if not points:
        raise ValueError("Ringkasan kosong")
    cfg = router9.RouterConfig.from_env()
    if cfg.configured:
        try:
            answer = router9.chat([
                {"role": "system", "content": "Buat naskah video edukasi 30-60 detik dari ringkasan. JSON: {\"hook\",\"beats\":[{\"narration\",\"source_page\"}],\"caption\"}. Maksimal 130 kata narasi. Jangan menambah klaim tanpa sumber."},
                {"role": "user", "content": json.dumps({"topik": topic, "ringkasan": points}, ensure_ascii=False)},
            ], cfg, max_tokens=1200)
            data = json.loads(re.search(r"\{.*\}", answer, re.S).group(0))
            if data.get("beats"):
                return {"ok": True, "generator": "9router", **data}
        except Exception:
            pass
    hook = topic or "Satu hal dari bahan kuliah ini"
    beats = [{"narration": p, "source_page": _page_of(p)} for p in points[:5]]
    caption = hook + "\n\nSumber: bahan kuliah terlampir. #AI #Edukasi"
    return {"ok": True, "generator": "fallback-template", "hook": hook, "beats": beats, "caption": caption}


def _page_of(text: str) -> int | None:
    m = re.search(r"\[hal\.?\s*(\d+)\]", text)
    return int(m.group(1)) if m else None


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def cek_mutu(script: dict, source_text: str) -> dict:
    """Tandai kalimat yang tidak punya dasar sumber. Bukan fact-check sempurna."""
    source_tokens = _tokens(source_text)
    flagged = []
    beats = script.get("beats") or []
    for i, beat in enumerate(beats):
        narration = beat.get("narration", "")
        toks = _tokens(narration)
        if not toks:
            continue
        overlap = len(toks & source_tokens) / max(1, len(toks))
        if overlap < 0.35:
            flagged.append({"beat": i, "text": narration, "reason": "Kata kunci tidak ditemukan di sumber", "overlap": round(overlap, 2)})
    return {"ok": not flagged, "flagged": flagged, "needs_human": bool(flagged),
            "note": "Pemeriksaan berbasis kemiripan kata, bukan bukti kebenaran mutlak."}


def usul_jadwal(now: datetime | None = None) -> dict:
    now = now or datetime.now(TZ)
    candidate = now.replace(hour=19, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return {"waktu": candidate.isoformat(timespec="seconds"),
            "alasan": "Usulan awal jam istirahat malam; belum didasarkan pada analitik akun. Pemilik boleh mengubah."}


def run_pipeline(path: str | Path, topic: str = "") -> dict:
    """Jalankan skill berurutan, maksimal 2 putaran revisi otomatis."""
    path = Path(path)
    summary = ringkas_modul(path)
    source_text = "\n".join(p["text"] for p in _read_pages(path))
    script = naskah_video(summary, topic)
    rounds = 0
    qc = cek_mutu(script, source_text)
    while not qc["ok"] and rounds < MAX_REVISION_ROUNDS:
        rounds += 1
        # Revisi sederhana: buang beat yang tidak didukung, bukan mengarang baru.
        flagged_idx = {f["beat"] for f in qc["flagged"]}
        script["beats"] = [b for i, b in enumerate(script.get("beats", [])) if i not in flagged_idx]
        script["revised"] = True
        qc = cek_mutu(script, source_text)
    schedule = usul_jadwal()
    return {"summary": summary, "script": script, "qc": qc, "schedule": schedule,
            "revision_rounds": rounds, "needs_human": qc["needs_human"] or not script.get("beats")}
