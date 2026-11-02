"""AGENTS — roster agent yang bekerja di pipeline, plus bus task-nya.

Setiap agent punya satu tanggung jawab sempit. Orkestrator tidak memanggil
agent secara langsung; ia membuka *task* (dicatat di tabel `agent_tasks`),
mengerjakan badan pekerjaan, lalu menutupnya. Dashboard hanya membaca tabel
itu untuk menggambar studio — jadi animasi tidak pernah berbohong tentang
apa yang sebenarnya sedang dikerjakan.

Tidak ada trigger di sini: agent tidak punya tombol. Yang menjalankan mereka
adalah `src/orchestrator.py`, yang berputar terus selama proses hidup.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

from . import db

# ---------------------------------------------------------------- roster
# `stage` = urutan kerja dalam satu episode. Dipakai orkestrator & dashboard.
AGENTS: list[dict] = [
    {
        "id": "riset", "name": "Riset", "stage": 1, "color": "#5EEAD4",
        "duty": "Pindai tren & sumber",
        "long": "Membaca HN, HuggingFace, GitHub, Google Trends dan watchlist "
                "referensi, lalu menilai momentum dan relevansi tiap sinyal.",
    },
    {
        "id": "ide", "name": "Ide", "stage": 2, "color": "#A78BFA",
        "duty": "Pilih sudut cerita",
        "long": "Menimbang tren yang belum pernah dibahas, memilih sudut yang "
                "bisa dijelaskan dalam satu menit, dan menolak topik yang terlalu "
                "mirip episode lama.",
    },
    {
        "id": "skrip", "name": "Skrip", "stage": 3, "color": "#60A5FA",
        "duty": "Tulis hook, beat & rencana visual",
        "long": "Menulis 6 beat: hook, tiga poin, satu batas jujur, dan CTA — "
                "lengkap dengan spec visual per beat serta sumber sebagai bukti.",
    },
    {
        "id": "revisi", "name": "Revisi", "stage": 4, "color": "#FBBF24",
        "duty": "Perbaiki naskah",
        "long": "Menerapkan revisi per aspek (hook, isi, narasi, visual, panjang, "
                "caption, sumber) tanpa merusak bagian yang tidak diminta.",
    },
    {
        "id": "animasi", "name": "Animasi", "stage": 5, "color": "#F472B6",
        "duty": "Bangun scene visual",
        "long": "Memilih tipe visual per beat, merender frame Pillow atau vektor "
                "Manim, lalu memastikan durasi tiap scene pas dengan narasinya.",
    },
    {
        "id": "dubbing", "name": "Dubbing", "stage": 6, "color": "#34D399",
        "duty": "Suara, musik & sfx",
        "long": "Mensintesis suara Indonesia, membuat musik sendiri sesuai tema, "
                "lalu mencampurnya dengan ducking supaya musik tidak menimpa suara.",
    },
    {
        "id": "qc", "name": "QC", "stage": 7, "color": "#FB923C",
        "duty": "Cek teknis & layout",
        "long": "Mengukur durasi, resolusi, fps, loudness -14 LUFS, clipping, dan "
                "memastikan teks tidak jatuh di area UI TikTok.",
    },
    {
        "id": "publikasi", "name": "Publikasi", "stage": 8, "color": "#818CF8",
        "duty": "Siapkan paket upload",
        "long": "Menyusun caption, hashtag, jadwal, dan paket file. Upload publik "
                "tetap butuh audit TikTok, jadi default-nya paket siap-tempel.",
    },
]

HUMAN = {"id": "kamu", "name": "Kamu", "color": "#FCD34D",
         "duty": "ACC atau revisi. Itu saja."}

BY_ID = {a["id"]: a for a in AGENTS}
ORDER = [a["id"] for a in sorted(AGENTS, key=lambda a: a["stage"])]


def get(agent_id: str) -> dict:
    return BY_ID.get(agent_id, {"id": agent_id, "name": agent_id, "color": "#888",
                                "duty": "", "stage": 99})


# ---------------------------------------------------------------- task bus

@contextmanager
def task(agent_id: str, title: str, episode_id: str | None = None, detail: str = ""):
    """Buka task, jalankan badan, tutup dengan status jujur.

    Kalau badan melempar exception, task ditandai `failed` **dan** exception
    diteruskan — orkestrator yang memutuskan mau lanjut atau berhenti. Tidak
    ada exception yang ditelan di sini.
    """
    tid = db.task_start(agent_id, title, episode_id, detail)

    box = {"id": tid, "agent": agent_id}

    def report(p: float, d: str | None = None) -> None:
        db.task_progress(tid, p, d)

    box["report"] = report
    try:
        yield box
    except Exception as e:
        db.task_finish(tid, "failed", f"{type(e).__name__}: {str(e)[:180]}")
        raise
    else:
        db.task_finish(tid, "done")
    finally:
        pass


def wait_for_human(title: str, episode_id: str, detail: str = "") -> int:
    """Tandai bahwa pipeline berhenti di gerbang ACC. Task tetap `waiting`
    sampai manusia memutuskan, supaya dashboard menampilkannya sebagai antrean
    yang benar-benar menunggu, bukan agent yang menganggur.
    """
    tid = db.task_start("revisi", title, episode_id, detail)
    db.task_finish(tid, "waiting", detail or "menunggu ACC")
    return tid


def clear_waiting(episode_id: str, status: str = "done") -> int:
    """Tutup task `waiting` milik episode setelah user ACC / tolak."""
    db.init()
    n = 0
    with db.conn() as c:
        rows = c.execute("SELECT id FROM agent_tasks WHERE episode_id=? AND status='waiting'",
                         (episode_id,)).fetchall()
        for r in rows:
            c.execute("UPDATE agent_tasks SET status=?, ended_at=?, progress=1.0 WHERE id=?",
                      (status, db.now(), r["id"]))
            n += 1
    return n


# ---------------------------------------------------------------- snapshot

def _age_sec(ts: str | None) -> float | None:
    """Detik sejak `ts`. Sadar timezone — `db.now()` UTC-aware, `datetime.now()` tidak."""
    if not ts:
        return None
    from datetime import datetime

    try:
        d = datetime.fromisoformat(ts)
    except Exception:
        return None
    delta = (datetime.now(d.tzinfo) if d.tzinfo else datetime.now()) - d
    return max(0.0, delta.total_seconds())


def snapshot() -> dict:
    """Kondisi tiap agent sekarang — sumber tunggal untuk animasi dashboard."""
    active = db.tasks_active()
    recent = db.tasks_recent(limit=120)

    by_agent: dict[str, list[dict]] = {a["id"]: [] for a in AGENTS}
    for t in active:
        by_agent.setdefault(t["agent"], []).append(t)

    out = []
    for a in AGENTS:
        mine = by_agent.get(a["id"], [])
        working = [t for t in mine if t["status"] == "working"]
        waiting = [t for t in mine if t["status"] == "waiting"]
        cur = (working or waiting or [None])[0]

        if working:
            state = "working"
        elif waiting:
            state = "waiting"
        else:
            state = "idle"

        done_today = sum(1 for t in recent
                         if t["agent"] == a["id"] and t["status"] == "done")
        failed = sum(1 for t in recent
                     if t["agent"] == a["id"] and t["status"] == "failed")

        out.append({
            **{k: a[k] for k in ("id", "name", "color", "duty", "long", "stage")},
            "state": state,
            "task": cur["title"] if cur else "",
            "detail": (cur["detail"] if cur else "") or "",
            "episode_id": cur["episode_id"] if cur else None,
            "progress": round(float(cur["progress"]), 3) if cur else 0.0,
            "elapsed_sec": _age_sec(cur["started_at"]) if cur else None,
            "queued": max(0, len(mine) - (1 if cur else 0)),
            "done_recent": done_today,
            "failed_recent": failed,
            "history": [
                {"title": t["title"], "status": t["status"],
                 "progress": round(float(t["progress"]), 3),
                 "episode_id": t["episode_id"], "started_at": t["started_at"],
                 "ended_at": t["ended_at"]}
                for t in mine[:8]
            ],
        })
    return {"agents": out, "human": HUMAN, "active_count": len(active)}


def log_line(agent_id: str, msg: str) -> str:
    """Format ringkas untuk terminal orkestrator."""
    a = get(agent_id)
    return f"  [{a['name']:<9}] {msg}"


def self_test() -> None:
    """Jalan cepat tanpa DB asli — dipakai `python -m src.agents`."""
    import tempfile
    from pathlib import Path

    # `:memory:` tidak bisa dipakai: db.conn() membuka koneksi baru tiap query.
    tmp = Path(tempfile.mkdtemp()) / "selftest.db"
    db.set_db_path(tmp)
    db.init()
    with task("riset", "Pindai tren", "-") as t:
        t["report"](0.4, "membaca HN")
        time.sleep(0.01)
    with task("skrip", "Tulis naskah", "-") as t:
        t["report"](1.0, "6 beat")
    snap = snapshot()
    for a in snap["agents"]:
        print(f"{a['name']:<10} {a['state']:<8} selesai={a['done_recent']} "
              f"gagal={a['failed_recent']}")
    print("total task aktif:", snap["active_count"])


if __name__ == "__main__":
    self_test()
