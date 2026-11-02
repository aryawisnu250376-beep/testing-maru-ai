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
    video = Path(item.get("video") or "")
    if not video.is_file():
        raise ValueError("Video belum tersedia; render dan QC dulu")
    if not item.get("label_ai", True):
        raise ValueError("Konten AI wajib diberi label AI")
    mode = item.get("mode_tiktok") or MODE
    if mode == "direct" and not ALLOW_DIRECT:
        raise PermissionError("Mode tayang langsung belum diaktifkan pemilik")
    return queue4.transition(
        id_konten, "TERJADWAL", "ootto", "Jadwal disetujui dari antrean pemilik",
        jadwal=dt.isoformat(timespec="seconds"),
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
                             jadwal=None, ootto_result={"status": "dibatalkan"})


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
        if mode == "direct":
            if not ALLOW_DIRECT:
                raise PermissionError("Mode direct belum diaktifkan")
            result = tiktok.direct_post(item)
            new_status = "TAYANG"
        else:
            result = tiktok.upload_draft(item)
            new_status = "DRAF_TIKTOK"
        return queue4.transition(item["id"], new_status, "ootto", "Terkirim ke TikTok",
                                 ootto_result=result, tiktok_publish_id=result.get("publish_id"))
    except Exception as exc:
        queue4.log("ootto", item["id"], "gagal", str(exc))
        return queue4.transition(item["id"], "GAGAL", "ootto", str(exc)[:500],
                                 ootto_result={"status": "gagal", "error": str(exc)[:500]})


def run_due() -> list[dict]:
    return [kirim(item) for item in due_items()]
