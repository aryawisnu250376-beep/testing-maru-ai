"""TREND RADAR — inti "kesadaran trend".

Realistis: tidak ada API trend TikTok publik. Jadi kita kumpulkan sinyal dari
sumber yang LEGAL & GRATIS, lalu skor: relevansi niche x momentum x kebaruan x
kecocokan-format.

Semua sumber di bawah ini gratis dan tanpa API key (kecuali GitHub = rate limit
ketat kalau tanpa token; taruh token di env GITHUB_TOKEN biar naik 30x).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

from . import db
from .config import load_config

UA = {"User-Agent": "ai-edukasi-agent/0.1 (+https://github.com/)"}

# Leksikon niche: istilah yang bikin sinyal dianggap relevan untuk kanal edukasi AI
AI_LEXICON = [
    "ai", "a.i.", "artificial intelligence", "llm", "language model", "gpt", "claude",
    "gemini", "llama", "qwen", "deepseek", "mistral", "phi", "gemma", "nemotron",
    "transformer", "diffusion", "agent", "agents", "rag", "embedding", "fine-tune",
    "finetune", "inference", "quantization", "quantized", "on-device", "local model",
    "open source ai", "open-source ai", "weights", "context window", "token", "tokens",
    "multimodal", "vision model", "speech", "tts", "whisper", "machine learning",
    "neural", "benchmark", "reasoning", "mcp", "coding agent", "copilot", "chatbot",
    "huggingface", "hugging face", "vlm", "moe", "mixture of experts", "distillation",
]

# Petunjuk bahwa topik cocok dijadikan pelajaran 60 detik
FORMAT_HINTS = [
    "why", "how", "kenapa", "cara", "apa itu", "what is", "explained", "guide",
    "introducing", "announcing", "release", "launch", "runs on", "small", "tiny",
    "1b", "1.5b", "1.7b", "2b", "3b", "4b", "7b", "vs", "diy", "local", "offline",
    "privacy", "free", "open source", "open-source",
]

# Taksonomi tema -> jembatan dari "sinyal mentah" ke "sudut pelajaran".
# Satu tema = satu keluarga ide konten. Label & angle ditulis bahasa manusia,
# karena inilah yang nanti dikirim ke penonton.
THEMES: dict[str, dict] = {
    "on_device": {
        "label": "AI yang bisa jalan di HP sendiri, tanpa internet",
        "keywords": ["on-device", "on device", "local model", "offline", "android", "mobile",
                     "phone", "runs on", "edge device", "gguf", "llama.cpp", "ollama",
                     "quantized", "quantization", "laptop", "cpu", "unsloth", "harness",
                     "hp", "ponsel", "telepon", "handphone", "tanpa internet", "offline", "lokal",
                     "di perangkat", "kantong"],
        "angle": "Kenapa AI sekarang muat di kantong, dan apa batasnya",
    },
    "small_models": {
        "label": "Model AI kecil yang makin pintar",
        "keywords": ["1b", "1.5b", "1.7b", "2b", "3b", "4b", "tiny", "mini", "small model",
                     "compact", "nano", "lite", "distill",
                     "model kecil", "kecil", "ringan", "mini", "mungil"],
        "angle": "Kecil bukan berarti bodoh: kenapa model mungil sekarang dipakai serius",
    },
    "agents": {
        "label": "AI agent yang bisa ngerjain tugas sendiri",
        "keywords": ["agent", "agentic", "mcp", "tool use", "autonomous", "computer use",
                     "browser use", "workflow", "orchestration", "multi-agent",
                     "agen", "otomatis", "mandiri", "tugas sendiri", "kerja sendiri"],
        "angle": "Beda chatbot vs agent, dan kenapa itu penting buat kerjaan kamu",
    },
    "open_source": {
        "label": "Model open source yang ngejar ketat model tertutup",
        "keywords": ["open source", "open-source", "weights", "apache", "mit license",
                     "community model", "permissive",
                     "terbuka", "sumber terbuka", "gratis"],
        "angle": "Kenapa bobot model terbuka mengubah siapa yang bisa bikin AI",
    },
    "reasoning": {
        "label": "Model yang 'mikir dulu' sebelum jawab",
        "keywords": ["reasoning", "thinking", "chain of thought", "thinks", "r1", "o3",
                     "benchmark", "swe-bench", "math", "logic",
                     "nalar", "berpikir", "mikir", "logika", "matematika"],
        "angle": "Apa yang sebenarnya terjadi saat AI 'berpikir', dan kapan itu sia-sia",
    },
    "multimodal": {
        "label": "AI yang bisa lihat, dengar, dan bikin gambar",
        "keywords": ["vision", "vlm", "multimodal", "image", "video gen", "speech", "tts",
                     "audio", "voice", "transcribe", "ocr", "diffusion",
                     "gambar", "suara", "video", "lihat", "dengar", "bikin gambar"],
        "angle": "Cara AI 'melihat' gambar, dijelaskan tanpa matematika",
    },
    "cost": {
        "label": "Harga AI yang jatuh dan siapa yang untung",
        "keywords": ["free", "cheap", "$", "price", "pricing", "cost", "token", "api key",
                     "quota", "rate limit", "subscription",
                     "biaya", "murah", "bayar", "langganan", "kuota"],
        "angle": "Kenapa biaya AI turun cepat, dan gimana itu dipakai bisnis",
    },
    "coding": {
        "label": "AI yang nulis kode dan ngerjain repo",
        "keywords": ["code", "coding", "copilot", "ide", "developer", "pull request", "repo",
                     "sdk", "cli", "harness",
                     "kode", "ngoding", "program", "developer", "aplikasi"],
        "angle": "Batas nyata AI coding: apa yang aman diserahin, apa yang jangan",
    },
    "rag_memory": {
        "label": "AI yang bisa 'ingat' dokumen dan obrolan kamu",
        "keywords": ["rag", "embedding", "retrieval", "vector", "context window", "memory",
                     "knowledge base", "long context", "chunk",
                     "dokumen", "ingat", "memori", "pengetahuan", "data kamu", "pdf"],
        "angle": "RAG vs lengkapi model: cara paling murah bikin AI paham data kamu",
    },
    "safety": {
        "label": "Keamanan, privasi, dan aturan main AI",
        "keywords": ["safety", "alignment", "jailbreak", "privacy", "regulation", "policy",
                     "leak", "security", "guardrail", "bias",
                     "aman", "bahaya", "privasi", "data pribadi", "aturan", "bocor", "risiko"],
        "angle": "Risiko nyata AI yang jarang dibahas media, dan cara menutupnya",
    },
}

STOPWORDS = set("""
the a an and or of to in for on with is are was were be been this that these those
it its as at by from you your we our they their he she his her i me my
yang dan di ke dari untuk pada dengan ini itu adalah akan bisa dapat tidak bukan
juga sudah telah para kita kami mereka dia ia anda kamu gw aku atau karena sebab
""".split())


# ---------------------------------------------------------------- utilities

def _get(url: str, timeout: int = 20, headers: dict | None = None) -> bytes:
    h = dict(UA)
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _h(text: str) -> str:
    return hashlib.sha1(re.sub(r"\s+", " ", text.lower()).strip().encode()).hexdigest()[:16]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _log_norm(value: float, ceiling: float = 5000.0) -> float:
    """Skor mentah (points/likes/stars/traffic) -> 0..1 secara logaritmik."""
    if value <= 0:
        return 0.0
    return min(1.0, math.log10(1 + value) / math.log10(1 + ceiling))


# ---------------------------------------------------------------- collectors

def collect_hackernews(limit: int = 15) -> list[dict]:
    since = int((datetime.now(timezone.utc) - timedelta(days=3)).timestamp())
    out: dict[str, dict] = {}
    for term in ("AI", "LLM", "model"):
        url = ("https://hn.algolia.com/api/v1/search_by_date?"
               + urllib.parse.urlencode({
                   "query": term, "tags": "story", "hitsPerPage": limit,
                   "numericFilters": f"points>80,created_at_i>{since}",
               }))
        try:
            data = json.loads(_get(url))
        except Exception as e:
            print(f"  [warn] hackernews '{term}': {e}")
            continue
        for hit in data.get("hits", []):
            title = (hit.get("title") or "").strip()
            if not title:
                continue
            hid = hit.get("objectID", title)
            out[hid] = {
                "source": "hackernews",
                "title": title,
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hid}",
                "raw_score": float(hit.get("points") or 0),
                "published": hit.get("created_at", ""),
                "meta": {"points": hit.get("points"), "comments": hit.get("num_comments")},
            }
    return list(out.values())


def collect_huggingface(limit: int = 15) -> list[dict]:
    url = f"https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit={limit}"
    try:
        data = json.loads(_get(url))
    except Exception as e:
        print(f"  [warn] huggingface: {e}")
        return []
    out = []
    for m in data:
        mid = m.get("id", "")
        if not mid:
            continue
        tags = m.get("tags") or []
        size_hint = next((t for t in tags if re.match(r"^\d+(\.\d+)?[bm]$", str(t))), "")
        title = f"Model AI baru: {mid.split('/')[-1]}" + (f" ({size_hint})" if size_hint else "")
        out.append({
            "source": "huggingface",
            "title": title,
            "url": f"https://huggingface.co/{mid}",
            "raw_score": float(m.get("likes") or 0),
            "published": m.get("createdAt", ""),
            "meta": {"likes": m.get("likes"), "downloads": m.get("downloads"),
                     "tags": tags[:12], "pipeline": m.get("pipeline_tag")},
        })
    return out


def collect_github(limit: int = 15, days: int = 14) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    headers = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    out: dict[str, dict] = {}
    for topic in ("llm", "ai-agent"):
        q = urllib.parse.quote(f"topic:{topic} created:>{since}")
        url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={limit}"
        try:
            data = json.loads(_get(url, headers=headers))
        except Exception as e:
            print(f"  [warn] github '{topic}': {e}")
            continue
        for r in data.get("items", []):
            name = r.get("full_name", "")
            desc = (r.get("description") or "").strip()
            out[name] = {
                "source": "github",
                "title": f"{name}: {desc}"[:180] if desc else name,
                "url": r.get("html_url", ""),
                "raw_score": float(r.get("stargazers_count") or 0),
                "published": r.get("created_at", ""),
                "meta": {"stars": r.get("stargazers_count"), "topic": topic,
                         "language": r.get("language")},
            }
    return list(out.values())


def collect_youtube(limit: int = 15, region: str = "ID") -> list[dict]:
    """YouTube = proxy terbaik untuk 'video pendek apa yang lagi naik'.

    Butuh YOUTUBE_API_KEY (free tier 10k unit/hari). Tanpa key: lewati diam-diam.
    """
    key = os.getenv("YOUTUBE_API_KEY", "")
    if not key:
        return []
    base = "https://www.googleapis.com/youtube/v3/videos"
    out: dict[str, dict] = {}
    for chart in ("mostPopular",):
        params = urllib.parse.urlencode({
            "part": "snippet,statistics", "chart": chart, "regionCode": region,
            "videoCategoryId": "28",  # Science & Technology
            "maxResults": min(limit, 25), "key": key,
        })
        try:
            data = json.loads(_get(f"{base}?{params}"))
        except Exception as e:
            print(f"  [warn] youtube: {e}")
            continue
        for v in data.get("items", []):
            sn = v.get("snippet", {})
            stats = v.get("statistics", {})
            title = (sn.get("title") or "").strip()
            if not title:
                continue
            views = int(stats.get("viewCount", 0) or 0)
            out[v["id"]] = {
                "source": "youtube",
                "title": f"[video] {title}",
                "url": f"https://www.youtube.com/watch?v={v['id']}",
                "raw_score": float(views // 1000),  # skala kasar biar sebanding
                "published": sn.get("publishedAt", ""),
                "meta": {"views": views, "channel": sn.get("channelTitle"),
                         "tags": sn.get("tags", [])[:10]},
            }
    return list(out.values())


def collect_reference_watchlist() -> list[dict]:
    """Sinyal dari video referensi yang KAMU amati (data/reference_watchlist.json).

    Yang diambil hanya POLA (nama pola, tipe hook), bukan isi karya. Setiap item
    diberi sumber "reference" dan skor kecil: tujuannya memancing ide, bukan
    mengklaim sedang trending.
    """
    import os as _os

    path = Path(_os.environ.get("REFERENCE_WATCHLIST",
                                Path(__file__).resolve().parents[1] / "data"
                                / "reference_watchlist.json"))
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [warn] watchlist referensi: {e}")
        return []

    out = []
    for item in data.get("items", []):
        transcript = (item.get("transcript") or "").strip()
        if not transcript:
            continue
        try:
            from .trends_tiktok import analyze_reference

            pattern = analyze_reference({"title": "", "url": item.get("url", "")},
                                        transcript, None)
        except Exception:
            continue
        name = pattern.get("pattern_name", "referensi")
        hook_type = (pattern.get("hook") or {}).get("type", "?")
        # tema: ambil kata kunci AI dari transkrip supaya masuk bucket yang tepat
        theme, _ = classify_theme(transcript, {})
        label = THEMES.get(theme, {}).get("label") or f"Pola '{name}' dari referensi"
        out.append({
            "source": "reference",
            "title": f"[pola] {name} (hook {hook_type}) — {label}",
            "url": item.get("url", ""),
            "raw_score": 60.0,
            "published": "",
            "meta": {"pattern": name, "hook_type": hook_type, "theme": theme,
                     "transcript_excerpt": transcript[:200]},
        })
    return out


def collect_google_trends(geo: str = "ID") -> list[dict]:
    url = f"https://trends.google.com/trending/rss?geo={geo}"
    try:
        raw = _get(url)
    except Exception as e:
        print(f"  [warn] google trends: {e}")
        return []
    ns = {"ht": "https://trends.google.com/trending/rss"}
    out = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  [warn] google trends parse: {e}")
        return []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        traffic_txt = item.findtext("ht:approx_traffic", default="", namespaces=ns) or ""
        traffic = float(re.sub(r"[^0-9]", "", traffic_txt) or 0)
        out.append({
            "source": "google_trends_id",
            "title": f"Trending di Indonesia: {title}",
            "url": item.findtext("link") or url,
            "raw_score": traffic,
            "published": item.findtext("pubDate") or "",
            "meta": {"approx_traffic": traffic_txt, "geo": geo},
        })
    return out


# ---------------------------------------------------------------- scoring

def relevance(title: str, meta: dict) -> tuple[float, list[str]]:
    text = (title + " " + " ".join(str(t) for t in (meta.get("tags") or []))).lower()
    hits = [term for term in AI_LEXICON if term in text]
    if not hits:
        return 0.0, []
    # 1 istilah = cukup; makin banyak makin yakin, tapi pakai diminishing return
    return min(1.0, 0.55 + 0.15 * (len(hits) - 1)), hits[:5]


def format_fit(title: str) -> tuple[float, list[str]]:
    text = title.lower()
    hits = [h for h in FORMAT_HINTS if h in text]
    return min(1.0, 0.45 + 0.12 * len(hits)), hits


def score_signals(signals: list[dict], seen: set[str], weights: dict,
                  min_score: float) -> list[dict]:
    scored = []
    for s in signals:
        rel, rel_hits = relevance(s["title"], s.get("meta", {}))
        if rel <= 0:
            continue  # buang yang tidak nyambung ke niche sama sekali
        mom = _log_norm(s["raw_score"])
        nov = 0.25 if s["hash"] in seen else 1.0
        fmt, fmt_hits = format_fit(s["title"])
        final = (weights["relevance"] * rel + weights["momentum"] * mom
                 + weights["novelty"] * nov + weights["format_fit"] * fmt)
        s = {**s, "score": round(final, 4),
             "why": {"relevance": rel, "momentum": mom, "novelty": nov, "format_fit": fmt,
                     "relevance_hits": rel_hits, "format_hits": fmt_hits}}
        if final >= min_score:
            scored.append(s)
    return sorted(scored, key=lambda x: x["score"], reverse=True)


def classify_theme(title: str, meta: dict) -> tuple[str, int]:
    """Tentukan tema dominan sebuah sinyal. Return (theme_id, jumlah keyword cocok).

    Judul diprioritaskan atas tag: model 1T yang kebetulan punya tag `gguf`
    bukan berarti tema "AI di HP". Tag hanya dipakai kalau judul tidak memberi
    petunjuk sama sekali.
    """
    def hits_in(text: str) -> dict[str, int]:
        low = text.lower()
        return {tid: sum(1 for kw in t["keywords"]
                         if re.search(r"(?<![a-z0-9])" + re.escape(kw), low))
                for tid, t in THEMES.items()}

    for text in (title, " ".join(str(t) for t in (meta.get("tags") or []))):
        counts = hits_in(text)
        best = max(counts, key=lambda k: counts[k])
        if counts[best] > 0:
            # model raksasa bukan cerita "AI di HP" walau punya tag kuantisasi
            if best in ("on_device", "small_models") and _is_huge_model(title):
                return "general", counts[best]
            return best, counts[best]
    return "general", 0


def _is_huge_model(title: str) -> bool:
    """Deteksi penanda ukuran raksasa: 100B+, 1T, A52B (MoE besar), dsb."""
    t = title.lower()
    if re.search(r"\b\d+(\.\d+)?t\b", t):          # 1T, 2.5T
        return True
    m = re.findall(r"\b(\d+(?:\.\d+)?)b\b", t)     # 100B, 405B, 671B
    return any(float(x) >= 70 for x in m)


def cluster(signals: list[dict], threshold: float = 0.55) -> list[dict]:
    """Kelompokkan sinyal per TEMA, bukan per kemiripan judul.

    Kenapa: judul sinyal itu pendek ("Model AI baru: X"), jadi Jaccard judul hampir
    selalu rendah. Yang benar-benar berarti adalah: beberapa sinyal dari beberapa
    sumber membicarakan keluarga ide yang sama. Itulah topik yang layak jadi video.

    Skor topik = skor sinyal terkuat + bonus bukti silang antar sumber.
    """
    buckets: dict[str, list[dict]] = {}
    for s in signals:
        theme, thits = classify_theme(s["title"], s.get("meta", {}))
        s = {**s, "theme": theme, "theme_hits": thits}
        buckets.setdefault(theme, []).append(s)

    clusters: list[dict] = []
    for theme, sigs in buckets.items():
        # dedupe URL di dalam tema
        seen_url: set[str] = set()
        uniq = []
        for s in sorted(sigs, key=lambda x: x["score"], reverse=True):
            if s["url"] in seen_url:
                continue
            seen_url.add(s["url"])
            uniq.append(s)

        sources = sorted({s["source"] for s in uniq})
        # headline = sinyal paling REPRESENTATIF untuk tema (bukan sekadar skor tertinggi)
        top = max(uniq, key=lambda x: (x.get("theme_hits", 0) * 2 + x["score"]))
        # bonus: makin banyak sumber independen membahas tema yang sama, makin kuat
        corroboration = min(0.18, 0.06 * (len(sources) - 1)) + min(0.09, 0.03 * (len(uniq) - 1))
        meta_theme = THEMES.get(theme, {})
        clusters.append({
            "theme": theme,
            "label": meta_theme.get("label", top["title"][:80]),
            "angle_hint": meta_theme.get("angle", "Kenapa ini penting sekarang"),
            "score": round(min(1.0, top["score"] + corroboration), 4),
            "headline_signal": top["title"],
            "sources": sources,
            "urls": [s["url"] for s in uniq][:6],
            "signals": uniq,
            "evidence": [{"source": s["source"], "title": s["title"], "url": s["url"],
                          "raw_score": s["raw_score"], "score": s["score"],
                          "hits": s.get("why", {}).get("relevance_hits", [])} for s in uniq[:6]],
        })
    return sorted(clusters, key=lambda c: c["score"], reverse=True)



# ---------------------------------------------------------------- entrypoint

def run(cfg: dict | None = None, persist: bool = True, verbose: bool = True) -> dict:
    cfg = cfg or load_config()
    tr = cfg["trend_radar"]
    src = tr.get("sources", {})
    limit = tr.get("max_signals_per_source", 15)

    signals: list[dict] = []
    if src.get("hackernews"):
        signals += collect_hackernews(limit)
    if src.get("huggingface"):
        signals += collect_huggingface(limit)
    if src.get("github"):
        signals += collect_github(limit)
    if src.get("google_trends_id"):
        signals += collect_google_trends(tr.get("geo", "ID"))
    if src.get("youtube", True):
        signals += collect_youtube(limit, tr.get("geo", "ID"))
    if src.get("reference_watchlist", True):
        refs = collect_reference_watchlist()
        if refs:
            signals += refs
            if verbose:
                print(f"  referensi yang kamu amati: {len(refs)} pola")

    for s in signals:
        s["hash"] = _h(s["title"])
        s.setdefault("meta", {})

    hashes = [s["hash"] for s in signals]
    db.init()
    seen = db.seen_trend(hashes)

    scored = score_signals(signals, seen, tr["weights"], tr.get("min_score", 0.45))
    clusters = cluster(scored, tr.get("dedupe_jaccard", 0.55))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {"collected": len(signals), "relevant": len(scored), "clusters": len(clusters)},
        "clusters": clusters[:10],
    }

    if persist:
        db.save_trends(signals)
        out = cfg["_root"] + "/data/last_trend_report.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    if verbose:
        c = report["counts"]
        print(f"\nTrend Radar: {c['collected']} sinyal → {c['relevant']} relevan → {c['clusters']} topik")
        for i, cl in enumerate(report["clusters"][:6], 1):
            print(f"  {i}. [{cl['score']:.2f}] {cl['label'][:80]}")
            print(f"     tema={cl['theme']} | sumber: {', '.join(cl['sources'])} | {len(cl['signals'])} bukti")
            print(f"     sinyal terkuat: {cl['headline_signal'][:76]}")
    return report


if __name__ == "__main__":
    run()
