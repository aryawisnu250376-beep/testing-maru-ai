"""LEARNING LOOP — dari metrik jadi keputusan penulisan berikutnya.

Ini bagian yang membedakan "pabrik konten" dari "pabrik konten yang makin pintar".

Alur:
  metrik video (views, avg_watch, likes) -> fitur script (tipe hook, kata hook,
  jenis visual, jumlah beat, ada angka?, ada pertanyaan?) -> agregasi per fitur ->
  blok "pola pemenang" -> disuntik ke prompt scriptwriter berikutnya.

Prinsip kehati-hatian:
  - Retensi (avg_watch / durasi) dipakai sebagai sinyal utama, bukan views.
    Views bisa naik karena kebetulan algoritma; retensi lebih jujur.
  - Minimum sampel (default 3) sebelum sebuah pola dianggap sinyal. Di bawah itu
    kita TIDAK menyimpulkan apa pun — mencegah belajar dari kebetulan.
  - Pola yang lemah tidak menghapus format; ia hanya jadi catatan.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import db

MIN_SAMPLES = 3


# ---------------------------------------------------------------- fitur

def extract_features(script: dict, duration: float = 0.0) -> dict:
    beats = script.get("beats") or []
    hook = str(script.get("hook") or (beats[0].get("narration") if beats else ""))
    hook_low = hook.lower()
    visuals = [((b.get("visual") or {}).get("type") or "card") for b in beats]
    body_words = sum(len(str(b.get("body", "")).split()) for b in beats)

    return {
        "theme": script.get("theme") or "unknown",
        "format": script.get("format") or "satu_konsep",
        "n_beats": len(beats),
        "hook_words": len(hook.split()),
        "hook_question": hook.rstrip().endswith("?") or bool(
            re.search(r"\b(kenapa|apa|gimana|bagaimana|kok)\b", hook_low)),
        "hook_number": bool(re.search(r"\d", hook)),
        "hook_type": ("pertanyaan" if hook.rstrip().endswith("?") else
                      "angka" if re.search(r"\d", hook) else
                      "negasi" if re.search(r"\b(bukan|jangan|nggak|tidak)\b", hook_low) else
                      "pernyataan"),
        "has_diagram": "diagram" in visuals,
        "has_stat": "stat" in visuals or "bars" in visuals,
        "has_compare": "compare" in visuals,
        "visual_variety": len(set(visuals)),
        "primary_visual": visuals[1] if len(visuals) > 1 else (visuals[0] if visuals else "card"),
        "duration_sec": round(duration, 1),
        "body_words": body_words,
    }


# ---------------------------------------------------------------- dataset

def collect_dataset() -> list[dict]:
    """Gabung episode + metrik terbaru jadi satu tabel latih."""
    db.init()
    rows: list[dict] = []
    with db.conn() as c:
        eps = c.execute(
            "SELECT id, script_json, paths_json FROM episodes "
            "WHERE script_json IS NOT NULL").fetchall()
        for ep in eps:
            m = c.execute(
                "SELECT * FROM metrics WHERE episode_id=? ORDER BY fetched_at DESC,rowid DESC LIMIT 1",
                (ep["id"],)).fetchone()
            if not m or not m["views"]:
                continue
            script = json.loads(ep["script_json"] or "{}")
            paths = json.loads(ep["paths_json"] or "{}")
            duration = float(paths.get("duration_sec") or 0)
            if not duration:
                d = Path(paths.get("video", "")).parent / "render_meta.json"
                if d.exists():
                    try:
                        duration = float(json.loads(d.read_text()).get("duration_sec") or 0)
                    except Exception:
                        duration = 0.0
            feats = extract_features(script, duration)
            views = max(1, m["views"])
            retention = (m["avg_watch"] / duration) if duration else 0.0
            engagement = (m["likes"] + 2 * m["comments"] + 3 * m["shares"]) / views
            rows.append({
                "episode_id": ep["id"],
                "features": {**feats, "hook_variant": m["hook_variant"] or script.get("hook_variant") or "unset"},
                "metrics": {"views": m["views"], "avg_watch": m["avg_watch"],
                            "likes": m["likes"], "comments": m["comments"],
                            "shares": m["shares"]},
                "retention": round(min(1.5, retention), 3),
                "retention_3s": round(m["retention_3s"] / 100, 3) if m["retention_3s"] is not None else None,
                "engagement": round(engagement, 4),
                # skor gabungan: retensi dominan, engagement sebagai penyeimbang
                "score": round(0.7 * min(1.5, retention) + 0.3 * min(0.3, engagement) * 3.33, 3),
                "hook": script.get("hook", ""),
                "title": script.get("title", ""),
            })
    return rows


def _group(rows: list[dict], key: str) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[str(r["features"].get(key))].append(r)
    out = []
    for value, items in buckets.items():
        n = len(items)
        out.append({
            "value": value, "n": n,
            "avg_retention": round(sum(i["retention"] for i in items) / n, 3),
            "avg_retention_3s": (round(sum(i["retention_3s"] for i in items if i.get("retention_3s") is not None) /
                                     max(1,sum(i.get("retention_3s") is not None for i in items)),3)
                                if any(i.get("retention_3s") is not None for i in items) else None),
            "avg_views": round(sum(i["metrics"]["views"] for i in items) / n),
            "avg_score": round(sum(i["score"] for i in items) / n, 3),
            "confident": n >= MIN_SAMPLES,
        })
    return sorted(out, key=lambda x: x["avg_score"], reverse=True)


def report() -> dict:
    rows = collect_dataset()
    if not rows:
        return {"n": 0, "ready": False,
                "message": "belum ada video dengan metrik. Catat dulu: "
                           "python -m src.cli metrics <ep> --views N --avg-watch S --likes N",
                "insights": [], "best_hooks": []}

    overall = {
        "n": len(rows),
        "avg_retention": round(sum(r["retention"] for r in rows) / len(rows), 3),
        "avg_views": round(sum(r["metrics"]["views"] for r in rows) / len(rows)),
        "avg_engagement": round(sum(r["engagement"] for r in rows) / len(rows), 4),
    }
    dims = {k: _group(rows, k) for k in
            ("hook_type", "hook_variant", "hook_words", "primary_visual", "visual_variety", "n_beats", "theme")}

    best_hooks = sorted(rows, key=lambda r: r["retention_3s"] if r.get("retention_3s") is not None else r["score"], reverse=True)[:5]
    insights = _insights(dims, overall, len(rows))
    return {"n": len(rows), "ready": len(rows) >= MIN_SAMPLES, "overall": overall,
            "dimensions": dims, "best_hooks": best_hooks, "insights": insights}


def _insights(dims: dict, overall: dict, n: int) -> list[str]:
    """Terjemahkan tabel jadi kalimat yang bisa langsung ditindak."""
    out: list[str] = []
    if n < MIN_SAMPLES:
        out.append(f"Data masih {n} video (minimum {MIN_SAMPLES}). Belum bisa menyimpulkan "
                   f"pola; produksi lebih banyak dulu.")
        return out

    base = overall["avg_retention"] or 0.001
    for dim, label in (("hook_type", "tipe hook"), ("primary_visual", "visual utama"),
                       ("n_beats", "jumlah beat")):
        groups = [g for g in dims.get(dim, []) if g["confident"]]
        if len(groups) < 2:
            continue
        best, worst = groups[0], groups[-1]
        if best["avg_retention"] > base * 1.08:
            out.append(f"{label} '{best['value']}' menahan penonton lebih lama "
                       f"({best['avg_retention']:.0%} vs rata-rata {base:.0%}, n={best['n']}).")
        if worst["avg_retention"] < base * 0.85:
            out.append(f"{label} '{worst['value']}' paling cepat ditinggalkan "
                       f"({worst['avg_retention']:.0%}, n={worst['n']}).")
    if overall["avg_retention"] < 0.35:
        out.append("Retensi rata-rata masih di bawah 35% — masalahnya hampir selalu di 3 detik "
                   "pertama, bukan di isi.")
    return out


def prompt_block(max_items: int = 5) -> str:
    """Blok teks untuk disuntik ke prompt scriptwriter."""
    r = report()
    if not r.get("ready"):
        return ""
    lines = ["POLA YANG TERBUKTI DI KANAL INI (observasional, bukan bukti sebab-akibat):"]
    base = r["overall"]["avg_retention"] or 0.001
    added = 0
    for dim, label in (("hook_type", "tipe hook"), ("primary_visual", "visual utama"),
                       ("n_beats", "jumlah beat"), ("hook_words", "panjang hook")):
        groups = r["dimensions"].get(dim, [])
        if len(groups) < 2:      # tidak ada variasi -> bukan pola, cuma kebetulan
            continue
        for g in groups:
            if not g["confident"] or g["avg_retention"] < base:
                continue
            lines.append(f"- {label} '{g['value']}': retensi {g['avg_retention']:.0%} "
                         f"(n={g['n']})")
            added += 1
            if added >= max_items:
                break
        if added >= max_items:
            break
    for i in r.get("insights", []):
        lines.append(f"- {i}")
    lines.append("Sampel kecil dan bukan uji acak. Jangan menganggap pola sebagai sebab-akibat.")
    return "\n".join(lines) if added else ""


# ---------------------------------------------------------------- tulis balik

def apply_insights(cfg: dict) -> dict:
    """Simpan pola pemenang ke file, supaya bisa dibaca agent & dashboard."""
    block = prompt_block()
    p = Path(cfg["_root"]) / "data" / "winning_patterns.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(block or "(belum ada data metrik yang cukup)\n", encoding="utf-8")
    _best_effort_github_sync_patterns()
    return {"path": str(p), "chars": len(block), "has_patterns": bool(block)}


def _best_effort_github_sync_patterns() -> None:
    """Sinkronkan pola pemenang ke repo GitHub terpusat bila MARU_GITHUB_SYNC_ENABLED aktif."""
    try:
        import sys as _sys

        repo_root = Path(__file__).resolve().parents[2]
        if not (repo_root / "maru_github_sync").is_dir():
            return
        if str(repo_root) not in _sys.path:
            _sys.path.insert(0, str(repo_root))
        from maru_github_sync import GitHubSyncConfig, MaruGitHubSyncService

        gcfg = GitHubSyncConfig.from_env(repo_root=repo_root)
        svc = MaruGitHubSyncService(gcfg)
        svc.export_local_to_central()
        if gcfg.is_ready:
            svc.best_effort_push_single(
                "skills/learned/social_media_winning_patterns.md", commit_label="social-learning"
            )
    except Exception:
        pass


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(report(), ensure_ascii=False, indent=2)[:2500])
