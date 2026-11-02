"""Test untuk modul baru: providers, revisor, trends_tiktok, audio, manim, watch."""

import numpy as np

from src import audio, providers, revisor, trends_tiktok


# ---------------------------------------------------------------- providers

def test_classify_error():
    assert providers._classify(401, "") == "unauthorized"
    assert providers._classify(403, "") == "unauthorized"
    assert providers._classify(404, "") == "not_found"
    assert providers._classify(429, "") == "rate_limited"
    assert providers._classify(400, "insufficient user quota") == "quota"
    assert providers._classify(500, "") == "server_error"
    assert providers._classify(None, "") == "unknown"


def test_probe_endpoint_mati_jujur():
    r = providers.probe_model("http://127.0.0.1:59999/v1", "", "x/model", timeout=2)
    assert r["status"] in ("unreachable", "timeout")


def test_check_all_endpoint_mati_tidak_bohong():
    out = providers.check_all("http://127.0.0.1:59999/v1", "", models=["a/b"], persist=False,
                              verbose=False)
    assert out["reachable"] is False
    assert out["results"][0]["status"] == "unreachable"
    assert out["recommend"]["strong"] is None
    assert "9Router" in providers.env_snippet(out["recommend"])


def test_recommend_pilih_yang_hidup():
    results = [
        {"model": "kr/claude-sonnet-4.5", "status": "ok", "latency_ms": 900, "error": ""},
        {"model": "gemini/gemini-2.5-flash-lite", "status": "ok", "latency_ms": 120, "error": ""},
        {"model": "kr/gpt-5.6-terra", "status": "quota", "latency_ms": 50, "error": "quota"},
    ]
    rec = providers.recommend(results, [])
    assert rec["strong"] == "kr/claude-sonnet-4.5"
    assert rec["cheap"] == "gemini/gemini-2.5-flash-lite"


def test_kandidat_memuat_model_dari_dashboard():
    semua = [m for g in providers.CANDIDATES.values() for m in g]
    for wajib in ("kr/claude-sonnet-4.5", "oc/big-pickle", "nvidia/deepseek-ai/deepseek-v4-flash",
                  "gemini/gemini-2.5-flash", "cf/@cf/meta/llama-3.2-3b-instruct",
                  "ollama/qwen3.5", "ps/poolside/laguna-s-2.1"):
        assert wajib in semua


# ---------------------------------------------------------------- revisor

def _seed(fresh_db, cfg):
    script = {
        "title": "t", "hook": "Ada satu hal di dunia AI yang minggu ini muncul terus.",
        "theme": "on_device", "format": "satu_konsep", "generator": "template",
        "beats": [
            {"kind": "hook", "narration": "Ada satu hal di dunia AI yang minggu ini muncul terus.",
             "headline": "Minggu ini di AI", "body": "b", "source_refs": [],
             "visual": {"type": "card", "props": {}}},
            {"kind": "point", "narration": "Model kecil sekarang bisa jalan di HP tanpa internet.",
             "headline": "Buktinya", "body": "b", "source_refs": [0],
             "visual": {"type": "card", "props": {}}},
            {"kind": "limit", "narration": "Tapi nalar panjangnya masih lemah.",
             "headline": "Batasnya", "body": "b", "source_refs": [0],
             "visual": {"type": "steps", "props": {"items": [{"title": "a"}]}}},
            {"kind": "cta", "narration": "Follow buat satu konsep tiap hari.",
             "headline": "Follow", "body": "b", "source_refs": [],
             "visual": {"type": "quote", "props": {"text": "t"}}},
        ],
        "caption": "caption awal", "hashtags": ["#AI"],
        "sources": [{"title": "s", "url": "https://example.com/a"}],
    }
    from src import db

    db.save_episode("ep-r", "pending_approval", {"theme": "on_device"}, script, {})
    return "ep-r"


def test_revisi_hook_pendek_tidak_menggantung(fresh_db, cfg):
    ep = _seed(fresh_db, cfg)
    res = revisor.apply_revision(ep, "hook", "Pendekkan hook maksimal 8 kata", cfg)
    assert res["ok"]
    hook = res["after"]["hook"]
    assert len(hook.split()) <= 8
    assert not hook.rstrip("?").lower().endswith(("yang", "di", "dan"))


def test_revisi_dicatat_di_riwayat(fresh_db, cfg):
    ep = _seed(fresh_db, cfg)
    revisor.apply_revision(ep, "hook", "pendek", cfg)
    revisor.apply_revision(ep, "caption", "tambah pertanyaan", cfg)
    h = revisor.history(ep)
    assert len(h) == 2
    assert {x["aspect"] for x in h} == {"hook", "caption"}
    assert all(x["status"] in ("applied", "invalid") for x in h)


def test_revisi_aspek_tidak_dikenal(fresh_db, cfg):
    ep = _seed(fresh_db, cfg)
    res = revisor.apply_revision(ep, "warna", "x", cfg)
    assert res["ok"] is False and "aspek tidak dikenal" in res["error"]


