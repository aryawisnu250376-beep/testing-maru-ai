"""JOB QUEUE — render tidak lagi memblokir, dan gagal tidak lagi menghilang.

Kenapa perlu:
  - Render 1 video ≈ 40-90 detik CPU. Kalau dijalankan langsung dari dashboard
    atau cron, satu kegagalan = tidak ada jejak.
  - Dua episode tidak boleh render bersamaan di 2 vCPU (OOM / 3x lebih lambat).

Desain: tabel `jobs` di SQLite + klaim atomik (BEGIN IMMEDIATE). Cukup untuk
satu mesin. Kalau nanti butuh multi-mesin, ganti klaim jadi `FOR UPDATE SKIP
LOCKED` di Postgres — sisa kode tidak berubah.

Status job: queued -> running -> done | failed (retry sampai max_attempts)
"""
from __future__ import annotations

import json
import time
import threading
import traceback

from . import db


def enqueue(kind: str, episode_id: str | None = None, payload: dict | None = None,
            max_attempts: int = 3) -> int:
    db.init()
    if kind not in ("scan", "script", "approve", "render", "qc", "publish", "learn", "check_models", "hermes"):
        raise ValueError("Jenis pekerjaan tidak dikenal")
    if max_attempts < 1 or max_attempts > 8:
        raise ValueError("max_attempts harus 1..8")
    with db.conn() as c:
        c.execute("BEGIN IMMEDIATE")
        if kind in ("render", "publish") and episode_id:
            row = c.execute("SELECT id FROM jobs WHERE episode_id=? AND kind=? AND status IN ('queued','running')",
                            (episode_id, kind)).fetchone()
            if row:
                return int(row["id"])
        cur = c.execute(
            "INSERT INTO jobs (episode_id, kind, status, max_attempts, payload, created_at)"
            " VALUES (?,?,'queued',?,?,?)",
            (episode_id, kind, max_attempts, json.dumps(payload or {}), db.now()))
        return int(cur.lastrowid)


def claim(now: float | None = None) -> dict | None:
    """Ambil satu job secara atomik. Return None kalau antrean kosong."""
    db.init()
    now = time.time() if now is None else now
    with db.conn() as c:
        c.execute("BEGIN IMMEDIATE")
        stale = c.execute("SELECT * FROM jobs WHERE status='running' AND lease_until>0 AND lease_until<?", (now,)).fetchall()
        for old in stale:
            if old["attempts"] >= old["max_attempts"]:
                c.execute("UPDATE jobs SET status='failed',error='Lease proses kedaluwarsa',finished_at=? WHERE id=?", (db.now(), old["id"]))
            else:
                delay = min(300, 5 * 2 ** (old["attempts"] - 1))
                c.execute("UPDATE jobs SET status='queued',next_attempt_at=?,lease_until=0,error='Proses terputus; pemulihan otomatis' WHERE id=?", (now+delay, old["id"]))
        row = c.execute(
            "SELECT * FROM jobs WHERE status='queued' AND next_attempt_at<=? ORDER BY id LIMIT 1", (now,)).fetchone()
        if not row:
            return None
        c.execute("UPDATE jobs SET status='running', attempts=attempts+1, started_at=?, lease_until=? WHERE id=?",
                  (db.now(), now + 1800, row["id"]))
        job = dict(row)
        job["status"] = "running"      # row diambil sebelum UPDATE — samakan
        job["attempts"] += 1
        job["payload"] = json.loads(job["payload"] or "{}")
    return job


def finish(job_id: int, ok: bool, result: dict | None = None, error: str = "") -> None:
    with db.conn() as c:
        c.execute("UPDATE jobs SET status=?, result=?, error=?, finished_at=?, lease_until=0 WHERE id=?",
                  ("done" if ok else "failed", json.dumps(result or {}, ensure_ascii=False),
                   error[:800], db.now(), job_id))


