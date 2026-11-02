"""State store (SQLite). Satu file, tanpa server.

Tabel:
  trends   — cache sinyal trend, dipakai untuk hitung novelty
  episodes — satu episode = satu paket konten, dengan state machine
  events   — audit log semua perubahan state (penting untuk approval)
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT

DB_PATH = Path(ROOT) / "data" / "pipeline.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trends (
    hash        TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT,
    raw_score   REAL DEFAULT 0,
    meta_json   TEXT DEFAULT '{}',
    first_seen  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episodes (
    id          TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    topic       TEXT,
    script_json TEXT,
    paths_json  TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id  TEXT NOT NULL,
    type        TEXT NOT NULL,
    data_json   TEXT DEFAULT '{}',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
    episode_id  TEXT NOT NULL,
    views       INTEGER DEFAULT 0,
    avg_watch   REAL DEFAULT 0,
    likes       INTEGER DEFAULT 0,
    comments    INTEGER DEFAULT 0,
    shares      INTEGER DEFAULT 0,
    fetched_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id  TEXT,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'queued',
    attempts    INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 2,
    payload     TEXT DEFAULT '{}',
    result      TEXT,
    error       TEXT,
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS model_status (
    model       TEXT PRIMARY KEY,
    provider    TEXT,
    ok          INTEGER,
    latency_ms  INTEGER,
    error       TEXT,
    checked_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id  TEXT NOT NULL,
    aspect      TEXT NOT NULL,
    instruction TEXT,
    old_value   TEXT,
    new_value   TEXT,
    status      TEXT NOT NULL DEFAULT 'applied',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rev_ep ON revisions(episode_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, id);
CREATE INDEX IF NOT EXISTS idx_ep_status ON episodes(status);
CREATE INDEX IF NOT EXISTS idx_metrics_ep ON metrics(episode_id);
CREATE TABLE IF NOT EXISTS agent_tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT NOT NULL,
    episode_id  TEXT,
    title       TEXT NOT NULL,
    detail      TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'queued',
    progress    REAL DEFAULT 0,
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    ended_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ep ON events(episode_id);
CREATE INDEX IF NOT EXISTS idx_agent_status ON agent_tasks(agent, status, id);
CREATE INDEX IF NOT EXISTS idx_agent_started ON agent_tasks(started_at);
"""

STATUSES = [
    "draft", "pending_approval", "approved", "rendering",
    "rendered", "published", "rejected", "failed",
]


_INIT_LOCK = threading.RLock()
_READY: set[Path] = set()


def set_db_path(path: str | Path) -> None:
    """Arahkan ke DB lain (dipakai tes & mode demo)."""
    global DB_PATH
    with _INIT_LOCK:
        DB_PATH = Path(path)
        _READY.clear()


