"""WATCH MODE — AI bekerja selama laptop menyala.

Satu proses, tiga peran:
  1. penjadwal  : menjalankan siklus sesuai `interval_hours` (default 6 jam)
  2. worker     : memproses antrean (scan → script → approval)
  3. penjaga    : berhenti sendiri kalau laptop mau tidur / sinyal dimatikan

Kenapa bukan cron saja: cron butuh hak sistem dan tidak tahu kapan laptop
dipakai. Watch mode jalan di terminal mana pun, ikut mati saat terminal ditutup,
dan menyimpan state supaya tidak mengulang siklus yang sama.

Aturan yang tetap dipegang:
  * **render tidak pernah otomatis** — selalu menunggu ACC
  * publish tidak pernah otomatis

Perintah:
  python -m src.cli watch                 # siklus tiap 6 jam
  python -m src.cli watch --interval 2    # tiap 2 jam
  python -m src.cli watch --once          # satu siklus lalu keluar
"""
from __future__ import annotations

import json
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import db, queue

STATE = Path(__file__).resolve().parents[1] / "data" / "watch_state.json"


def _now() -> datetime:
    return datetime.now()


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_cycle": None, "cycles": 0, "last_episode": None}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _due(state: dict, interval_hours: float) -> bool:
    last = state.get("last_cycle")
    if not last:
        return True
    try:
        return _now() - datetime.fromisoformat(last) >= timedelta(hours=interval_hours)
    except Exception:
        return True


def cycle(cfg: dict) -> dict:
    """Satu siklus: pastikan trend segar, siapkan satu episode baru untuk di-ACC."""
    db.init()

    # 1. kalau belum ada laporan trend atau sudah basi (>12 jam), scan
    report_path = Path(cfg["_root"]) / "data" / "last_trend_report.json"
    stale = True
    if report_path.exists():
        age = _now().timestamp() - report_path.stat().st_mtime
        stale = age > 12 * 3600
    if stale:
        jid = queue.enqueue("scan")
        print(f"  → scan trend masuk antrean (job #{jid})")
        queue.work_once()

    # 2. jangan menumpuk episode yang belum di-ACC
    waiting = db.list_episodes(status="pending_approval", limit=5)
    if len(waiting) >= 2:
        print(f"  ⏸ {len(waiting)} episode masih menunggu ACC — tidak membuat yang baru")
        return {"action": "skip", "waiting": len(waiting)}

    # 3. buat script baru
    jid = queue.enqueue("script")
    print(f"  → tulis script masuk antrean (job #{jid})")
    queue.work_once()

    # 4. kirim untuk ACC (non-blocking; Telegram kalau terkonfigurasi)
    eps = db.list_episodes(limit=1)
    if not eps:
        return {"action": "none"}
    ep = eps[0]
    if ep["status"] == "draft":
        queue.enqueue("approve", ep["id"])
        queue.work_once()

    return {"action": "prepared", "episode_id": ep["id"], "title": (ep["script"] or {}).get("title")}


def run(cfg: dict, interval_hours: float = 6.0, once: bool = False) -> None:
    state = load_state()
    stop = {"flag": False}

    def _sig(_s, _f):
        stop["flag"] = True
        print("\n  sinyal berhenti diterima, menutup dengan rapi…")

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _sig)
        except Exception:
            pass

    print("═" * 64)
    print(" WATCH MODE — AI bekerja selama laptop menyala")
    print(f" interval: {interval_hours} jam · Ctrl+C untuk berhenti")
    print(" render TIDAK otomatis — selalu menunggu ACC kamu")
    print("═" * 64)

    while not stop["flag"]:
        state = load_state()
        if _due(state, interval_hours):
            print(f"\n[{_now():%Y-%m-%d %H:%M}] siklus #{state.get('cycles', 0) + 1}")
            try:
                res = cycle(cfg)
                print(f"  hasil: {res}")
                state["last_episode"] = res.get("episode_id") or state.get("last_episode")
            except Exception as e:
                print(f"  ✖ siklus gagal: {str(e)[:200]}")
            state["last_cycle"] = _now().isoformat(timespec="seconds")
            state["cycles"] = state.get("cycles", 0) + 1
            save_state(state)
        else:
            nxt = _now() + timedelta(hours=interval_hours)
            print(f"  idle — siklus berikutnya sekitar {nxt:%H:%M}", end="\r", flush=True)

        if once:
            return
        # tidur 30 detik per iterasi supaya sinyal berhenti cepat ditangani
        for _ in range(30):
            if stop["flag"]:
                break
            time.sleep(1)

    print("watch mode berhenti.")


if __name__ == "__main__":
    from .config import load_config

    run(load_config())
