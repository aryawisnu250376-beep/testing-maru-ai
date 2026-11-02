"""SCRIPTWRITER v2 + sanitiser + validator.

Aturan yang tidak bisa dinegosiasi:
  1. Tiap klaim punya sumber (sources[] + source_refs per beat). URL diambil dari
     cluster trend, BUKAN dari model.
  2. Wajib ada tepat satu beat `limit` yang menyebut batasan/kekurangan.
  3. Hook ≤ 9 kata, tiap beat ≤ 24 kata.
  4. Tiap beat wajib punya spec `visual` supaya render tidak menebak.

Dua lapis penjagaan:
  - sanitiser : memperbaiki output jelek (memotong, menambah beat limit, memilih
                visual default). Tidak mengubah fakta.
  - validator : menolak kalau masih ada pelanggaran. Dipakai sebagai gerbang.
"""
from __future__ import annotations

import json
import re

import yaml

from .config import ROOT, load_config
from .llm import LLM
from .story import HEADLINES, STAGES, VISUALS, build_arc, hook_options

BANNED = ["revolusioner", "game changer", "mengubah segalanya", "terobosan besar",
          "mengguncang dunia", "wajib punya", "auto kaya", "sekarang semua orang bisa jadi kaya"]

VISUAL_TYPES = {
    "card": "teks besar + penjelasan. props: {}",
    "diagram": "alur kotak berurutan + panah. props: {\"nodes\":[{\"title\":\"..\",\"sub\":\"..\"}]} (2-4)",
    "steps": "daftar langkah bernomor. props: {\"items\":[{\"title\":\"..\"}]} (2-4)",
    "bars": "perbandingan bar tumbuh. props: {\"items\":[{\"label\":\"..\",\"value\":angka}],\"unit\":\"..\"}",
    "stat": "satu angka besar menghitung naik. props: {\"value\":\"4x\",\"label\":\"..\",\"sub\":\"..\"}",
    "compare": "dua kolom. props: {\"left\":{\"title\":\"..\",\"items\":[\"..\"]},\"right\":{...}}",
    "code": "blok terminal yang mengetik. props: {\"lines\":[\"..\"]}",
    "quote": "kutipan besar. props: {\"text\":\"..\",\"attribution\":\"..\"}",
    "character": "Nara, karakter tetap 2D. props: {\"emotion\":\"curious|worried|happy\"}",
    "clock": "jam analogi. props: {\"label\":\"...\",\"illustrative\":true}",
    "thermometer": "indikator kualitatif. props: {\"label\":\"...\",\"level\":0.6,\"illustrative\":true}",
    "manim": "animasi diagram bergerak (Manim). props: {\"scene\":\"diagram|steps|bars|compare|stat\", ...props scene}",
}

