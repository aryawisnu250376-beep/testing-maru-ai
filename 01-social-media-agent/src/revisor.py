"""REVISI terarah — kolom revisi untuk tiap aspek script, lalu ACC.

Kenapa per-aspek, bukan satu tombol "edit":
  Instruksi bebas seperti "edit: lebih menarik" menghasilkan perubahan acak.
  Instruksi terarah ("hook terlalu panjang", "analogi kurang relatable") hanya
  menyentuh satu bagian dan tidak merusak bagian yang sudah bagus.

Aspek yang bisa direvisi:
  hook       kalimat pembuka
  body       teks yang tampil di layar per beat
  narration  yang diucapkan narator
  visual     tipe & isi visual per beat
  length     total durasi (tambah/kurangi beat)
  caption    caption + hashtag
  sources    tambah/buang sumber

Setiap revisi dicatat di tabel `revisions` (jejak audit): apa yang diminta,
nilai lama, nilai baru. Jadi kalau hasilnya jelek, bisa ditelusuri.
"""
from __future__ import annotations

import json
import re

from . import db

ASPECTS = {
    "hook": "Kalimat pembuka — apa yang bikin orang berhenti scroll",
    "body": "Teks yang tampil besar di layar",
    "narration": "Yang diucapkan narator",
    "visual": "Tipe visual & isinya",
    "length": "Total durasi / jumlah beat",
    "caption": "Caption TikTok & hashtag",
    "sources": "Sumber yang dirujuk",
}

SHORTCUTS = {
    "hook_lebih_pendek": ("hook", "Pendekkan hook jadi maksimal 8 kata, pertahankan rasa penasaran."),
    "hook_pertanyaan": ("hook", "Ubah hook jadi pertanyaan yang bikin orang merasa wajib tahu jawabannya."),
    "lebih_sederhana": ("narration", "Sederhanakan narasi: hilangkan istilah teknis, pakai bahasa sehari-hari."),
    "tambah_analogi": ("body", "Tambahkan satu analogi kehidupan sehari-hari di beat contoh."),
    "lebih_cepat": ("length", "Kurangi 1 beat terpanjang supaya durasi turun di bawah 45 detik."),
    "batasan_lebih_kuat": ("narration", "Perkuat beat 'limit': sebut satu risiko nyata yang spesifik."),
    "visual_lebih_variatif": ("visual", "Ganti visual beat ke-2 dan ke-3 jadi tipe berbeda (diagram/bars/compare)."),
    "caption_lebih_mengundang": ("caption", "Buat caption yang mengundang jawaban, tambah 1 pertanyaan."),
}


# ---------------------------------------------------------------- revisi

def apply_revision(episode_id: str, aspect: str, instruction: str, cfg: dict,
                   llm=None) -> dict:
    """Revisi satu aspek. Return {ok, before, after, notes}."""
    from . import scriptwriter

    ep = db.get_episode(episode_id)
    if not ep or not ep.get("script"):
        return {"ok": False, "error": "episode/script tidak ditemukan"}
    if aspect not in ASPECTS:
        return {"ok": False, "error": f"aspek tidak dikenal: {aspect}",
                "available": list(ASPECTS)}

    script = json.loads(json.dumps(ep["script"]))  # deep copy
    before = _snapshot(script, aspect)
    notes: list[str] = []

    if llm is None:
        from .llm import LLM

        llm = LLM.from_config(cfg)

    if llm.available:
        try:
            script = _revise_with_llm(script, aspect, instruction, cfg, llm)
            notes.append("direvisi oleh LLM")
        except Exception as e:
            notes.append(f"LLM gagal ({str(e)[:80]}), pakai aturan lokal")
            script = _revise_local(script, aspect, instruction)
    else:
        script = _revise_local(script, aspect, instruction)
        notes.append("tanpa LLM: revisi berbasis aturan")

    # sanitise + validasi ulang.
    # PENTING: sanitize mengambil sources dari `evidence` cluster. Kalau cluster
    # tidak punya evidence (mis. episode lama), sumber asli akan terhapus.
    # Jadi evidence dibangun dari sumber yang sudah ada.
    cluster = dict(ep.get("topic") or {})
    if not cluster.get("evidence"):
        cluster["evidence"] = [
            {"source": (s_ or {}).get("url", "").split("/")[2] if (s_ or {}).get("url") else "ref",
             "title": (s_ or {}).get("title", ""), "url": (s_ or {}).get("url", ""),
             "raw_score": 0, "score": 0.5}
            for s_ in (script.get("sources") or []) if (s_ or {}).get("url")
        ]
    cluster.setdefault("label", script.get("title", ""))
    script, sani_notes = scriptwriter.sanitize(script, cluster, cfg)
    ok, errors, warns = scriptwriter.validate_script(script, cfg)
    notes += sani_notes

    after = _snapshot(script, aspect)
    db.init()
    with db.conn() as c:
        c.execute("INSERT INTO revisions (episode_id, aspect, instruction, old_value, "
                  "new_value, status, created_at) VALUES (?,?,?,?,?,?,?)",
                  (episode_id, aspect, instruction[:400],
                   json.dumps(before, ensure_ascii=False)[:3000],
                   json.dumps(after, ensure_ascii=False)[:3000],
                   "applied" if ok else "invalid", db.now()))
    if ok:
        from . import approve
        approve.invalidate(episode_id, "Revisi " + aspect)
        db.save_episode(episode_id, "pending_approval", ep.get("topic") or {}, script, ep.get("paths"))
    db.log_event(episode_id, "revision", {"aspect": aspect, "instruction": instruction[:200], "applied": ok})

    return {"ok": ok, "aspect": aspect, "before": before, "after": after,
            "errors": errors, "warnings": warns, "notes": notes,
            "script": script}


