"""Test radar, learning, antrean, caption, publish, dan DB."""

import pytest

from src import captions as cap
from src import db, learning, queue


# ---------------------------------------------------------------- trend radar

def test_relevance_membuang_topik_non_ai():
    from src.trend_radar import relevance

    rel, hits = relevance("Melbourne Victory vs CC Mariners", {})
    assert rel == 0.0 and hits == []
    rel2, hits2 = relevance("New open source LLM runs on-device", {})
    assert rel2 > 0.5 and hits2


def test_format_fit_mendeteksi_petunjuk():
    from src.trend_radar import format_fit

    high, _ = format_fit("How a 1.5B model runs on your phone")
    low, _ = format_fit("Company announces quarterly update")
    assert high > low


def test_scoring_dan_clustering():
    from src.trend_radar import cluster, score_signals
    from src.trend_radar import _h

    signals = [
        {"source": "github", "title": "on-device LLM agent for android", "url": "https://a/1",
         "raw_score": 900, "meta": {}, "hash": _h("on-device LLM agent for android")},
        {"source": "huggingface", "title": "Qwen3.8-1.7B tiny model", "url": "https://a/2",
         "raw_score": 300, "meta": {}, "hash": _h("Qwen3.8-1.7B tiny model")},
        {"source": "google_trends_id", "title": "Trending di Indonesia: club america",
         "url": "https://a/3", "raw_score": 500, "meta": {}, "hash": _h("x")},
    ]
    weights = {"relevance": 0.35, "momentum": 0.25, "novelty": 0.25, "format_fit": 0.15}
    scored = score_signals(signals, seen=set(), weights=weights, min_score=0.3)
    assert all("bola" not in s["title"].lower() for s in scored)  # non-AI dibuang
    cl = cluster(scored, threshold=0.5)
    assert len(cl) >= 1
    assert all(c["score"] > 0 for c in cl)


def test_classify_theme_prioritas_judul():
    from src.trend_radar import classify_theme

    # model 1T dengan tag gguf bukan tema "on-device"
    theme, _ = classify_theme("Model AI baru: Mistral-Large-4-1T-A52B", {"tags": ["gguf"]})
    assert theme != "on_device"


# ---------------------------------------------------------------- captions

def test_group_lines_membatasi_kata():
    words = [cap.Word(f"kata{i}", i * 0.4, i * 0.4 + 0.35) for i in range(12)]
    groups = cap.group_lines(words, max_words=3, max_chars=40)
    assert all(len(g) <= 3 for g in groups)
    assert sum(len(g) for g in groups) == 12


def test_ass_timestamp_dan_offset(tmp_path):
    w = [cap.Word("halo", 0.0, 0.4), cap.Word("dunia", 0.4, 0.8)]
    scenes = [w, [cap.Word("lagi", 0.0, 0.3)]]   # fungsi melakukan grouping sendiri
    p = cap.captions_for_scenes(scenes, durations=[0.8, 0.3], path=tmp_path / "c.ass")
    text = p.read_text(encoding="utf-8")
    assert "[Events]" in text
    assert "Dialogue:" in text
    # scene kedua harus tergeser >= 0.8s
    starts = [float(x.split(":")[-1]) for x in
              [ln.split(",")[1] for ln in text.splitlines() if ln.startswith("Dialogue:")]]
    assert max(starts) >= 0.8


def test_caption_kata_aktif_di_highlight(tmp_path):
    w = [cap.Word("satu", 0.0, 0.4), cap.Word("dua", 0.4, 0.8)]
    p = cap.build_ass([cap.group_lines(w)], tmp_path / "h.ass", style="word")
    assert "&H005CE2FF" in p.read_text(encoding="utf-8")


# ---------------------------------------------------------------- learning

def _episode(i, question, retention, db_ok=True):
    hook = "Kenapa AI bisa jalan di HP?" if question else "AI jalan di HP."
    script = {
        "title": f"ep {i}", "hook": hook, "theme": "on_device", "format": "satu_konsep",
        "beats": [
            {"kind": "hook", "narration": hook, "body": "x", "source_refs": [],
             "visual": {"type": "card", "props": {}}},
            {"kind": "point", "narration": "a", "body": "y", "source_refs": [0],
             "visual": ({"type": "diagram", "props": {"nodes": [{"title": "a"}, {"title": "b"}]}}
                        if question else {"type": "card", "props": {}})},
            {"kind": "limit", "narration": "b", "body": "z", "source_refs": [0],
             "visual": {"type": "steps", "props": {"items": [{"title": "a"}]}}},
            {"kind": "cta", "narration": "c", "body": "w", "source_refs": [],
             "visual": {"type": "quote", "props": {"text": "t"}}},
        ],
        "caption": "c", "hashtags": ["#AI"],
        "sources": [{"title": "s", "url": "https://example.com/a"}],
    }
    db.save_episode(f"ep-test-{i}", "published", {"theme": "on_device"}, script,
                    {"duration_sec": 40})
    db.save_metrics(f"ep-test-{i}", {"views": 1000, "avg_watch": retention * 40,
                                     "likes": 50, "comments": 5, "shares": 2})