def retry_or_fail(job: dict, error: str) -> str:
    """Kalau masih ada jatah percobaan, kembalikan ke antrean."""
    if job["attempts"] < job["max_attempts"]:
        delay = min(300, 5 * 2 ** (job["attempts"] - 1))
        with db.conn() as c:
            c.execute("UPDATE jobs SET status='queued', error=?, next_attempt_at=?,lease_until=0 WHERE id=?",
                      (error[:800], time.time() + delay, job["id"]))
        if job.get("episode_id") and job.get("kind") == "render":
            ep = db.get_episode(job["episode_id"])
            if ep and ep["status"] == "rendering":
                db.set_status(job["episode_id"], "approved", retry_in_sec=delay)
        return "retry"
    finish(job["id"], False, error=error)
    if job.get("episode_id") and job.get("kind") == "render":
        ep = db.get_episode(job["episode_id"])
        if ep and ep["status"] in ("approved", "rendering"):
            db.set_status(job["episode_id"], "failed", reason="Render gagal setelah semua percobaan")
    return "failed"


def pending_count() -> int:
    """Job yang masih menunggu dikerjakan (belum selesai/gagal).

    `running`, `done`, `failed`, `cancelled` tidak dihitung: yang sedang jalan
    bukan lagi beban antrean, dan job selesai tidak boleh menahan antrean baru.
    """
    with db.conn() as c:
        r = c.execute("SELECT COUNT(*) n FROM jobs WHERE status = 'queued'").fetchone()
    return int(r["n"])


def list_jobs(limit: int = 40) -> list[dict]:
    db.init()
    with db.conn() as c:
        rows = c.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"] or "{}")
        try:
            d["result"] = json.loads(d["result"] or "{}")
        except Exception:
            d["result"] = {}
        out.append(d)
    return out


# ---------------------------------------------------------------- runner

HANDLERS: dict[str, callable] = {}


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn

    return deco