def _snapshot(script: dict, aspect: str):
    beats = script.get("beats", [])
    if aspect == "hook":
        return {"hook": script.get("hook"), "first": beats[0] if beats else None}
    if aspect == "body":
        return [b.get("body") for b in beats]
    if aspect == "narration":
        return [b.get("narration") for b in beats]
    if aspect == "visual":
        return [b.get("visual") for b in beats]
    if aspect == "length":
        return {"beats": len(beats),
                "words": sum(len(str(b.get("narration", "")).split()) for b in beats)}
    if aspect == "caption":
        return {"caption": script.get("caption"), "hashtags": script.get("hashtags")}
    if aspect == "sources":
        return script.get("sources")
    return None


def _revise_with_llm(script: dict, aspect: str, instruction: str, cfg: dict, llm) -> dict:
    system = ("Kamu editor script video pendek. Kamu HANYA boleh mengubah bagian yang "
              "diminta. Jangan mengubah fakta, sumber, atau beat lain. Jawab JSON utuh.")
    user = f"""ASPEK YANG DIREVISI: {aspect} — {ASPECTS[aspect]}
INSTRUKSI: {instruction}

SCRIPT SEKARANG:
{json.dumps(script, ensure_ascii=False)[:5000]}

Aturan: pertahankan skema JSON yang sama, jumlah sumber, dan beat 'limit'.
Kembalikan JSON script yang sudah direvisi saja."""
    out = llm.chat_json([{"role": "system", "content": system},
                         {"role": "user", "content": user}], tier="strong", temperature=0.5)
    # pertahankan sumber asli (jangan biarkan model mengarang URL)
    out["sources"] = script.get("sources", [])
    return out


_DANGLING = {"yang", "di", "dan", "atau", "untuk", "dari", "ke", "pada", "dengan",
             "karena", "tapi", "kalau", "itu", "ini", "adalah", "akan", "bisa"}


def _clean_shorten(text: str, limit: int, question: bool = False,
                   fallback: str | None = None) -> str:
    """Pendekkan TANPA merusak grammar.

    Urutan usaha:
      1. `fallback` (biasanya headline — memang ditulis pendek & utuh)
      2. kalimat pertama, kalau sudah cukup pendek
      3. klausa pertama (potong di koma), kalau cukup pendek
      4. terakhir: potong kata + rapikan, sadar bahwa hasilnya bisa kurang mulus
    """
    text = str(text or "").strip()
    if not text:
        return text
    words = text.split()
    if len(words) <= limit:
        return text

    if fallback:
        fb = " ".join(str(fallback).split()[:limit]).strip(" .,;:—-")
        if fb:
            return fb + ("?" if question else ".")

    first = re.split(r"(?<=[.!?])\s+", text)[0]
    if len(first.split()) <= limit:
        return first if first.endswith(("?", "!")) else first.rstrip(".") + "."

    clause = text.split(",")[0]
    if 3 <= len(clause.split()) <= limit:
        return clause.rstrip(" .,;:—-") + ("?" if question else ".")

    cut = words[:limit]
    while cut and cut[-1].lower().strip(".,!?") in _DANGLING:
        cut.pop()
    out = " ".join(cut or words[:limit]).rstrip(".,;:!—- ")
    return out + ("?" if question else ".")