def _loads(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=20000")
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


# Additive, transactional migrations. Never destroy or recreate user data.
MIGRATIONS = {
    2: (
        "ALTER TABLE jobs ADD COLUMN next_attempt_at REAL DEFAULT 0",
        "ALTER TABLE jobs ADD COLUMN lease_until REAL DEFAULT 0",
        "ALTER TABLE metrics ADD COLUMN retention_3s REAL",
        "ALTER TABLE metrics ADD COLUMN hook_variant TEXT DEFAULT ''",
        "CREATE INDEX IF NOT EXISTS idx_jobs_claim ON jobs(status,next_attempt_at,id)",
    ),
    3: (
        "CREATE TABLE metrics_history (episode_id TEXT NOT NULL, views INTEGER DEFAULT 0, avg_watch REAL DEFAULT 0, likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0, shares INTEGER DEFAULT 0, fetched_at TEXT NOT NULL, retention_3s REAL, hook_variant TEXT DEFAULT '')",
        "INSERT INTO metrics_history SELECT episode_id,views,avg_watch,likes,comments,shares,fetched_at,retention_3s,hook_variant FROM metrics",
        "DROP TABLE metrics",
        "ALTER TABLE metrics_history RENAME TO metrics",
        "CREATE INDEX idx_metrics_ep ON metrics(episode_id)",
    ),
}


def init() -> None:
    target = DB_PATH.resolve()
    if target in _READY:
        return
    with _INIT_LOCK:
        if target in _READY:
            return
        with conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            version = int(c.execute("PRAGMA user_version").fetchone()[0])
            has_episodes = c.execute("SELECT 1 FROM sqlite_master WHERE name='episodes'").fetchone()
            if version > 1 + len(MIGRATIONS):
                raise RuntimeError("DB dibuat versi aplikasi lebih baru; upgrade aplikasi dulu.")
            if version == 0:
                if has_episodes:
                    backup = DB_PATH.with_suffix(".pre-v2.db")
                    if not backup.exists():
                        dest = sqlite3.connect(backup)
                        try:
                            c.backup(dest)
                        finally:
                            dest.close()
                c.executescript(SCHEMA)
                c.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
                c.execute("INSERT OR IGNORE INTO schema_version VALUES (1,?)", (now(),))
                c.execute("PRAGMA user_version=1")
                version = 1
            if 0 < version < 1 + len(MIGRATIONS):
                c.commit()  # backup cannot run while this connection holds a write transaction
                backup = DB_PATH.with_suffix(f".pre-v{1+len(MIGRATIONS)}.db")
                if not backup.exists():
                    dest = sqlite3.connect(backup)
                    try:
                        c.backup(dest)
                    finally:
                        dest.close()
            for ver in range(version + 1, 2 + len(MIGRATIONS)):
                c.execute("SAVEPOINT migration")
                try:
                    for sql in MIGRATIONS[ver]:
                        c.execute(sql)
                    c.execute("INSERT INTO schema_version VALUES (?,?)", (ver, now()))
                    c.execute(f"PRAGMA user_version={ver}")
                    c.execute("RELEASE migration")
                except Exception:
                    c.execute("ROLLBACK TO migration")
                    c.execute("RELEASE migration")
                    raise
            # A worker crash must not leave an agent permanently 'working'.
            c.execute("UPDATE agent_tasks SET status='failed',ended_at=?,detail='Terputus saat proses berhenti; mulai ulang tugas dengan aman.' WHERE status IN ('working','queued')", (now(),))
        _READY.add(target)


def new_episode_id(slug: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    return f"ep-{stamp}-{slug[:28]}-{uuid.uuid4().hex[:4]}"


# ---------- trends ----------

def seen_trend(hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    q = ",".join("?" * len(hashes))
    with conn() as c:
        rows = c.execute(f"SELECT hash FROM trends WHERE hash IN ({q})", hashes).fetchall()
    return {r["hash"] for r in rows}


def save_trends(items: list[dict]) -> None:
    with conn() as c:
        for t in items:
            c.execute(
                "INSERT OR IGNORE INTO trends (hash, source, title, url, raw_score, meta_json, first_seen)"
                " VALUES (?,?,?,?,?,?,?)",
                (t["hash"], t["source"], t["title"], t.get("url", ""),
                 float(t.get("raw_score", 0)), json.dumps(t.get("meta", {})),
                 t.get("first_seen", now())),
            )


# ---------- episodes ----------

def save_episode(episode_id: str, status: str, topic: dict, script: dict | None = None,
                 paths: dict | None = None) -> None:
    ts = now()
    with conn() as c:
        row = c.execute("SELECT id FROM episodes WHERE id=?", (episode_id,)).fetchone()
        if row:
            cur = c.execute("SELECT paths_json FROM episodes WHERE id=?", (episode_id,)).fetchone()
            merged = json.loads(cur["paths_json"] or "{}")
            merged.update(paths or {})
            c.execute(
                "UPDATE episodes SET status=?, topic=?, script_json=?, paths_json=?, updated_at=? WHERE id=?",
                (status, json.dumps(topic), json.dumps(script) if script else None,
                 json.dumps(merged), ts, episode_id),
            )
        else:
            c.execute(
                "INSERT INTO episodes (id, status, topic, script_json, paths_json, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (episode_id, status, json.dumps(topic),
                 json.dumps(script) if script else None, json.dumps(paths or {}), ts, ts),
            )
    log_event(episode_id, "status", {"status": status})


def get_episode(episode_id: str) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["topic"] = _loads(d.get("topic"), {})
    d["script"] = _loads(d.get("script_json"), None)
    d["paths"] = _loads(d.get("paths_json"), {})
    return d


def list_episodes(status: str | None = None, limit: int = 30) -> list[dict]:
    with conn() as c:
        if status:
            rows = c.execute("SELECT * FROM episodes WHERE status=? ORDER BY created_at DESC LIMIT ?",
                             (status, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["topic"] = _loads(d.get("topic"), {})
        d["script"] = _loads(d.get("script_json"), None)
        d["paths"] = _loads(d.get("paths_json"), {})
        out.append(d)
    return out


def set_status(episode_id: str, status: str, **extra) -> None:
    if status not in STATUSES:
        raise ValueError(f"status tidak dikenal: {status}")
    with conn() as c:
        c.execute("UPDATE episodes SET status=?, updated_at=? WHERE id=?", (status, now(), episode_id))
    log_event(episode_id, "status", {"status": status, **extra})


def log_event(episode_id: str, etype: str, data: dict) -> None:
    with conn() as c:
        c.execute("INSERT INTO events (episode_id, type, data_json, created_at) VALUES (?,?,?,?)",
                  (episode_id, etype, json.dumps(data), now()))


def validate_metrics(episode_id: str, payload: dict) -> dict:
    import math
    init()
    ep = get_episode(episode_id)
    if not ep:
        raise ValueError("Episode tidak ditemukan")
    out = {}
    for key in ("views", "likes", "comments", "shares"):
        value = payload.get(key, 0)
        if isinstance(value, bool) or float(value) != int(float(value)) or not 0 <= float(value) <= 1e12:
            raise ValueError(key + " harus bilangan bulat non-negatif")
        out[key] = int(value)
    for key in ("avg_watch", "retention_3s"):
        value = payload.get(key)
        if value is None or value == "":
            out[key] = None if key == "retention_3s" else 0.0
            continue
        value = float(value)
        if not math.isfinite(value) or value < 0 or (key == "retention_3s" and value > 100) or (key == "avg_watch" and value > 86400):
            raise ValueError(key + " di luar rentang valid")
        out[key] = value
    if any(out[k] > out["views"] for k in ("likes", "comments", "shares")):
        raise ValueError("Suka/komentar/bagikan tidak boleh melebihi views pada snapshot yang sama")
    duration = float((ep.get("paths") or {}).get("duration_sec") or 0)
    if duration and out["avg_watch"] > duration * 3:
        raise ValueError("Rata-rata tonton tidak wajar untuk durasi video")
    variant = str(payload.get("hook_variant") or (ep.get("script") or {}).get("hook_variant") or "")
    if variant not in ("", "A", "B"):
        raise ValueError("Varian hook harus A atau B")
    out["hook_variant"] = variant
    return out


def save_metrics(episode_id: str, m: dict) -> None:
    m = validate_metrics(episode_id, m)
    with conn() as c:
        c.execute(
            "INSERT INTO metrics (episode_id, views, avg_watch, likes, comments, shares, fetched_at, retention_3s, hook_variant)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (episode_id, m["views"], m["avg_watch"], m["likes"], m["comments"], m["shares"], now(),
             m["retention_3s"], m["hook_variant"]),
        )


def latest_metrics(episode_id: str) -> dict | None:
    init()
    with conn() as c:
        row = c.execute("SELECT * FROM metrics WHERE episode_id=? ORDER BY fetched_at DESC,rowid DESC LIMIT 1", (episode_id,)).fetchone()
    return dict(row) if row else None


if __name__ == "__main__":
    init()
    print(f"DB siap: {DB_PATH}")


# ---------------------------------------------------------------- agent tasks
# Antrean kerja per agent. Dipakai orkestrator (menulis) dan dashboard
# (membaca untuk animasi studio). Semua fungsi di sini murah: satu query.

TASK_STATUSES = ("queued", "working", "done", "waiting", "failed")


def task_start(agent: str, title: str, episode_id: str | None = None,
               detail: str = "") -> int:
    """Buka task baru berstatus `working`. Mengembalikan id untuk update progress."""
    init()
    ts = now()
    with conn() as c:
        cur = c.execute(
            "INSERT INTO agent_tasks (agent, episode_id, title, detail, status,"
            " progress, created_at, started_at) VALUES (?,?,?,?,'working',0,?,?)",
            (agent, episode_id, title[:200], detail[:400], ts, ts))
    return int(cur.lastrowid)


def task_progress(task_id: int, progress: float, detail: str | None = None) -> None:
    progress = max(0.0, min(1.0, float(progress)))
    with conn() as c:
        if detail is None:
            c.execute("UPDATE agent_tasks SET progress=? WHERE id=?", (progress, task_id))
        else:
            c.execute("UPDATE agent_tasks SET progress=?, detail=? WHERE id=?",
                      (progress, detail[:400], task_id))


def task_finish(task_id: int, status: str = "done", detail: str | None = None) -> None:
    if status not in TASK_STATUSES:
        status = "done"
    progress = 1.0 if status == "done" else None
    with conn() as c:
        if detail is not None:
            c.execute("UPDATE agent_tasks SET status=?, progress=COALESCE(?,progress),"
                      " detail=?, ended_at=? WHERE id=?",
                      (status, progress, detail[:400], now(), task_id))
        else:
            c.execute("UPDATE agent_tasks SET status=?, progress=COALESCE(?,progress),"
                      " ended_at=? WHERE id=?", (status, progress, now(), task_id))


def tasks_active() -> list[dict]:
    """Task yang masih dikerjakan atau menunggu (untuk animasi & drawer)."""
    init()
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM agent_tasks WHERE status IN ('working','waiting','queued')"
            " ORDER BY id DESC LIMIT 60").fetchall()
    return [_task_row(r) for r in rows]


def tasks_recent(limit: int = 40, agent: str | None = None) -> list[dict]:
    init()
    q = "SELECT * FROM agent_tasks"
    args: list = []
    if agent:
        q += " WHERE agent=?"
        args.append(agent)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        rows = c.execute(q, args).fetchall()
    return [_task_row(r) for r in rows]


def tasks_for_episode(episode_id: str) -> list[dict]:
    init()
    with conn() as c:
        rows = c.execute("SELECT * FROM agent_tasks WHERE episode_id=? ORDER BY id",
                         (episode_id,)).fetchall()
    return [_task_row(r) for r in rows]


def _task_row(r) -> dict:
    d = dict(r)
    d["progress"] = float(d.get("progress") or 0)
    return d


def prune_tasks(keep_days: int = 7) -> int:
    """Buang riwayat task lama supaya DB tidak tumbuh tanpa batas di mode 24/7."""
    init()
    from datetime import datetime, timedelta

    cut = (datetime.now() - timedelta(days=keep_days)).isoformat(timespec="seconds")
    with conn() as c:
        cur = c.execute("DELETE FROM agent_tasks WHERE created_at < ? AND status != 'working'",
                        (cut,))
    return cur.rowcount