SYSTEM = f"""Kamu penulis script untuk kanal TikTok edukasi AI berbahasa Indonesia.
Audiens: orang Indonesia 18-35 tahun, penasaran teknologi, TIDAK teknis.

ATURAN KERAS (langgar = output ditolak):
1. Bahasa Indonesia santai, seperti menjelaskan ke teman. Boleh pakai "kamu"/"gw".
2. Hook maksimal 9 kata. Harus bikin orang berhenti scroll.
3. Untuk cerita_naratif: tepat 7 beat, story_stage berurutan tokoh→masalah→percobaan→titik_balik→batasan→pelajaran→cta. kinds: hook,point,point,point,limit,point,cta. Maks 24 kata/beat, target 125-155 kata total.
4. WAJIB tepat satu beat berjenis "limit" yang menyebut kelemahan/batasan jujur.
5. WAJIB satu analogi kehidupan sehari-hari (boleh di beat sendiri).
6. JANGAN sebut nama model, versi, angka, atau tanggal yang tidak ada di SUMBER.
7. Jangan pakai kata: revolusioner, game changer, mengubah segalanya.
8. Setiap beat punya source_refs (indeks sumber). Boleh [] untuk hook dan cta.
9. Tiap beat WAJIB punya blok "visual" berisi "type" + "props".
   Tipe yang tersedia:
{chr(10).join('   - ' + k + ': ' + v for k, v in VISUAL_TYPES.items())}
   Pilih visual yang benar-benar mewakili isi beat. Jangan semuanya "card":
   minimal 2 jenis visual berbeda dalam satu video.
10. headline MAKSIMAL 5 kata (tampil besar). body MAKSIMAL 18 kata (teks di layar).
11. CTA singkat, tanpa jualan.
12. Nara adalah tokoh fiksi, bukan pengalaman nyata atau testimoni. story.fictional=true dan disclosure menyebut ilustrasi. Jangan mengarang hasil, angka, atau keunggulan.
13. Klaim faktual pada beat masalah/percobaan/titik_balik/batasan/pelajaran wajib source_refs yang benar-benar mendukung. Jangan mengutip isi sumber yang tidak disediakan.
14. Diagram tanpa data numerik bersumber harus illustrative=true. Jangan mengarang statistik.

FORMAT OUTPUT: JSON valid saja, tanpa penjelasan, tanpa markdown fence.
Skema:
{{
 "title": "judul internal, maks 60 char",
 "format": "cerita_naratif",
 "story": {{"fictional": true, "character": "Nara", "disclosure": "Cerita Nara adalah ilustrasi, bukan testimoni."}},
 "hook_options": [{{"id":"A","text":"..."}},{{"id":"B","text":"..."}}],
 "hook_variant": "A",
 "hook": "kalimat hook",
 "beats": [
   {{"kind":"hook|point|limit|cta", "story_stage":"tokoh|masalah|percobaan|titik_balik|batasan|pelajaran|cta",
     "narration":"yang diucapkan narator (maks 24 kata)",
     "headline":"MAKS 5 KATA",
     "body":"1 kalimat pendek untuk layar (maks 18 kata)",
     "source_refs":[0,2],
     "visual":{{"type":"...","props":{{...}}}}}}
 ],
 "caption":"caption TikTok 1-2 kalimat, mengandung pertanyaan",
 "hashtags":["#AI","#belajarAI"],
 "sources":[{{"title":"...","url":"..."}}]
}}"""


# ---------------------------------------------------------------- prompt