def _load_handlers() -> None:
    """Import handler lazily supaya queue bisa dipakai tanpa dependency render."""
    if HANDLERS:
        return
    from pathlib import Path

    from . import approve as ap
    from . import publish as pb
    from . import qc as qcmod
    from . import scriptwriter, trend_radar
    from .config import load_config, out_dir

    cfg = load_config()

    @handler("scan")
    def _scan(job):
        return trend_radar.run(cfg, persist=True)

    @handler("script")
    def _script(job):
        from .cli import _find_cluster, _slug

        theme = job["payload"].get("theme")
        cluster = _find_cluster(cfg, theme)
        script = scriptwriter.write_script(cluster, cfg)
        ok, errs, warns = scriptwriter.validate_script(script, cfg)
        ep = db.new_episode_id(_slug(script.get("title", "episode")))
        d = out_dir(ep)
        (d / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        db.save_episode(ep, "draft", cluster, script, {"script": str(d / "script.json")})
        return {"episode_id": ep, "validation": {"ok": ok, "errors": errs, "warnings": warns}}

    @handler("approve")
    def _approve(job):
        ep = db.get_episode(job["episode_id"])
        return ap.request_approval(job["episode_id"], ep["script"], cfg, ep.get("topic"),
                                   wait_sec=int(job["payload"].get("wait", 0)))

    @handler("render")
    def _render(job):
        from . import orchestrator
        ep_id = job["episode_id"]
        ep = db.get_episode(ep_id)
        if not ep:
            raise ValueError("Episode tidak ditemukan")
        ap.require_approval(ep_id)
        return orchestrator.produce_approved(ep, cfg)

    @handler("qc")
    def _qc(job):
        ep = db.get_episode(job["episode_id"])
        d = out_dir(job["episode_id"])
        meta = json.loads((d/"render_meta.json").read_text()) if (d/"render_meta.json").exists() else None
        report = qcmod.run_qc(Path(ep["paths"].get("video", "")), cfg, meta=meta)
        if not report["passed"]:
            raise RuntimeError("QC belum lulus: "+", ".join(report["failed"]))
        return report

    @handler("publish")
    def _publish(job):
        ep = db.get_episode(job["episode_id"])
        return pb.publish(job["episode_id"], ep["script"], cfg,
                          mode=job["payload"].get("mode"))

    @handler("check_models")
    def _check_models(job):
        from . import providers
        llm_cfg = cfg.get("llm", {})
        base = llm_cfg.get("base_url", "")
        model = llm_cfg.get("model_strong") or llm_cfg.get("model")
        if not base or not model:
            return {"error": "LLM_BASE_URL dan LLM_MODEL belum diisi di server"}
        result = providers.probe_model(base, llm_cfg.get("api_key", ""), model, timeout=12)
        return {"result": result}

    @handler("hermes")
    def _hermes(job):
        from . import hermes4
        return hermes4.run_file(job["payload"]["path"], job["payload"].get("topic", ""))

    @handler("learn")
    def _learn(job):
        from . import learning

        return {"patterns": learning.apply_insights(cfg), "report": learning.report()}


def run_job(job: dict) -> dict:
    _load_handlers()
    fn = HANDLERS.get(job["kind"])
    if not fn:
        finish(job["id"], False, error=f"jenis job tidak dikenal: {job['kind']}")
        return {"ok": False, "error": "unknown kind"}
    stop_heartbeat = threading.Event()
    def heartbeat():
        while not stop_heartbeat.wait(60):
            with db.conn() as c:
                c.execute("UPDATE jobs SET lease_until=? WHERE id=? AND status='running'",(time.time()+1800,job["id"]))
    hb = threading.Thread(target=heartbeat,daemon=True)
    hb.start()
    try:
        if job.get("kind") in ("render", "publish") and job.get("episode_id"):
            from . import approve
            try:
                approve.require_approval(job["episode_id"])
            except PermissionError:
                finish(job["id"], False, error="ACC tidak valid atau naskah berubah")
                return {"ok": False, "error": "approval required", "state": "failed"}
        result = fn(job) or {}
        if result.get("error") or result.get("action") in ("blocked", "qc_failed"):
            raise RuntimeError(str(result.get("error") or result.get("reason") or result.get("action")))
        finish(job["id"], True, result=result)
        print(f"  ✔ job #{job['id']} {job['kind']} selesai")
        return {"ok": True, "result": result}
    except Exception as e:
        if job.get("episode_id") and job.get("kind") == "render":
            ep = db.get_episode(job["episode_id"])
            if ep and ep["status"] == "rendering":
                db.set_status(job["episode_id"], "failed", reason=str(e)[:200])
        tb = traceback.format_exc().strip().splitlines()
        err = str(e)[:300] + (f"  [{tb[-1][:120]}]" if tb else "")
        if job.get("episode_id"):
            db.log_event(job["episode_id"], "job_failed",
                         {"kind": job["kind"], "error": err,
                          "traceback": traceback.format_exc()[-1500:]})
        state = retry_or_fail(job, err)
        print(f"  ✖ job #{job['id']} {job['kind']} {state}: {str(e)[:140]}")
        return {"ok": False, "error": str(e), "state": state}
    finally:
        stop_heartbeat.set()


def work_once(now: float | None = None) -> bool:
    job = claim(now)
    if not job:
        return False
    run_job(job)
    return True


def worker(poll_sec: float = 2.0, once: bool = False, max_jobs: int = 0) -> None:
    """Loop worker. `max_jobs=0` berarti tanpa batas."""
    print(f"worker mulai (poll {poll_sec}s). Ctrl+C untuk berhenti.")
    done = 0
    try:
        while True:
            did = work_once()
            if did:
                done += 1
                if max_jobs and done >= max_jobs:
                    print(f"selesai setelah {done} job")
                    return
            elif once:
                print("antrean kosong")
                return
            else:
                time.sleep(poll_sec)
    except KeyboardInterrupt:
        print("\nworker berhenti")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="worker antrean render")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll", type=float, default=2.0)
    ap.add_argument("--max-jobs", type=int, default=0)
    a = ap.parse_args()
    worker(a.poll, a.once, a.max_jobs)