def test_learning_butuh_minimal_sampel(fresh_db):
    _episode(0, True, 0.6)
    _episode(1, False, 0.3)
    r = learning.report()
    assert r["n"] == 2
    assert r["ready"] is False            # < MIN_SAMPLES
    assert learning.prompt_block() == ""  # tidak menyimpulkan dari 2 video


def test_learning_menemukan_pola(fresh_db):
    for i in range(6):
        _episode(i, i % 2 == 0, 0.55 if i % 2 == 0 else 0.3)
    r = learning.report()
    assert r["ready"] is True
    hook_groups = {g["value"]: g for g in r["dimensions"]["hook_type"]}
    assert hook_groups["pertanyaan"]["avg_retention"] > hook_groups["pernyataan"]["avg_retention"]
    block = learning.prompt_block()
    assert "POLA YANG TERBUKTI" in block and "pertanyaan" in block


def test_extract_features():
    f = learning.extract_features({"hook": "Kenapa ini penting?", "beats": [
        {"visual": {"type": "diagram"}}, {"visual": {"type": "stat"}}]})
    assert f["hook_type"] == "pertanyaan" and f["has_diagram"] and f["has_stat"]
    assert f["visual_variety"] == 2


# ---------------------------------------------------------------- queue

def test_queue_klaim_atomik(fresh_db):
    jid = queue.enqueue("scan")
    job = queue.claim()
    assert job["id"] == jid and job["status"] == "running"
    assert queue.claim() is None          # tidak boleh diklaim dua kali
    queue.finish(jid, True, {"ok": 1})
    assert queue.pending_count() == 0


def test_queue_retry_lalu_gagal(fresh_db):
    queue.enqueue("render", "ep-x", max_attempts=2)
    job = queue.claim()
    assert queue.retry_or_fail(job, "gagal pertama") == "retry"
    assert queue.claim() is None
    job2 = queue.claim(now=__import__("time").time() + 6)
    assert job2["attempts"] == 2
    assert queue.retry_or_fail(job2, "gagal kedua") == "failed"
    jobs = queue.list_jobs()
    assert jobs[0]["status"] == "failed"


# ---------------------------------------------------------------- publish

def test_package_manual_lengkap(fresh_db, tmp_path, monkeypatch, cfg):
    import src.publish as pub

    ep = "ep-test-pkg"
    d = tmp_path / ep
    d.mkdir()
    (d / "final.mp4").write_bytes(b"x" * 2048)
    (d / "cover.png").write_bytes(b"y" * 512)
    monkeypatch.setattr(pub, "out_dir", lambda _id: d)

    script = {"caption": "coba", "hashtags": ["#AI", "#test"],
              "sources": [{"title": "s", "url": "https://a.b/c"}]}
    pkg = pub.build_package(ep, script, cfg)
    assert (d / "publish" / "video.mp4").exists()
    assert (d / "publish" / "caption.txt").exists()
    assert "Siap upload" in (d / "publish" / "SIAP_UPLOAD.md").read_text(encoding="utf-8")
    assert "AI" in pkg["full_caption"]


def test_caption_dipotong_2200(fresh_db, tmp_path, monkeypatch, cfg):
    import src.publish as pub

    ep = "ep-long"
    d = tmp_path / ep
    d.mkdir()
    monkeypatch.setattr(pub, "out_dir", lambda _id: d)
    pkg = pub.build_package(ep, {"caption": "a" * 5000, "hashtags": [], "sources": []}, cfg)
    assert len(pkg["full_caption"]) <= pub.MAX_CAPTION


# ---------------------------------------------------------------- db

def test_episode_roundtrip(fresh_db):
    script = {"title": "t", "hook": "h", "beats": [], "caption": "c", "sources": []}
    db.save_episode("ep-r", "draft", {"theme": "x"}, script, {"a": 1})
    ep = db.get_episode("ep-r")
    assert ep["script"]["title"] == "t" and ep["paths"]["a"] == 1
    db.set_status("ep-r", "approved")
    assert db.get_episode("ep-r")["status"] == "approved"


def test_status_tidak_dikenal_ditolak(fresh_db):
    db.save_episode("ep-s", "draft", {}, {})
    with pytest.raises(ValueError):
        db.set_status("ep-s", "status_ngawur")