def _persona() -> dict:
    try:
        with open(ROOT / "config" / "persona.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _patterns(cfg: dict) -> str:
    try:
        from .learning import prompt_block

        return prompt_block()
    except Exception:
        return ""


def build_messages(cluster: dict, cfg: dict, feedback: str | None = None) -> list[dict]:
    p = _persona()
    evidence = "\n".join(
        f"[{i}] ({e['source']}, skor {e['score']:.2f}) {e['title']} — {e['url']}"
        for i, e in enumerate(cluster.get("evidence", [])))
    n = len(cluster.get("evidence", []))
    voice = json.dumps(p.get("voice", {}), ensure_ascii=False)
    formats = json.dumps(p.get("format_library", []), ensure_ascii=False)
    pat = _patterns(cfg)
    patterns = ("\n" + pat + "\n") if pat else ""

    user = f"""SUMBER (pakai HANYA ini):
{evidence}

TEMA: {cluster.get('label')}
SUDUT DISARANKAN: {cluster.get('angle_hint')}
SINYAL TERKUAT: {cluster.get('headline_signal')}

CIRI SUARA: {voice}
FORMAT TERSEDIA: {formats}
{patterns}
Tulis cerita Nara 50-65 detik, 7 beat. Hanya gunakan fakta yang benar-benar tersurat dalam sumber; jika tidak cukup, jadikan cerita tentang cara memeriksa sumber, bukan mengarang fitur. Sources wajib berisi {n} sumber di atas
dengan url PERSIS sama."""
    if feedback:
        user += f"\n\nREVISI WAJIB — percobaan sebelumnya melanggar:\n{feedback}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


# ---------------------------------------------------------------- sanitiser

def _trim_words(text: str, limit: int) -> str:
    # Never silently truncate a factual claim in the middle.
    words = str(text or "").split()
    if len(words) <= limit:
        return " ".join(words)
    cut = " ".join(words[:limit]).rstrip(",;:-")
    if not cut.endswith((".", "!", "?")):
        cut += "."
    return cut


def _short_headline(text: str, limit: int = 5) -> str:
    words = str(text or "").split()
    return " ".join(words[:limit]).rstrip(".,:;")


def default_visual(beat: dict, idx: int) -> dict:
    kind = beat.get("kind", "point")
    if kind in ("hook", "cta"):
        return {"type": "card", "props": {}}
    if kind == "limit":
        return {"type": "steps", "props": {"items": [{"title": _short_headline(
            s, 6)} for s in str(beat.get("body", "")).split(".") if s.strip()][:3] or
            [{"title": "Ada batasnya"}]}}
    return {"type": "card", "props": {}}


def sanitize(script: dict, cluster: dict, cfg: dict) -> tuple[dict, list[str]]:
    """Perbaiki output jelek tanpa mengubah fakta. Return (script, catatan)."""
    notes: list[str] = []
    sw = cfg.get("scriptwriter", {})
    max_words = sw.get("max_words_per_beat", 24)

    # judul dari label tema (lebih tajam daripada "Model AI baru: X")
    if cluster.get("label") and (not script.get("title") or
                                 re.match(r"^(model ai baru|trending)", str(script.get("title", "")).lower())):
        script["title"] = cluster["label"][:60]
        notes.append("title diambil dari label tema")

    script["hook"] = _trim_words(script.get("hook") or script.get("title", ""), 9)
    beats = script.get("beats") or []

    # buang beat kosong
    beats = [b for b in beats if str(b.get("narration") or "").strip()]
    if not beats:
        raise ValueError("script tanpa beat")

    if beats[0].get("kind") != "hook":
        beats[0]["kind"] = "hook"
        notes.append("beat pertama dipaksa jadi hook")

    for i, b in enumerate(beats):
        n = len(str(b.get("narration", "")).split())
        if n > max_words:
            notes.append(f"beat {i}: narasi {n} kata melebihi batas; perlu revisi, tidak dipotong diam-diam")
        b["headline"] = _short_headline(b.get("headline") or b.get("body", ""), 5)
        if not b.get("body"):
            b["body"] = _trim_words(b["narration"], 18)
        if len(str(b["body"]).split()) > 18:
            b["body"] = _trim_words(b["body"], 18)
            notes.append(f"beat {i}: body dipotong ke 18 kata")
        v = b.get("visual")
        if not isinstance(v, dict) or v.get("type") not in VISUAL_TYPES:
            b["visual"] = default_visual(b, i)
            notes.append(f"beat {i}: visual default")

    # wajib ada beat limit
    if sw.get("must_include_limitation", True) and "limit" not in [b.get("kind") for b in beats]:
        limit_beat = {
            "kind": "limit",
            "narration": "Tapi jangan buru-buru percaya. Kebanyakan klaim ini masih dari pengumuman dan demo, belum hasil pakai jangka panjang.",
            "headline": "Batasnya nyata",
            "body": "Demo bukan bukti. Cek sendiri sebelum percaya.",
            "source_refs": list(range(min(3, len(cluster.get("evidence", []))))),
            "visual": {"type": "steps", "props": {"items": [
                {"title": "Masih demo"}, {"title": "Belum uji jangka panjang"},
                {"title": "Bisa berubah cepat"}]}},
        }
        limit_beat["_auto_limit"] = True
        insert_at = max(1, len(beats) - 1)
        if beats[-1].get("kind") == "cta":
            beats.insert(insert_at, limit_beat)
        else:
            beats.append(limit_beat)
        notes.append("beat 'limit' ditambahkan otomatis")

    if "cta" not in [b.get("kind") for b in beats]:
        beats.append({
            "kind": "cta",
            "narration": "Kalau kamu mau satu konsep AI dijelasin tiap hari dalam satu menit, follow dulu.",
            "headline": "Satu konsep. Satu menit.",
            "body": "Follow buat satu konsep AI tiap hari.",
            "source_refs": [],
            "visual": {"type": "quote", "props": {
                "text": "Yang penting bukan yang paling canggih, tapi yang kamu pahami.",
                "attribution": cfg.get("brand", {}).get("name", "")}},
        })
        notes.append("beat 'cta' ditambahkan")

    limit_seen = False
    kept = []
    for b in beats:
        if b.get("kind") == "limit":
            if limit_seen:
                continue
            limit_seen = True
        kept.append(b)
    beats = kept
    max_beats = int(sw.get("max_beats", 7))
    if len(beats) > max_beats:
        required = [beats[0]] + [b for b in beats if b.get("kind") == "limit"][:1]
        if beats[-1].get("kind") == "cta":
            required.append(beats[-1])
        room = max_beats - len(required)
        middle = [b for b in beats[1:-1] if b.get("kind") not in ("limit", "cta")][:room]
        beats = [beats[0]] + middle + required[1:]
        notes.append("jumlah beat dibatasi tanpa membuang batasan/CTA")

    # pastikan variasi visual
    types = [b["visual"]["type"] for b in beats]
    if len(set(types)) < 2 and len(beats) >= 3:
        beats[1]["visual"] = {"type": "diagram", "props": {"nodes": [
            {"title": _short_headline(b.get("headline") or "Langkah 1", 4), "sub": ""},
            {"title": _short_headline(beats[2].get("headline") or "Langkah 2", 4), "sub": ""},
        ]}}
        notes.append("variasi visual ditambahkan")

    script["beats"] = beats
    script.setdefault("format", "satu_konsep")
    script.setdefault("caption", str(script.get("title", "")) + " — menurut kamu gimana?")
    script.setdefault("hashtags", cfg.get("publish", {}).get("default_hashtags", ["#AI"]))

    # sumber: selalu dari cluster, bukan dari model
    allowed = {e["url"]: e["title"] for e in cluster.get("evidence", [])}
    srcs, seen = [], set()
    for s in script.get("sources", []) or []:
        url = str(s.get("url", "")).strip()
        if url in allowed and url not in seen:
            srcs.append({"title": allowed[url], "url": url})
            seen.add(url)
    if not srcs:
        srcs = [{"title": e["title"], "url": e["url"]} for e in cluster.get("evidence", [])[:4]]
        notes.append("sources diambil dari cluster")
    old_sources = script.get("sources") or []
    new_index = {s_["url"]: i for i,s_ in enumerate(srcs)}
    for b in beats:
        if b.get("_auto_limit"):
            b["source_refs"] = list(range(len(srcs)))
            b.pop("_auto_limit")
            continue
        mapped = []
        for ref in b.get("source_refs") or []:
            if type(ref) is int and 0 <= ref < len(old_sources):
                url = old_sources[ref].get("url")
                if url in new_index and new_index[url] not in mapped:
                    mapped.append(new_index[url])
        b["source_refs"] = mapped
    script["sources"] = srcs
    return script, notes


# ---------------------------------------------------------------- validator

def validate_script(script: dict, cfg: dict, strict: bool = True) -> tuple[bool, list[str], list[str]]:
    sw = cfg.get("scriptwriter", {})
    errors: list[str] = []
    warns: list[str] = []

    for key in ("title", "hook", "beats", "caption", "sources"):
        if key not in script:
            errors.append(f"field wajib hilang: {key}")
    if errors:
        return False, errors, warns

    beats = script.get("beats") or []
    max_beats, max_words = sw.get("max_beats", 7), sw.get("max_words_per_beat", 24)
    if not (3 <= len(beats) <= max_beats):
        errors.append(f"jumlah beat {len(beats)} di luar 3..{max_beats}")
    if len(script["hook"].split()) > 11:
        warns.append(f"hook {len(script['hook'].split())} kata (>11)")

    kinds = [b.get("kind") for b in beats]
    if sw.get("must_include_limitation", True) and "limit" not in kinds:
        errors.append("tidak ada beat 'limit' (wajib sebut batasan)")
    if kinds and kinds[0] != "hook":
        errors.append("beat pertama harus 'hook'")
    if "cta" not in kinds:
        warns.append("tidak ada beat 'cta'")

    for i, b in enumerate(beats):
        n = len(str(b.get("narration") or "").split())
        if n == 0:
            errors.append(f"beat {i}: narration kosong")
        elif n > max_words:
            errors.append(f"beat {i}: {n} kata > {max_words}")
        if not b.get("headline"):
            errors.append(f"beat {i}: headline kosong")
        v = b.get("visual")
        if not isinstance(v, dict) or v.get("type") not in VISUAL_TYPES:
            errors.append(f"beat {i}: visual tidak valid")
        else:
            props = v.get("props") or {}
            if v["type"] in ("diagram", "steps", "bars") and not (props.get("nodes") or props.get("items")):
                errors.append(f"beat {i}: visual '{v['type']}' tanpa props.items/nodes")
            if v["type"] == "stat" and not props.get("value"):
                errors.append(f"beat {i}: visual 'stat' tanpa props.value")
            if v["type"] == "compare" and not (props.get("left") and props.get("right")):
                errors.append(f"beat {i}: visual 'compare' tanpa left/right")

    sources = script.get("sources") or []
    if sw.get("require_sources", True) and not sources:
        errors.append("sources kosong — tiap klaim wajib punya URL")
    for s in sources:
        if not str(s.get("url", "")).startswith("http"):
            errors.append(f"sumber tanpa URL valid: {s.get('title')}")

    from urllib.parse import urlparse
    for s_ in sources:
        u = urlparse(str(s_.get("url", "")))
        if u.scheme not in ("http", "https") or not u.hostname:
            errors.append("URL sumber harus http/https dan memiliki host")
    for i, b in enumerate(beats):
        refs = b.get("source_refs", [])
        if not isinstance(refs, list) or any(type(j) is not int or j < 0 or j >= len(sources) for j in refs):
            errors.append(f"beat {i}: source_refs tidak valid")
        elif b.get("kind") in ("point", "limit") and not refs:
            errors.append(f"beat {i}: klaim faktual wajib merujuk sumber")
        v = b.get("visual") or {}
        props = v.get("props") or {}
        if v.get("type") in ("bars", "stat") and not props.get("illustrative") and not refs:
            errors.append(f"beat {i}: angka visual wajib bersumber atau ditandai ilustrasi")
    if kinds.count("limit") != 1:
        errors.append("wajib tepat satu beat limit")
    if len(script["hook"].split()) > 9:
        errors.append("hook melebihi 9 kata")
    if script.get("format") == "cerita_naratif":
        if [b.get("story_stage") for b in beats] != STAGES:
            errors.append("urutan cerita harus tokoh→masalah→percobaan→titik_balik→batasan→pelajaran→cta")
        if not (script.get("story") or {}).get("fictional"):
            errors.append("cerita fiksi wajib diberi label")
    low = json.dumps(script, ensure_ascii=False).lower()
    for w in BANNED:
        if w in low:
            errors.append(f"kata terlarang: '{w}'")

    src_text = " ".join(str(s.get("title", "")) + str(s.get("url", "")) for s in sources).lower()
    for v in set(re.findall(r"\b[a-z][a-z0-9.\-]{2,}\s?v?\d+\.\d+\b", low)):
        if v.replace(" ", "") not in src_text.replace(" ", ""):
            warns.append(f"versi/angka '{v}' tidak ada di sources — cek halusinasi")

    return (not errors if strict else True), errors, warns


# ---------------------------------------------------------------- template

def _diagram_label(title: str) -> str:
    """Judul sinyal mentah -> label pendek yang kebaca di kotak diagram."""
    t = re.sub(r"^Model AI baru:\s*", "", str(title))
    t = re.sub(r"^Trending di Indonesia:\s*", "", t)
    t = re.sub(r"\.(gguf|safetensors)$", "", t, flags=re.I)
    if ":" in t:
        head, tail = t.split(":", 1)
        t = f"{head.split('/')[-1]}: {tail.strip()}"
    return t[:40]


def write_with_template(cluster: dict, cfg: dict) -> dict:
    """Fallback naratif yang jujur: tokoh fiksi + fakta terbatas pada sumber."""
    from copy import deepcopy
    ev = cluster.get("evidence") or [
        {"title": x.get("title", "Referensi"), "url": x["url"]}
        for x in cluster.get("sources", []) if isinstance(x, dict) and x.get("url")
    ]
    # Last resort for a manually supplied list of URLs.
    if not ev and cluster.get("urls"):
        ev = [{"title": "Sumber topik", "url": u} for u in cluster["urls"]]
    sources = [{"title": e["title"], "url": e["url"]} for e in ev[:4]]
    if not sources:
        raise ValueError("Tidak ada sumber. Riset/topik harus menyediakan evidence atau sources.")
    refs = list(range(len(sources)))
    theme = cluster.get("theme") or "general"
    arc = build_arc(theme)
    options = hook_options(theme)
    narrations = [options[0]["text"], *arc]
    beats = []
    for i, narration in enumerate(narrations):
        beats.append({
            "kind": ["hook", "point", "point", "point", "limit", "point", "cta"][i],
            "story_stage": STAGES[i], "narration": narration,
            "headline": HEADLINES[i] if i < len(HEADLINES) else "Pahami dulu",
            "body": narration,
            "source_refs": refs if i in (1, 2, 3, 4, 5) else [],
            "visual": deepcopy(VISUALS[i]),
        })
    beats[2]["visual"] = {"type": "diagram", "props": {"nodes": [
        {"title": "Baca sumber"}, {"title": "Coba tugas kecil"}, {"title": "Periksa hasil"}]}}
    disclosure = "Cerita Nara adalah ilustrasi fiktif, bukan testimoni. Periksa sumber sebelum mengambil keputusan."
    return {
        "title": str(cluster.get("label") or "Cerita AI Nara")[:60],
        "format": "cerita_naratif", "theme": theme,
        "story": {"fictional": True, "character": "Nara", "disclosure": disclosure},
        "hook": narrations[0], "hook_options": options, "hook_variant": "A",
        "beats": beats, "caption": narrations[-1] + "\n\n" + disclosure,
        "hashtags": cfg.get("publish", {}).get("default_hashtags", ["#AI"]),
        "sources": sources, "generator": "template",
        "editorial_status": "perlu_tinjauan_fakta",
        "notes": ["Template naratif, bukan keluaran LLM.", "Nara adalah tokoh fiktif.",
                  "Tautan sumber bukan pengganti pemeriksaan isi sumber oleh manusia."],
    }


# ---------------------------------------------------------------- entrypoint

def write_script(cluster: dict, cfg: dict | None = None, llm: LLM | None = None,
                 max_attempts: int = 3) -> dict:
    """Tulis script. LLM kalau ada, revisi otomatis kalau validator gagal."""
    cfg = cfg or load_config()
    llm = llm or LLM.from_config(cfg)

    if not llm.available:
        script = write_with_template(cluster, cfg)
        script, notes = sanitize(script, cluster, cfg)
        script["notes"] = notes
        return script

    feedback: str | None = None
    for attempt in range(max_attempts):
        try:
            raw = llm.chat_json(build_messages(cluster, cfg, feedback), tier="strong",
                                temperature=0.75)
        except Exception as e:
            print(f"  [warn] LLM gagal ({e}); fallback template")
            script = write_with_template(cluster, cfg)
            script, notes = sanitize(script, cluster, cfg)
            script["notes"] = notes + ["LLM gagal"]
            return script

        raw["generator"] = "llm"
        raw["theme"] = cluster.get("theme")
        script, notes = sanitize(raw, cluster, cfg)
        ok, errors, warns = validate_script(script, cfg)
        script["notes"] = notes
        if ok:
            return script
        feedback = "\n".join(f"- {e}" for e in errors)
        print(f"  percobaan {attempt + 1}: {len(errors)} pelanggaran, minta revisi")
    raise ValueError("Naskah LLM belum lolos validasi: " + "; ".join(errors))


if __name__ == "__main__":
    cfg = load_config()
    rep = json.load(open(ROOT / "data" / "last_trend_report.json", encoding="utf-8"))
    sc = write_script(rep["clusters"][0], cfg)
    ok, errs, warns = validate_script(sc, cfg)
    print(f"generator={sc['generator']} ok={ok}")
    for e in errs:
        print("  ERROR:", e)
    for w in warns:
        print("  WARN :", w)