def _revise_local(script: dict, aspect: str, instruction: str) -> dict:
    """Revisi deterministik tanpa LLM — cukup untuk instruksi umum."""
    beats = script.get("beats", [])
    low = (instruction or "").lower()

    if aspect == "hook":
        hook = script.get("hook", "")
        if "pendek" in low or "short" in low:
            headline = (script.get("beats") or [{}])[0].get("headline", "")
            script["hook"] = _clean_shorten(hook, 8, question=("tanya" in low),
                                            fallback=headline)
        elif "pertanyaan" in low or "question" in low:
            core = re.sub(r"^(kalau|jadi|dan)\s+", "", hook.lower()).rstrip(".?!")
            script["hook"] = f"Kamu tahu kenapa {core}?"
        else:
            script["hook"] = hook
        if beats:
            beats[0]["narration"] = script["hook"]
            beats[0]["headline"] = " ".join(script["hook"].split()[:5])

    elif aspect == "narration":
        if "sederhana" in low or "simple" in low:
            replacements = {
                "kuantisasi": "pemadatan ukuran", "inferensi": "proses menjawab",
                "parameter": "ukuran model", "distilasi": "peniruan model",
                "benchmark": "uji perbandingan", "latensi": "waktu tunggu",
            }
            for b in beats:
                text = str(b.get("narration", ""))
                for tech, plain in replacements.items():
                    text = re.sub(tech, plain, text, flags=re.I)
                b["narration"] = text
        if "batasan" in low or "risiko" in low:
            for b in beats:
                if b.get("kind") == "limit":
                    b["narration"] = ("Tapi ini bukan tanpa risiko. Kalau dipakai untuk keputusan "
                                      "penting, kesalahannya susah dilacak dan bisa diulang diam-diam.")
                    b["body"] = "Risiko nyata: kesalahan kecil bisa berulang tanpa terlihat."

    elif aspect == "body":
        if "analogi" in low:
            for b in beats:
                if b.get("kind") == "point" and not (b.get("visual") or {}).get("props"):
                    b["body"] = ("Ibarat dapur restoran: bahannya sama, tapi cara memasaknya "
                                 "menentukan hasilnya.")
                    break

    elif aspect == "visual":
        rotation = ["diagram", "steps", "compare", "bars"]
        i = 0
        for b in beats:
            if b.get("kind") in ("hook", "cta"):
                continue
            vtype = rotation[i % len(rotation)]
            props = {
                "diagram": {"nodes": [{"title": "Sebelum", "sub": ""}, {"title": "Sesudah", "sub": ""}]},
                "steps": {"items": [{"title": "Langkah 1"}, {"title": "Langkah 2"}]},
                "compare": {"left": {"title": "Mitos", "items": ["a", "b"]},
                            "right": {"title": "Fakta", "items": ["c", "d"]}},
                "bars": {"items": [{"label": "A", "value": 10}, {"label": "B", "value": 4}]},
            }[vtype]
            b["visual"] = {"type": vtype, "props": props}
            i += 1

    elif aspect == "length":
        if ("pendek" in low or "cepat" in low or "kurang" in low) and len(beats) > 4:
            # buang beat 'point' terpanjang
            points = [(i, b) for i, b in enumerate(beats) if b.get("kind") == "point"]
            if points:
                idx = max(points, key=lambda p: len(str(p[1].get("narration", "")).split()))[0]
                beats.pop(idx)
                script["beats"] = beats

    elif aspect == "caption":
        base = script.get("caption", "")
        if "?" not in base:
            base = base.rstrip(". ") + " — menurut kamu gimana?"
        if "undang" in low or "mengundang" in low:
            base = base.rstrip(". ") + " Tulis pendapatmu di komentar."
        script["caption"] = base[:300]
        tags = set(script.get("hashtags") or [])
        tags.update({"#AI", "#belajarAI"})
        script["hashtags"] = sorted(tags)[:8]

    elif aspect == "sources":
        pass  # sumber tidak boleh dikarang; hanya bisa dikurangi lewat validator manual

    return script


def history(episode_id: str) -> list[dict]:
    db.init()
    with db.conn() as c:
        rows = c.execute("SELECT * FROM revisions WHERE episode_id=? ORDER BY id DESC",
                         (episode_id,)).fetchall()
    return [dict(r) for r in rows]


def pending() -> list[dict]:
    """Semua episode yang menunggu ACC (kolom revisi/ACC di dashboard)."""
    db.init()
    out = []
    for ep in db.list_episodes(status="pending_approval", limit=50):
        script = ep.get("script") or {}
        out.append({
            "episode_id": ep["id"],
            "title": script.get("title", "-"),
            "hook": script.get("hook", ""),
            "beats": len(script.get("beats") or []),
            "generator": script.get("generator", "-"),
            "revisions": len(history(ep["id"])),
            "updated_at": ep["updated_at"],
        })
    return out
