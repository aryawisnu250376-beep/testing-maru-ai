"""AMATI – TIRU – MODIFIKASI, dengan pengaman hak cipta.

Kenyataan yang harus diterima lebih dulu:
  * TikTok **tidak punya API trend publik**. Scraping Creative Center melanggar
    ToS dan cepat diblokir. Jadi "kesadaran trend TikTok" dibangun dari sinyal
    yang legal + analisis referensi yang kamu berikan sendiri.
  * Yang boleh ditiru adalah **pola** (struktur, ritme, jenis hook), bukan
    **karya** (naskah, voice, musik, visual, editing). Ide tidak berhak cipta;
    ekspresi berhak cipta.

Alur tiga langkah:

  1. AMATI   → `fetch_reference(url)` ambil metadata publik (oEmbed, tanpa login)
               + `analyze_reference(text)` pecah jadi struktur (hook, beat, ritme)
  2. TIRU    → `pattern_to_spec(pattern)` ubah pola jadi kerangka script kita
  3. MODIFIKASI → `transform_spec(spec, cluster)` ganti substansi total:
               subjek, contoh, angka, urutan, ditambah konteks & kritik

`compliance_check()` menilai hasil akhir sebelum render. Ini bukan nasihat hukum;
ini daftar periksa supaya kamu tidak menyalin mentah.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; ai-edukasi-agent/1.0)"}


# ---------------------------------------------------------------- 1. AMATI

def fetch_reference(url: str, timeout: int = 15) -> dict:
    """Metadata publik video TikTok/YouTube lewat oEmbed (tanpa login, tanpa scrape)."""
    url = (url or "").strip()
    if not url:
        return {"error": "url kosong"}
    if "tiktok.com" in url:
        api = "https://www.tiktok.com/oembed?url=" + urllib.parse.quote(url, safe="")
        source = "tiktok"
    elif "youtube.com" in url or "youtu.be" in url:
        api = "https://www.youtube.com/oembed?url=" + urllib.parse.quote(url, safe="") + "&format=json"
        source = "youtube"
    else:
        return {"error": "hanya TikTok/YouTube yang didukung untuk analisis referensi"}
    try:
        req = urllib.request.Request(api, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
    except Exception as e:
        return {"error": f"gagal ambil metadata: {str(e)[:150]}", "url": url, "source": source}

    title = data.get("title") or ""
    return {
        "source": source, "url": url,
        "title": title,
        "author": data.get("author_name") or data.get("author_unique_id") or "",
        "thumbnail": data.get("thumbnail_url", ""),
        # oEmbed tidak memberi transkrip/audio: itu harus kamu tempel sendiri
        "needs_transcript": True,
        "note": ("Metadata saja tidak cukup untuk meniru POLA. Tempel transkrip/"
                 "deskripsi videonya (atau ringkasanmu) ke --transcript."),
    }


def analyze_reference(reference: dict, transcript: str = "", cfg: dict | None = None) -> dict:
    """Pecah referensi jadi POLA yang bisa dipakai ulang, bukan karya."""
    text = (transcript or reference.get("title") or "").strip()
    if not text:
        return {"error": "tidak ada teks untuk dianalisis (transkrip kosong)"}

    llm = None
    if cfg:
        from .llm import LLM

        llm = LLM.from_config(cfg)
    if llm and llm.available:
        try:
            return _analyze_with_llm(text, llm)
        except Exception as e:
            print(f"  [warn] analisis LLM gagal ({str(e)[:80]}), pakai heuristik")

    return _analyze_heuristic(text, reference)


def _analyze_with_llm(text: str, llm) -> dict:
    system = ("Kamu analis konten short-form. Tugasmu memecah sebuah video menjadi POLA "
              "struktural (bukan menyalin isinya). Jawab JSON saja.")
    user = f"""Analisis teks video ini. Fokus pada STRUKTUR, bukan isi.

TEKS:
\"\"\"{text[:6000]}\"\"\"