def test_revisi_visual_membuat_variasi(fresh_db, cfg):
    ep = _seed(fresh_db, cfg)
    res = revisor.apply_revision(ep, "visual", "buat lebih variatif", cfg)
    tipe = [b["visual"]["type"] for b in res["script"]["beats"]]
    assert len(set(tipe)) >= 3


def test_revisi_menjaga_sumber_tetap_ada(fresh_db, cfg):
    ep = _seed(fresh_db, cfg)
    res = revisor.apply_revision(ep, "sources", "tambah sumber", cfg)
    assert res["script"]["sources"], "sumber tidak boleh hilang karena revisi"


def test_shortcut_semua_valid():
    for name, (aspect, instr) in revisor.SHORTCUTS.items():
        assert aspect in revisor.ASPECTS, name
        assert instr, name


# ---------------------------------------------------------------- trends_tiktok

TRANSCRIPT = ("Kamu mungkin salah paham soal AI di HP. Banyak yang bilang AI cuma bisa jalan "
              "di server besar. Padahal model kecil bisa jalan di ponsel. Caranya dipadatkan. "
              "Tapi ada batasnya.")


def test_analyze_heuristic_tanpa_llm(cfg):
    pat = trends_tiktok.analyze_reference({"title": "", "author": "x"}, TRANSCRIPT, None)
    assert pat["analyzed_by"] == "heuristic"
    assert pat["hook"]["type"] in ("pertanyaan", "negasi", "pernyataan", "angka")
    assert pat["must_not_copy"], "harus menyebut apa yang tidak boleh ditiru"


def test_fetch_reference_platform_tidak_didukung():
    r = trends_tiktok.fetch_reference("https://example.com/video/1")
    assert "error" in r


def test_compliance_menolak_salinan_mentah(cfg):
    salinan = {"hook": TRANSCRIPT, "beats": [{"narration": TRANSCRIPT}],
               "sources": [{"title": "s", "url": "https://a.b"}]}
    res = trends_tiktok.compliance_check(salinan, reference_text=TRANSCRIPT)
    assert res["passed"] is False
    assert "kemiripan_teks" in res["failed"]


def test_compliance_menerima_hasil_transformasi(fresh_db, cfg, cluster):
    spec = {"topic": cluster["label"], "angle": "a",
            "hook_draft": "Kenapa AI kecil bisa jalan di kantong?",
            "beat_plan": [], "inherited_from_pattern": {"hook_type": "pertanyaan"},
            "transformation_rules": [], "reference": {"title": "ref", "author": "orang"}}
    script = trends_tiktok.transform_spec(spec, cluster, cfg)
    res = trends_tiktok.compliance_check(script, reference_text=TRANSCRIPT)
    assert res["passed"], res["failed"]
    assert script["transformation"]["reference_author"] == "orang"


# ---------------------------------------------------------------- audio

def test_music_bed_menghasilkan_audio_berisi(tmp_path):
    p = audio.music_bed(3.0, style="tech", out=tmp_path / "m.wav")
    import wave

    with wave.open(str(p)) as w:
        assert w.getframerate() == audio.SR
        n = w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768
    assert n > audio.SR * 2.5
    assert 0.02 < float(np.sqrt(np.mean(x ** 2))) < 0.9   # bukan hening, bukan clipping
    assert float(np.max(np.abs(x))) <= 1.0


def test_sfx_semua_tipe(tmp_path):
    for name in ("whoosh", "pop", "riser"):
        p = audio.sfx(name, out=tmp_path / f"{name}.wav")
        assert p.exists() and p.stat().st_size > 1000


def test_mix_ducking_menekan_musik(tmp_path):
    """Bukti ducking: energi musik turun saat ada suara, dibanding tanpa ducking."""
    import wave

    sr, n = audio.SR, audio.SR * 4
    t = np.arange(n) / sr
    voice = np.zeros(n, dtype=np.float32)
    voice[: int(1.5 * sr)] = (0.3 * np.sin(2 * np.pi * 180 * t[: int(1.5 * sr)])).astype(np.float32)
    audio._write_wav(voice, tmp_path / "v.wav")
    audio._write_wav((0.4 * np.sin(2 * np.pi * 3500 * t)).astype(np.float32), tmp_path / "m.wav")

    def band(path, s, e, f0=3500.0):
        with wave.open(str(path)) as w:
            w.setpos(int(s * sr))
            x = np.frombuffer(w.readframes(int((e - s) * sr)), dtype="<i2").astype(np.float32)
        spec = np.abs(np.fft.rfft(x))
        freqs = np.fft.rfftfreq(len(x), 1 / sr)
        i = int(np.argmin(np.abs(freqs - f0)))
        return float(spec[max(0, i - 3): i + 4].sum())

    out = audio.mix(tmp_path / "v.wav", tmp_path / "duck.wav", tmp_path / "m.wav",
                    [], music_db=-6, duck=True)
    a, b = band(out, 0.4, 1.4), band(out, 2.2, 3.2)
    assert b > a * 1.5, f"musik tidak ditekan saat ada suara (voice={a:.0f}, hening={b:.0f})"


