"""Aturan editorial: yang boleh lolos ke render dan yang harus ditolak."""

from src import scriptwriter as sw


def base_script(cluster):
    return {
        "title": "Model AI baru: X",
        "format": "satu_konsep",
        "hook": "AI paling berguna tahun ini nggak ada di server.",
        "beats": [
            {"kind": "hook", "narration": "AI paling berguna tahun ini nggak ada di server.",
             "headline": "Bukan di server", "body": "Muat di HP.",
             "source_refs": [], "visual": {"type": "card", "props": {}}},
            {"kind": "point", "narration": "Model kecil sekarang bisa jalan di HP tanpa internet.",
             "headline": "Buktinya ada", "body": "Model 1,7B jalan di HP.",
             "source_refs": [0, 1],
             "visual": {"type": "diagram", "props": {"nodes": [{"title": "a"}, {"title": "b"}]}}},
            {"kind": "limit", "narration": "Tapi nalar panjangnya masih lemah.",
             "headline": "Batasnya nyata", "body": "Lemah di nalar panjang.",
             "source_refs": [1],
             "visual": {"type": "steps", "props": {"items": [{"title": "a"}]}}},
            {"kind": "cta", "narration": "Follow buat satu konsep tiap hari.",
             "headline": "Satu konsep", "body": "Follow.",
             "source_refs": [], "visual": {"type": "quote", "props": {"text": "t"}}},
        ],
        "caption": "kenapa ini penting?",
        "hashtags": ["#AI"],
        "sources": [{"title": "a", "url": "https://github.com/a/b"},
                    {"title": "b", "url": "https://huggingface.co/L/lfm3"}],
    }


def test_valid_script_lolos(cluster, cfg):
    sc = base_script(cluster)
    sc, _ = sw.sanitize(sc, cluster, cfg)
    ok, errs, warns = sw.validate_script(sc, cfg)
    assert ok, errs


def test_tanpa_sumber_ditolak(cluster, cfg):
    sc = base_script(cluster)
    sc["sources"] = []
    ok, errs, _ = sw.validate_script(sc, cfg)
    assert not ok and any("sources kosong" in e for e in errs)


def test_tanpa_beat_limit_ditolak(setup=None, **kw):
    # validator harus menolak script yang tidak menyebut batasan
    from src.config import load_config

    cfg = load_config()
    cl = {"evidence": [], "label": "x"}
    sc = base_script(cl)
    sc["beats"] = [b for b in sc["beats"] if b["kind"] != "limit"]
    ok, errs, _ = sw.validate_script(sc, cfg)
    assert not ok and any("limit" in e for e in errs)


def test_sanitize_menambah_beat_limit(cluster, cfg):
    sc = base_script(cluster)
    sc["beats"] = [b for b in sc["beats"] if b["kind"] != "limit"]
    sc, notes = sw.sanitize(sc, cluster, cfg)
    assert "limit" in [b["kind"] for b in sc["beats"]]
    assert any("limit" in n for n in notes)
    ok, errs, _ = sw.validate_script(sc, cfg)
    assert ok, errs


def test_sanitize_tidak_memotong_klaim_faktual_diam_diam(cluster, cfg):
    sc = base_script(cluster)
    sc["beats"][1]["narration"] = "kata " * 40
    sc, _ = sw.sanitize(sc, cluster, cfg)
    assert len(sc["beats"][1]["narration"].split()) == 40
    ok, errors, _ = sw.validate_script(sc, cfg)
    assert not ok and any("kata >" in e for e in errors)


def test_headline_dipotong_lima_kata(cluster, cfg):
    sc = base_script(cluster)
    sc["beats"][1]["headline"] = "satu dua tiga empat lima enam tujuh"
    sc, _ = sw.sanitize(sc, cluster, cfg)
    assert len(sc["beats"][1]["headline"].split()) <= 5


def test_kata_terlarang_ditolak(cluster, cfg):
    sc = base_script(cluster)
    sc["beats"][1]["narration"] = "Ini revolusioner banget."
    ok, errs, _ = sw.validate_script(sc, cfg)
    assert not ok and any("terlarang" in e for e in errs)


def test_sumber_dipaksa_dari_cluster(cluster, cfg):
    """Model tidak boleh mengarang URL: sumber diambil dari cluster."""
    sc = base_script(cluster)
    sc["sources"] = [{"title": "karangan", "url": "https://situs-palsu.example/x"}]
    sc, notes = sw.sanitize(sc, cluster, cfg)
    urls = {s["url"] for s in sc["sources"]}
    assert "https://situs-palsu.example/x" not in urls
    assert urls <= {e["url"] for e in cluster["evidence"]}


def test_visual_tidak_valid_diganti(cluster, cfg):
    sc = base_script(cluster)
    sc["beats"][1]["visual"] = {"type": "hologram", "props": {}}
    sc, _ = sw.sanitize(sc, cluster, cfg)
    assert sc["beats"][1]["visual"]["type"] in sw.VISUAL_TYPES


def test_visual_wajib_punya_props(cluster, cfg):
    sc = base_script(cluster)
    sc["beats"][1]["visual"] = {"type": "diagram", "props": {}}
    ok, errs, _ = sw.validate_script(sc, cfg)
    assert not ok and any("props" in e for e in errs)


def test_template_selalu_valid(cluster, cfg):
    sc = sw.write_with_template(cluster, cfg)
    sc, _ = sw.sanitize(sc, cluster, cfg)
    ok, errs, _ = sw.validate_script(sc, cfg)
    assert ok, errs
    assert sc["generator"] == "template"


def test_judul_dari_label_tema(cluster, cfg):
    sc = base_script(cluster)  # judul "Model AI baru: X" -> harus diganti
    sc, _ = sw.sanitize(sc, cluster, cfg)
    assert sc["title"] == cluster["label"][:60]
