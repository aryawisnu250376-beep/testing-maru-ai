"""Antrean JSON bersama untuk kerangka 4 bot.

Satu file per konten di `antrean/<id>.json`. MausBot/dashboard hanya menampilkan
dan menerima keputusan pemilik; Hermes hanya boleh menulis DRAF/MENUNGGU/REVISI;
Ootto satu-satunya yang boleh mengubah DISETUJUI -> TERJADWAL/TAYANG/GAGAL.
Semua perubahan dicatat dengan waktu, pelaku, dan alasan.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import ROOT

QUEUE_DIR = Path(os.getenv("ANTREAN_DIR", str(ROOT / "antrean")))
LOG_PATH = Path(os.getenv("AKTIVITAS_LOG", str(ROOT / "log" / "aktivitas.log")))
TZ = ZoneInfo(os.getenv("ZONA_WAKTU", "Asia/Jakarta"))
_LOCK = threading.RLock()

STATUSES = (
    "DRAF", "MENUNGGU", "DISETUJUI", "DITOLAK", "REVISI",
    "TERJADWAL", "TAYANG", "GAGAL", "DRAF_TIKTOK",
)
# Pelaku -> status yang boleh ditulis. Pemilik adalah satu-satunya pemberi ACC.
ALLOWED = {
    "hermes": {"DRAF", "MENUNGGU", "REVISI"},
    "pemilik": {"DISETUJUI", "DITOLAK", "REVISI", "MENUNGGU"},
    "ootto": {"TERJADWAL", "TAYANG", "GAGAL", "DRAF_TIKTOK", "DISETUJUI"},
    "mausbot": {"MENUNGGU"},
}
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _path(content_id: str) -> Path:
    if not SAFE_ID.fullmatch(content_id or ""):
        raise ValueError("ID konten tidak valid")
    return QUEUE_DIR / f"{content_id}.json"


def _atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".queue-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def log(actor: str, content_id: str, action: str, reason: str = "") -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"waktu": now(), "pelaku": actor, "id": content_id,
                       "aksi": action, "alasan": reason[:500]}, ensure_ascii=False)
    with _LOCK, LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def get(content_id: str) -> dict | None:
    p = _path(content_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_items(status: str | None = None) -> list[dict]:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(QUEUE_DIR.glob("*.json")):
        try:
            item = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and item.get("status") != status:
            continue
        out.append(item)
    return sorted(out, key=lambda x: x.get("dibuat", ""), reverse=True)


def create(content_id: str, judul: str, *, naskah: str = "", caption: str = "",
           usulan_jam: str = "", alasan_jam: str = "", sumber: list | None = None,
           video: str = "", episode_id: str = "", actor: str = "hermes") -> dict:
    if actor not in ("hermes", "mausbot"):
        raise PermissionError("Hanya Hermes/MausBot yang membuat draf awal")
    if get(content_id):
        raise ValueError("ID konten sudah ada")
    item = {
        "id": content_id, "judul": judul[:120], "naskah": naskah, "caption": caption,
        "usulan_jam": usulan_jam, "alasan_jam": alasan_jam, "sumber": sumber or [],
        "video": video, "episode_id": episode_id, "status": "DRAF",
        "dibuat": now(), "diubah": now(), "riwayat": [],
        "label_ai": True, "mode_tiktok": os.getenv("OOTTO_MODE", "draft"),
    }
    with _LOCK:
        _atomic(_path(content_id), item)
        log(actor, content_id, "buat_draf")
    return item


def transition(content_id: str, status: str, actor: str, reason: str = "",
               **fields) -> dict:
    if status not in STATUSES:
        raise ValueError(f"Status tidak dikenal: {status}")
    if actor not in ALLOWED or status not in ALLOWED[actor]:
        log(actor, content_id, "ditolak", f"tidak boleh menulis {status}")
        raise PermissionError(f"{actor} tidak boleh mengubah status menjadi {status}")
    with _LOCK:
        item = get(content_id)
        if not item:
            raise ValueError("Konten tidak ditemukan")
        old = item.get("status")
        # Tidak ada lompatan dari draf/liar langsung ke tayang.
        if status in ("TERJADWAL", "TAYANG", "DRAF_TIKTOK") and old not in ("DISETUJUI", "TERJADWAL"):
            raise PermissionError("Ootto hanya memproses konten DISETUJUI")
        if actor == "ootto" and status == "DISETUJUI" and old != "TERJADWAL":
            raise PermissionError("Ootto tidak boleh memberi ACC")
        if actor == "pemilik" and status == "DISETUJUI" and old not in ("DRAF", "MENUNGGU", "REVISI", "DISETUJUI"):
            raise PermissionError("Hanya draf menunggu yang dapat disetujui")
        item.update({k: v for k, v in fields.items() if k in (
            "naskah", "caption", "usulan_jam", "alasan_jam", "sumber", "video",
            "jadwal", "ootto_result", "tiktok_publish_id", "catatan_revisi", "qc_passed")})
        item["status"] = status
        item["diubah"] = now()
        item.setdefault("riwayat", []).append(
            {"dari": old, "ke": status, "waktu": now(), "pelaku": actor, "alasan": reason[:500]})
        _atomic(_path(content_id), item)
        log(actor, content_id, f"{old}->{status}", reason)
    return item


def owner_decision(content_id: str, decision: str, reason: str = "",
                   jadwal: str | None = None) -> dict:
    decision = decision.upper()
    mapping = {"SETUJU": "DISETUJUI", "TOLAK": "DITOLAK", "REVISI": "REVISI"}
    if decision not in mapping:
        raise ValueError("Keputusan harus SETUJU, TOLAK, atau REVISI")
    fields = {}
    if decision == "SETUJU":
        if jadwal:
            fields["jadwal"] = jadwal
        fields["disetujui_pada"] = now()
    if decision == "REVISI":
        fields["catatan_revisi"] = reason
    return transition(content_id, mapping[decision], "pemilik", reason, **fields)