def test_musik_bed_terdengar_pada_level_config(tmp_path):
    """Regresi: `music_db: -23` membuat musik praktis tidak terdengar (RMS ~0,004).

    Musik harus berada ~10-25 dB di bawah narasi: cukup terdengar sebagai
    alas, tapi tidak menabrak suara. Kalau test ini gagal, cek `music_db`
    di config/config.yaml.
    """
    import wave

    from src.config import load_config

    sr = audio.SR
    t = np.arange(sr * 6) / sr
    voice = np.zeros(len(t), dtype=np.float32)                       # hening total
    voice[: sr] = (0.3 * np.sin(2 * np.pi * 180 * t[:sr])).astype(np.float32)
    audio._write_wav(voice, tmp_path / "v.wav")
    audio._write_wav((0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32), tmp_path / "m.wav")

    db = float(load_config()["video"]["music_db"])
    out = audio.mix(tmp_path / "v.wav", tmp_path / "o.wav", tmp_path / "m.wav", [], music_db=db)

    with wave.open(str(out)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    narrative = float(np.sqrt(np.mean(x[: sr] ** 2)))
    bed = float(np.sqrt(np.mean(x[sr * 3: sr * 5] ** 2)))
    ratio_db = 20 * np.log10(max(bed, 1e-9) / max(narrative, 1e-9))
    assert -30 < ratio_db < -8, (
        f"musik {ratio_db:.1f} dB terhadap narasi (music_db={db}); "
        f"target -25..-10 dB supaya terdengar tapi tidak menimpa suara"
    )


def test_mix_tanpa_musik_tetap_jalan(tmp_path):
    import wave

    sr = audio.SR
    audio._write_wav((0.2 * np.sin(2 * np.pi * 200 * np.arange(sr) / sr)).astype(np.float32),
                     tmp_path / "v.wav")
    out = audio.mix(tmp_path / "v.wav", tmp_path / "o.wav")
    with wave.open(str(out)) as w:
        assert w.getnframes() > sr * 0.8


def test_bed_style_otomatis_dari_tema(tmp_path):
    assert audio.bed_for_episode(3, tmp_path, theme="on_device").name == "music_tech.wav"
    assert audio.bed_for_episode(3, tmp_path, theme="safety").name == "music_calm.wav"


# ---------------------------------------------------------------- manim

def test_manim_scene_file_dibangun_valid(tmp_path):
    from src import manim_scene

    spec = {"type": "diagram", "nodes": [{"title": "A", "sub": ""}, {"title": "B", "sub": ""}]}
    p = manim_scene.build_scene_file(spec, tmp_path / "s.py", "#5eead4", 5.0)
    src = p.read_text(encoding="utf-8")
    assert "class EpisodeScene(Scene)" in src
    assert "__T_IN__" not in src and "__SPEC__" not in src
    compile(src, str(p), "exec")  # sintaks Python valid


def test_manim_spec_eksplisit_dan_implisit():
    from src.visuals import Ctx, manim_spec

    cfg = {"brand": {}}
    a = Ctx(beat={"visual": {"type": "manim", "props": {"scene": "bars",
                                                       "items": [{"label": "x", "value": 1}]}}},
            idx=0, total=1, cfg=cfg)
    assert manim_spec(a)["type"] == "bars" and manim_spec(a)["items"]

    b = Ctx(beat={"visual": {"type": "diagram", "props": {"nodes": [{"title": "a"}]}}},
            idx=0, total=1, cfg=cfg)
    assert manim_spec(b)["type"] == "diagram"


def test_wants_manim_mode(tmp_path):
    from src.visuals import Ctx, wants_manim

    beat = {"kind": "point", "visual": {"type": "diagram", "props": {"nodes": []}}}
    ctx = Ctx(beat=beat, idx=1, total=3, cfg={})
    assert wants_manim(ctx, {"video": {"animator": "pillow"}}) is False
    assert wants_manim(ctx, {"video": {"animator": "auto"}}) is True
    assert wants_manim(ctx, {"video": {"animator": "manim"}}) is True


# ---------------------------------------------------------------- watch

def test_watch_due_logic():
    from src.watch import _due

    assert _due({"last_cycle": None}, 6) is True
    from datetime import datetime, timedelta

    assert _due({"last_cycle": datetime.now().isoformat()}, 6) is False
    old = (datetime.now() - timedelta(hours=7)).isoformat()
    assert _due({"last_cycle": old}, 6) is True


def test_watch_cycle_menghormati_batas_acc(fresh_db, cfg):
    """Kalau sudah ada 2 episode menunggu ACC, jangan bikin lagi."""
    from src import db, watch

    for i in range(2):
        db.save_episode(f"ep-w{i}", "pending_approval", {}, {"title": "t", "beats": []}, {})
    res = watch.cycle(cfg)
    assert res["action"] == "skip"
    assert res["waiting"] >= 2
