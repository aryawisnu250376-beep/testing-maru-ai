"""Uji kerangka 4 bot: aturan persetujuan adalah jaring pengaman utama."""

import importlib
import json

import pytest

from src import queue4


@pytest.fixture()
def q(tmp_path, monkeypatch):
    monkeypatch.setattr(queue4, "QUEUE_DIR", tmp_path / "antrean")
    monkeypatch.setattr(queue4, "LOG_PATH", tmp_path / "log" / "aktivitas.log")
    return queue4


def _draft(q, cid="k-1"):
    q.create(cid, "Judul", naskah="Halo dunia.", caption="cap", actor="hermes")
    q.transition(cid, "MENUNGGU", "hermes", "siap tinjau")
    return cid


def test_hermes_tidak_bisa_setuju(q):
    cid = _draft(q)
    with pytest.raises(PermissionError):
        q.transition(cid, "DISETUJUI", "hermes", "coba acc sendiri")
    assert q.get(cid)["status"] == "MENUNGGU"


def test_hermes_tidak_bisa_memanggil_ootto_status(q):
    cid = _draft(q)
    with pytest.raises(PermissionError):
        q.transition(cid, "TERJADWAL", "hermes", "lompat")
    with pytest.raises(PermissionError):
        q.transition(cid, "TAYANG", "hermes", "lompat")


def test_ootto_menolak_non_disetujui(q):
    cid = _draft(q)
    import ootto

    with pytest.raises(PermissionError):
        ootto.jadwalkan(cid, "2030-01-01T19:00:00+07:00")
    # tercatat di log
    log = (q.LOG_PATH).read_text(encoding="utf-8")
    assert "ditolak" in log


def test_ootto_tidak_bisa_memberi_acc(q):
    cid = _draft(q)
    with pytest.raises(PermissionError):
        q.transition(cid, "DISETUJUI", "ootto", "coba acc")


def test_alur_pemilik_setuju_lalu_ootto(q, tmp_path):
    cid = _draft(q)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    q.transition(cid, "MENUNGGU", "hermes", "video siap", video=str(video))
    q.owner_decision(cid, "SETUJU", "sudah dibaca")
    assert q.get(cid)["status"] == "DISETUJUI"
    import ootto

    item = ootto.jadwalkan(cid, "2030-01-01T19:00:00+07:00")
    assert item["status"] == "TERJADWAL"
    assert ootto.status(cid)["jadwal"]
    ootto.batalkan(cid)
    assert q.get(cid)["status"] == "DISETUJUI"


def test_pemilik_tolak_dan_revisi(q):
    cid = _draft(q)
    q.owner_decision(cid, "TOLAK", "tidak sesuai")
    assert q.get(cid)["status"] == "DITOLAK"
    cid2 = _draft(q, "k-2")
    q.owner_decision(cid2, "REVISI", "perbaiki hook")
    item = q.get(cid2)
    assert item["status"] == "REVISI" and item["catatan_revisi"] == "perbaiki hook"


def test_riwayat_mencatat_pelaku_dan_alasan(q):
    cid = _draft(q)
    q.owner_decision(cid, "SETUJU", "alasan pemilik")
    hist = q.get(cid)["riwayat"]
    assert any(h["pelaku"] == "pemilik" and h["ke"] == "DISETUJUI" for h in hist)
    assert all("waktu" in h for h in hist)


def test_label_ai_wajib(q, tmp_path):
    cid = _draft(q)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    q.transition(cid, "MENUNGGU", "hermes", "v", video=str(video))
    q.owner_decision(cid, "SETUJU", "ok")
    # hapus label AI -> ootto menolak
    item = q.get(cid)
    item["label_ai"] = False
    q._atomic(q._path(cid), item)
    import ootto

    with pytest.raises(ValueError):
        ootto.jadwalkan(cid, "2030-01-01T19:00:00+07:00")


def test_ootto_waktu_harus_masa_depan(q, tmp_path):
    cid = _draft(q)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    q.transition(cid, "MENUNGGU", "hermes", "v", video=str(video))
    q.owner_decision(cid, "SETUJU", "ok")
    import ootto

    with pytest.raises(ValueError):
        ootto.jadwalkan(cid, "2020-01-01T19:00:00+07:00")


def test_cek_mutu_menandai_klaim_tanpa_sumber():
    from src import skills4

    script = {"beats": [{"narration": "Model ini mencapai 99 persen akurasi global."}]}
    source = "Bahan kuliah membahas cara kerja agent dan alat."
    qc = skills4.cek_mutu(script, source)
    assert not qc["ok"] and qc["flagged"]


def test_usul_jadwal_zona_waktu():
    from src import skills4

    out = skills4.usul_jadwal()
    assert "+07:00" in out["waktu"] and out["alasan"]


def test_router_belum_dikonfigurasi_jujur(monkeypatch):
    from src import router9

    monkeypatch.delenv("ROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    out = router9.test_question()
    assert out["ok"] is False and "belum" in out["error"].lower()


def test_frames_to_video_rgba_tidak_rusak(tmp_path):
    """Regresi: frame RGBA harus dikonversi ke rgb24 sebelum stream ke ffmpeg."""
    from PIL import Image
    from src import anim
    from src import qc
    frames = [Image.new("RGBA", (64, 64), (200, 30, 30, 255)) for _ in range(3)]
    out = tmp_path / "t.mp4"
    anim.frames_to_video(iter(frames), out, 64, 64, 24)
    info = qc.probe(out)
    assert info["width"] == 64 and info["height"] == 64 and info["codec"] == "h264"