Skema JSON:
{{
 "hook": {{"text": "kalimat pembuka", "type": "pertanyaan|angka|negasi|pernyataan", "words": jumlah_kata}},
 "structure": [{{"beat": 1, "fungsi": "hook|konteks|penjelasan|contoh|batasan|cta",
                  "ringkasan": "1 kalimat"}}],
 "pacing": {{"estimasi_detik": angka, "kata_per_detik": angka}},
 "pattern_name": "nama pola, misal 'salah-paham lalu koreksi'",
 "why_it_works": "1 kalimat psikologis",
 "transplantable": ["elemen pola yang bisa dipakai topik lain"],
 "must_not_copy": ["hal yang TIDAK boleh ditiru: kalimat khas, contoh spesifik, gaya visual"]
}}"""
    out = llm.chat_json([{"role": "system", "content": system},
                         {"role": "user", "content": user}], tier="strong", temperature=0.3)
    out["analyzed_by"] = "llm"
    return out


def _analyze_heuristic(text: str, reference: dict) -> dict:
    words = text.split()
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    hook = sentences[0] if sentences else text[:120]
    hook_type = ("pertanyaan" if hook.rstrip().endswith("?") else
                 "angka" if re.search(r"\d", hook) else
                 "negasi" if re.search(r"\b(bukan|jangan|nggak|tidak)\b", hook.lower()) else
                 "pernyataan")
    est = max(8, len(words) / 2.6)
    return {
        "hook": {"text": hook, "type": hook_type, "words": len(hook.split())},
        "structure": [
            {"beat": 1, "fungsi": "hook", "ringkasan": hook[:100]},
            {"beat": 2, "fungsi": "konteks", "ringkasan": sentences[1][:100] if len(sentences) > 1 else "-"},
            {"beat": 3, "fungsi": "penjelasan", "ringkasan": sentences[2][:100] if len(sentences) > 2 else "-"},
            {"beat": 4, "fungsi": "cta", "ringkasan": "ajakan di akhir"},
        ],
        "pacing": {"estimasi_detik": round(est), "kata_per_detik": 2.6},
        "pattern_name": f"{hook_type}-based explainer",
        "why_it_works": "Membuka dengan ketegangan lalu menjelaskan; penonton menunggu jawaban.",
        "transplantable": ["tipe hook", "urutan fungsi beat", "ritme pendek per beat"],
        "must_not_copy": ["kalimat persis", "contoh spesifik", "audio/musik", "visual & editing",
                          "nama & identitas kreator"],
        "analyzed_by": "heuristic",
        "reference_title": reference.get("title", ""),
        "reference_author": reference.get("author", ""),
    }


# ---------------------------------------------------------------- 2 dan 3. TIRU + MODIFIKASI

TRANSFORM_RULES = [
    "Subjek diganti: bahas topik lain dari radar, bukan topik video referensi.",
    "Semua angka, contoh, dan analogi ditulis sendiri — tidak ada yang diwarisi.",
    "Urutan beat diubah dan ditambah satu beat 'batasan' (referensi biasanya tidak punya).",
    "Ditambah konteks lokal Indonesia + satu kritik/kelemahan jujur.",
    "Tidak memakai kalimat khas, jargon khas, atau gaya visual kreator asal.",
    "Narasi ditulis ulang dari nol dengan persona kita, bukan diparafrase kata per kata.",
]


def pattern_to_spec(pattern: dict, cluster: dict, cfg: dict) -> dict:
    """Ubah POLA jadi kerangka script orisinal untuk topik kita sendiri."""
    tema = cluster.get("label", "topik AI")
    angle = cluster.get("angle_hint", "kenapa ini penting")
    hook_type = (pattern.get("hook") or {}).get("type", "pertanyaan")

    hook_templates = {
        "pertanyaan": f"Kalau {tema.lower()}, kenapa itu bisa terjadi?",
        "angka": f"Satu angka menjelaskan {tema.lower()}.",
        "negasi": f"Bukan seperti yang kamu kira soal {tema.lower()}.",
        "pernyataan": f"{tema} — dan ini yang jarang dijelaskan.",
    }
    beat_plan = [
        {"kind": "hook", "fungsi": "hook"},
        {"kind": "point", "fungsi": "konteks"},
        {"kind": "point", "fungsi": "penjelasan"},
        {"kind": "point", "fungsi": "contoh"},
        {"kind": "limit", "fungsi": "batasan"},
        {"kind": "cta", "fungsi": "cta"},
    ]
    return {
        "topic": tema, "angle": angle,
        "hook_draft": hook_templates.get(hook_type, hook_templates["pertanyaan"]),
        "beat_plan": beat_plan,
        "inherited_from_pattern": {"hook_type": hook_type, "pacing": pattern.get("pacing", {})},
        "transformation_rules": TRANSFORM_RULES,
        "reference": {"title": pattern.get("reference_title", ""),
                      "author": pattern.get("reference_author", "")},
    }


PLACEHOLDERS = [
    (r"\b(kamu|anda|kalian)\b", "penonton"),
    (r"\b(aku|saya|gue|gw)\b", "narasumber"),
]


def transform_spec(spec: dict, cluster: dict, cfg: dict) -> dict:
    """Hasilkan script penuh yang orisinal dari kerangka, plus jejak transformasi."""
    from . import scriptwriter

    script = scriptwriter.write_with_template(cluster, cfg)
    script["hook"] = spec["hook_draft"]
    script["beats"][0]["narration"] = spec["hook_draft"]
    script["beats"][0]["headline"] = "Kalau begitu?"
    script["transformation"] = {
        "pattern_used": spec["inherited_from_pattern"],
        "rules_applied": [
            "topik diambil dari radar sendiri, bukan dari referensi",
            "narasi ditulis ulang penuh (template persona)",
            "beat 'limit' ditambahkan (biasanya tidak ada di referensi)",
            "tidak ada aset dari kreator asal",
        ],
        "reference_title": spec["reference"]["title"],
        "reference_author": spec["reference"]["author"],
    }
    return script


# ---------------------------------------------------------------- pengaman

def compliance_check(script: dict, reference_text: str = "") -> dict:
    """Daftar periksa sebelum render. Bukan nasihat hukum.

    Yang dinilai: kemiripan teks dengan referensi, keberadaan atribusi,
    keberadaan transformasi, dan aset yang dipakai.
    """
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    narration = " ".join(str(b.get("narration", "")) for b in script.get("beats", []))
    words = set(re.findall(r"[a-z0-9]+", narration.lower()))

    # 1. kemiripan leksikal dengan referensi (Jaccard pada kata unik)
    if reference_text:
        ref_words = set(re.findall(r"[a-z0-9]+", reference_text.lower()))
        inter = len(words & ref_words)
        union = len(words | ref_words) or 1
        sim = inter / union
        add("kemiripan_teks", sim < 0.35,
            f"Jaccard {sim:.2f} (aman <0.35; makin rendah makin orisinal)")
    else:
        add("kemiripan_teks", True, "tidak ada referensi untuk dibandingkan")

    # 2. ada jejak transformasi
    add("jejak_transformasi", bool(script.get("transformation")),
        "script mencatat pola & aturan transformasi" if script.get("transformation")
        else "tidak ada catatan transformasi — kalau meniru pola, catat asalnya")

    # 3. tidak mengklaim karya orang
    add("tanpa_klaim_aset", not re.search(r"\b(musik|lagu|video|klip)\s+dari\b", narration.lower()),
        "narasi tidak mengklaim aset pihak lain")

    # 4. sumber untuk klaim
    add("sumber_ada", bool(script.get("sources")), f"{len(script.get('sources', []))} sumber")

    # 5. atribusi referensi (kalau memakai pola dari kreator tertentu)
    ref = (script.get("transformation") or {}).get("reference_author")
    if ref:
        add("atribusi", "*opsional*: sebut kreator sumber pola di komentar (etika, bukan kewajiban hukum)",
            f"pola terinspirasi dari @{ref}")

    # 6. label AI
    add("label_ai", True, "wajib aktifkan label 'konten dihasilkan AI' saat upload")

    failed = [c for c in checks if not c["ok"]]
    return {"passed": not failed, "score": round(1 - len(failed) / len(checks), 2),
            "checks": checks, "failed": [c["check"] for c in failed],
            "note": "Ini daftar periksa praktis, bukan nasihat hukum. Ide bebas dipakai; "
                    "ekspresi (naskah, audio, visual, editing) tidak."}


# ---------------------------------------------------------------- entrypoint

def run(reference_url: str = "", transcript: str = "", cfg: dict | None = None) -> dict:
    pattern = {}
    if reference_url:
        ref = fetch_reference(reference_url)
        if ref.get("error"):
            print(f"  [warn] {ref['error']}")
        else:
            print(f"  referensi: {ref['title'][:60]} — @{ref['author']}")
            pattern = analyze_reference(ref, transcript, cfg)
            print(f"  pola: {pattern.get('pattern_name')} "
                  f"(hook: {pattern.get('hook', {}).get('type')})")
            print(f"  yang TIDAK boleh ditiru: {', '.join(pattern.get('must_not_copy', [])[:3])}")
    return pattern
