"""Ootto — penjadwal TikTok satu pemilik.

Hanya membaca antrean bersama. Tidak menerima perintah langsung dari Hermes.
Mode bawaan: draft/inbox. Tayang langsung tidak aktif kecuali diminta pemilik
dan aplikasi TikTok sudah lolos audit yang diperlukan.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src import queue4

TZ = ZoneInfo(os.getenv("ZONA_WAKTU", "Asia/Jakarta"))
MODE = os.getenv("OOTTO_MODE", "draft").lower()
ALLOW_DIRECT = os.getenv("OOTTO_ALLOW_DIRECT", "false").lower() in ("1", "true", "yes")


def _parse_time(waktu: str) -> datetime:
    dt = datetime.fromisoformat(waktu)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def _validated_video(item: dict) -> Path:
    video = Path(item.get('video') or '')
    if not video.is_file() or item.get('qc_passed') is False:
        raise ValueError('Video belum lulus QC; render dan QC dulu')
    if item.get('verified_episode_video'):
        from src.dashboard_ops import approved_video
        if approved_video(item.get('episode_id', '')) != video.resolve():
            raise ValueError('Video tidak lagi sesuai dengan episode yang disetujui')
    return video


def jadwalkan(id_konten: str, waktu: str) -> dict:
    """Jadwalkan pengiriman lokal. Hanya konten DISETUJUI yang diterima."""
    item = queue4.get(id_konten)
    if not item:
        raise ValueError("Konten tidak ditemukan")
    if item.get("status") != "DISETUJUI":
        queue4.log("ootto", id_konten, "ditolak", f"status {item.get('status')} bukan DISETUJUI")
        raise PermissionError("Ootto hanya memproses konten DISETUJUI")
    dt = _parse_time(waktu)
    if dt <= datetime.now(TZ):
        raise ValueError("Waktu jadwal harus di masa depan")
    _validated_video(item)
    if not item.get("label_ai", True):
        raise ValueError("Konten AI wajib diberi label AI")
    mode = item.get("mode_tiktok") or MODE
    if mode == "direct" and not ALLOW_DIRECT:
        raise PermissionError("Mode tayang langsung belum diaktifkan pemilik")
    return queue4.transition(
        id_konten, "TERJADWAL", "ootto", "Jadwal disetujui dari antrean pemilik",
        expected_status="DISETUJUI", jadwal=dt.isoformat(timespec="seconds"),
        ootto_result={"mode": mode, "status": "menunggu_jadwal", "publish_id": None},
    )


def status(id_konten: str) -> dict:
    item = queue4.get(id_konten)
    if not item:
        raise ValueError("Konten tidak ditemukan")
    return {
        "id": id_konten, "status": item.get("status"), "jadwal": item.get("jadwal"),
        "mode": item.get("mode_tiktok") or MODE, "ootto_result": item.get("ootto_result"),
        "tiktok_publish_id": item.get("tiktok_publish_id"),
    }


def batalkan(id_konten: str) -> dict:
    item = queue4.get(id_konten)
    if not item:
        raise ValueError("Konten tidak ditemukan")
    if item.get("status") != "TERJADWAL":
        raise PermissionError("Hanya jadwal TERJADWAL yang dapat dibatalkan")
    res = item.get("ootto_result") or {}
    if res.get("publish_id"):
        raise PermissionError("Sudah terkirim ke TikTok; batalkan lewat aplikasi TikTok")
    return queue4.transition(id_konten, "DISETUJUI", "ootto", "Jadwal dibatalkan pemilik",
                             expected_status="TERJADWAL", jadwal=None, ootto_result={"status": "dibatalkan"})


def due_items(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(TZ)
    out = []
    for item in queue4.list_items("TERJADWAL"):
        try:
            if _parse_time(item["jadwal"]) <= now:
                out.append(item)
        except Exception:
            continue
    return out


def kirim(item: dict) -> dict:
    """Kirim satu item jatuh tempo. Dipanggil scheduler, bukan Hermes."""
    from . import tiktok
    if item.get("status") != "TERJADWAL":
        raise PermissionError("Item tidak TERJADWAL")
    mode = item.get("mode_tiktok") or MODE
    try:
        _validated_video(item)
        if mode == "direct":
            if not ALLOW_DIRECT:
                raise PermissionError("Mode direct belum diaktifkan")
            result = tiktok.direct_post(item)
            new_status = "DIKIRIM_TIKTOK"
        else:
            result = tiktok.upload_draft(item)
            new_status = "DRAF_TIKTOK"
        return queue4.transition(item["id"], new_status, "ootto", "Terkirim ke TikTok",
                                 expected_status="TERJADWAL", ootto_result=result, tiktok_publish_id=result.get("publish_id"))
    except Exception as exc:
        error = "Pengiriman gagal; tinjau konfigurasi, video, dan status TikTok sebelum mencoba lagi"
        queue4.log("ootto", item["id"], "gagal", type(exc).__name__)
        return queue4.transition(item["id"], "GAGAL", "ootto", error,
                                 expected_status="TERJADWAL", ootto_result={"status": "gagal", "error": error})


def reconcile_direct(item: dict) -> dict | None:
    """Upload acknowledgement is not publication; only the status endpoint confirms it."""
    from . import tiktok
    publish_id = item.get('tiktok_publish_id')
    if not publish_id:
        return None
    try:
        result = tiktok.post_status(publish_id)
    except (OSError, RuntimeError, ValueError):
        queue4.log('ootto', item['id'], 'konfirmasi_tertunda', 'Status TikTok tidak dapat dibaca; akan dicoba lagi')
        return None
    state = result.get('status')
    if state == 'PUBLISH_COMPLETE':
        return queue4.transition(item['id'], 'TAYANG', 'ootto', 'Publikasi dikonfirmasi TikTok',
                                 expected_status='DIKIRIM_TIKTOK', ootto_result={**(item.get('ootto_result') or {}), 'status': state})
    if state == 'FAILED':
        return queue4.transition(item['id'], 'GAGAL', 'ootto', 'TikTok melaporkan publikasi gagal',
                                 expected_status='DIKIRIM_TIKTOK', ootto_result={**(item.get('ootto_result') or {}), 'status': state})
    return None


def run_due() -> list[dict]:
    reconciled = [result for item in queue4.list_items('DIKIRIM_TIKTOK') if (result := reconcile_direct(item))]
    return reconciled + [kirim(item) for item in due_items()]
