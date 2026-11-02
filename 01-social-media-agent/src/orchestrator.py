"""ORCHESTRATOR — AI yang bekerja sendiri, tanpa trigger.

Perbedaan dengan `watch.py`: watch hanya menyiapkan episode lalu berhenti.
Orkestrator ini menutup seluruh lingkaran:

    riset → ide → skrip → [KAMU: ACC / revisi] → animasi → dubbing → QC → publikasi

Dan yang paling penting: **tidak ada tombol**. Tidak ada `scan`, tidak ada
`render`. Agent memilih sendiri apa yang dikerjakan tiap langkah, berdasarkan
kondisi DB. Kamu hanya masuk di satu titik: menyetujui atau merevisi.

Aturan yang tidak bisa dilanggar dari sini:
  * render tidak pernah jalan sebelum ada file keputusan `approve`
  * publish publik tidak pernah otomatis (butuh audit TikTok) — yang dibuat
    hanya paket siap-upload

Cara pakai:
    python -m src.cli studio              # jalan terus sampai Ctrl+C
    python -m src.cli studio --once       # satu langkah saja (untuk test)
    python -m src.dashboard               # dashboard + orkestrator sekaligus
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import agents, db

STATE = Path(os.environ.get(
    "STUDIO_STATE",
    str(Path(__file__).resolve().parents[1] / "data" / "orchestrator_state.json")))


def set_state_path(path: str | Path) -> None:
    """Pindahkan file state. Wajib dipakai test supaya tidak merusak state asli."""
    global STATE
    STATE = Path(path)

DEFAULTS = {
    "enabled": True,
    "max_pending_approval": 2,      # berhenti bikin episode baru kalau sebanyak ini menunggu
    "min_hours_between_episodes": 3.0,
    "auto_produce_after_approval": True,
    "auto_publish": False,          # publish publik tetap manual (audit TikTok)
    "learn_when_idle": True,
    "tick_sec": 15,
}


def _age(ts: str | None):
    """Selisih waktu yang tahan campuran naive/aware.

    `db.now()` menyimpan UTC ber-timezone ("...+00:00"), sedangkan `datetime.now()`
    naive. Mengurangkan keduanya melempar TypeError — dan karena dulu error itu
    ditelan `except: return True`, jeda antar-episode **tidak pernah berlaku**
    sehingga orkestrator membuat episode baru tiap tick. Jangan diulang.
    """
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts)
    except Exception:
        return None
    return (datetime.now(d.tzinfo) if d.tzinfo else datetime.now()) - d


def _cfg_autonomy(cfg: dict) -> dict:
    out = dict(DEFAULTS)
    out.update((cfg or {}).get("autonomy") or {})
    return out


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"started_at": None, "steps": 0, "last_episode_at": None,
            "last_action": None, "last_error": None}


def save_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- pemilihan kerja

def _uuid_ep(ep: dict) -> str:
    return ep["id"]


def _has_final(ep: dict) -> bool:
    p = (ep.get("paths") or {}).get("video")
    return bool(p) and Path(p).exists()


def _next_to_produce() -> dict | None:
    """Episode yang sudah di-ACC tapi belum punya video."""
    for e in db.list_episodes(status="approved", limit=10):
        if not _has_final(e):
            return e
    return None


def _pending_count() -> int:
    return len(db.list_episodes(status="pending_approval", limit=20))


def _due_to_learn(auto: dict, state: dict) -> bool:
    """Belajar itu pekerjaan berat — sekali sejam cukup, bukan tiap tick."""
    age = _age(state.get("last_learn_at"))
    return age is None or age >= timedelta(minutes=60)


def _due_for_new_episode(auto: dict, state: dict) -> bool:
    age = _age(state.get("last_episode_at"))
    return age is None or age >= timedelta(hours=float(auto["min_hours_between_episodes"]))


# ---------------------------------------------------------------- langkah kerja

def _research(cfg: dict) -> dict:
    """Agent Riset: pindai semua sumber. Mengembalikan laporan cluster."""
    from . import trend_radar

    with agents.task("riset", "Pindai tren & sumber", None) as t:
        t["report"](0.10, "membaca HN, HuggingFace, GitHub, Google Trends")
        report = trend_radar.run(cfg, persist=True, verbose=False)
        n = report.get("counts", {})
        t["report"](1.0, f"{n.get('collected', 0)} sinyal → {n.get('clusters', 0)} topik")
    return report


def _pick_cluster(report: dict, cfg: dict) -> dict:
    """Agent Ide: pilih topik yang belum pernah jadi episode."""
    covered = set()
    for e in db.list_episodes(limit=200):
        title = ((e.get("script") or {}).get("title") or "").lower()
        if title:
            covered.add(title)

    clusters = report.get("clusters") or []
    with agents.task("ide", "Pilih sudut cerita", None,
                     f"{len(clusters)} kandidat") as t:
        chosen = None
        for i, c in enumerate(clusters):
            t["report"](min(0.9, (i + 1) / max(len(clusters), 1)),
                        f"menimbang: {str(c.get('title', ''))[:60]}")
            # tolak kalau judulnya sudah pernah dipakai
            if str(c.get("title", "")).lower() in covered:
                continue
            chosen = c
            break
        if chosen is None and clusters:
            chosen = clusters[0]
        if chosen is None:
            t["report"](1.0, "tidak ada sinyal layak hari ini")
            return {}
        t["report"](1.0, f"dipilih: {str(chosen.get('title', ''))[:70]}")
    return chosen


def _write_episode(cluster: dict, cfg: dict) -> dict:
    """Agent Skrip: tulis naskah, simpan episode, lalu serahkan ke ACC."""
    import json as _json

    from . import scriptwriter
    from .cli import _slug
    from .config import out_dir
    from .llm import LLM

    with agents.task("skrip", "Tulis hook + 6 beat + visual", None,
                     str(cluster.get("title", ""))[:90]) as t:
        llm = LLM.from_config(cfg)
        t["report"](0.15, "menyusun kerangka dari sinyal riset")
        script = scriptwriter.write_script(cluster, cfg, llm)
        t["report"](0.60, "validasi aturan naskah")
        ok, errors, _warn = scriptwriter.validate_script(script, cfg)

        tries = 0
        while not ok and getattr(llm, "available", False) and tries < 2:
            tries += 1
            t["report"](0.60 + 0.1 * tries, f"minta perbaikan ke LLM (putaran {tries})")
            msgs = scriptwriter.build_messages(cluster, cfg)
            msgs.append({"role": "user", "content":
                         "Script sebelumnya melanggar aturan ini:\n- " + "\n- ".join(errors)
                         + "\nTulis ulang, patuhi semua aturan."})
            try:
                script = llm.chat_json(msgs, tier="strong", temperature=0.7)
                script["generator"] = "llm"
                script["theme"] = cluster.get("theme")
                ok, errors, _warn = scriptwriter.validate_script(script, cfg)
            except Exception:
                break

        ep_id = db.new_episode_id(_slug(script.get("title", "episode")))
        d = out_dir(ep_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "script.json").write_text(
            _json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
        db.save_episode(ep_id, "draft", cluster, script,
                        {"script": str(d / "script.json")})
        t["report"](1.0, f"{ep_id} · validasi {'OK' if ok else 'ada catatan'}")

    # serahkan ke manusia
    db.set_status(ep_id, "pending_approval")
    agents.wait_for_human("Menunggu ACC kamu", ep_id,
                          script.get("title", "")[:90])
    return {"episode_id": ep_id, "title": script.get("title"),
            "validation_ok": ok, "errors": errors}


class _PhaseRouter:
    """Satu render menyentuh beberapa agent. Router ini menutup task agent lama
    dan membuka task agent baru setiap kali fase berubah, jadi dashboard selalu
    melukiskan siapa yang benar-benar sedang bekerja.
    """

    def __init__(self, episode_id: str, title: str):
        self.ep = episode_id
        self.title = title
        self.cur_agent = None
        self.cur_id = None

    def _close(self):
        if self.cur_id:
            db.task_finish(self.cur_id, "done")
        self.cur_id = None
        self.cur_agent = None

    def __call__(self, phase: str, frac: float, detail: str):
        agent = "dubbing" if phase == "dubbing" else "animasi"
        if agent != self.cur_agent:
            self._close()
            labels = {"dubbing": "Suara, musik & sfx", "animasi": "Bangun scene visual"}
            self.cur_id = db.task_start(agent, labels[agent], self.ep, self.title[:90])
            self.cur_agent = agent
        if self.cur_id:
            db.task_progress(self.cur_id, frac, detail)

    def done(self):
        self._close()


def produce_approved(ep: dict, cfg: dict, auto: dict | None = None) -> dict:
    """Render synchronously; called by the single queue worker, never by HTTP."""
    auto = auto or _cfg_autonomy(cfg)
    from . import approve as ap
    from . import publish as pb
    from . import qc as qcmod
    from . import render as rn

    ep_id = _uuid_ep(ep)
    script = ep.get("script") or {}

    # gerbang: tidak ada ACC, tidak ada render
    error = ap.approval_error(ep_id, script)
    if error:
        return {"action": "blocked", "reason": error}

    db.set_status(ep_id, "rendering")
    router = _PhaseRouter(ep_id, script.get("title", ""))
    try:
        meta = rn.render_episode(script, cfg, ep_id, on_step=router)
    finally:
        router.done()

    db.save_episode(ep_id, "rendered", ep.get("topic"), script,
                    {"video": meta["video"], "cover": meta["cover"],
                     "duration_sec": meta["duration_sec"], "render_meta": str(Path(meta["video"]).parent / "render_meta.json")})

    with agents.task("qc", "Cek durasi, loudness & layout", ep_id) as t:
        t["report"](0.3, "mengukur loudness")
        rep = qcmod.run_qc(Path(meta["video"]), cfg, meta=meta)
        (Path(meta["video"]).parent / "qc_report.json").write_text(
            json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
        t["report"](1.0, ("lulus" if rep.get("passed") else "ada catatan")
                    + f" · {rep.get('loudness', {}).get('integrated_lufs')} LUFS")

    if not rep.get("passed") or not meta.get("layout", {}).get("ok"):
        db.set_status(ep_id, "failed", reason="QC belum lulus")
        return {"action": "qc_failed", "episode_id": ep_id, "qc_passed": False}

    with agents.task("publikasi", "Siapkan paket upload", ep_id) as t:
        t["report"](0.4, "menyusun caption & hashtag")
        try:
            pkg = pb.build_package(ep_id, script, cfg)
            t["report"](1.0, "paket siap" + ("" if auto.get("auto_publish") else " (upload manual)"))
        except Exception as e:
            pkg = {"error": str(e)[:160]}
            t["report"](1.0, f"paket gagal: {str(e)[:80]}")

    return {"action": "produced", "episode_id": ep_id,
            "duration_sec": meta.get("duration_sec"),
            "qc_passed": rep.get("passed"), "package": pkg}


def _learn(cfg: dict) -> dict:
    """Saat menunggu ACC, agent tidak diam: ia belajar dari performa yang ada."""
    from . import learning

    with agents.task("revisi", "Pelajari pola performa", None) as t:
        t["report"](0.5, "menimbang metrik episode lalu")
        rep = learning.report()
        n = len(rep.get("rows") or rep.get("patterns") or [])
        t["report"](1.0, f"{n} sinyal performa dianalisis")
    return {"action": "learned", "items": n}


# ---------------------------------------------------------------- satu langkah

def step(cfg: dict, state: dict | None = None) -> dict:
    """Satu unit kerja. Dipanggil berulang oleh `run()`; aman dipanggil sekali."""
    db.init()
    auto = _cfg_autonomy(cfg)
    state = state if state is not None else load_state()

    # 1. ada episode yang sudah di-ACC? kerjakan itu dulu — ACC kamu adalah prioritas
    ep = _next_to_produce()
    if ep:
        if not auto.get("auto_produce_after_approval", True):
            return {"action": "idle", "reason": "produksi otomatis dinonaktifkan"}
        from . import approve, queue
        error = approve.approval_error(ep["id"])
        if error:
            db.set_status(ep["id"], "pending_approval", reason=error)
            return {"action": "blocked", "reason": error}
        jid = queue.enqueue("render", ep["id"], max_attempts=3)
        return {"action": "queued", "episode_id": ep["id"], "job_id": jid}

    # 2. terlalu banyak yang menunggu? jangan menumpuk; sambil menunggu, belajar
    if _pending_count() >= int(auto["max_pending_approval"]):
        if auto.get("learn_when_idle") and _due_to_learn(auto, state):
            res = _learn(cfg)
            # hanya mengubah dict yang diberikan; yang menyimpan file adalah run()
            state["last_learn_at"] = datetime.now().isoformat(timespec="seconds")
            return res
        return {"action": "idle", "reason": "menunggu ACC"}

    # 3. sudah waktunya episode baru?
    if not _due_for_new_episode(auto, state):
        return {"action": "idle", "reason": "jeda antar-episode belum lewat"}

    # 4. riset → ide → tulis → serahkan ke ACC
    report = _research(cfg)
    cluster = _pick_cluster(report, cfg)
    if not cluster:
        return {"action": "idle", "reason": "tidak ada sinyal layak"}
    res = _write_episode(cluster, cfg)
    state["last_episode_at"] = datetime.now().isoformat(timespec="seconds")
    return {"action": "prepared", **res}


# ---------------------------------------------------------------- loop

def run(cfg: dict, once: bool = False, tick: float | None = None,
        quiet: bool = False) -> dict:
    """Putaran tanpa akhir. Tidak butuh trigger: tiap tick ia memilih kerja sendiri."""
    auto = _cfg_autonomy(cfg)
    tick = float(tick if tick is not None else auto.get("tick_sec", 15))
    state = load_state()
    state["started_at"] = state.get("started_at") or datetime.now().isoformat(timespec="seconds")
    save_state(state)

    if not quiet:
        print("═" * 68)
        print(" STUDIO OTONOM — agent bekerja sendiri, kamu hanya ACC / revisi")
        print(f" jeda antar episode : {auto['min_hours_between_episodes']} jam")
        print(f" batas menunggu ACC : {auto['max_pending_approval']} episode")
        print(" tidak ada tombol render. render hanya jalan setelah kamu ACC.")
        print("═" * 68)

    last_sig = None
    failures = 0
    while True:
        res = {"action": "error"}
        state["heartbeat_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            retry_at = _age(state.get("next_retry_at"))
            if state.get("next_retry_at") and retry_at is not None and retry_at.total_seconds() < 0:
                res = {"action": "idle", "reason": "menunggu pemulihan otomatis"}
            else:
                res = step(cfg, state)
                failures = 0
                state["next_retry_at"] = None
            state["steps"] = state.get("steps", 0) + 1
            state["last_action"] = res.get("action")
            state["last_error"] = None
            save_state(state)

            sig = res.get("action") if res.get("action") != "idle" else "idle"
            if not quiet and sig != last_sig:
                stamp = f"[{datetime.now():%H:%M:%S}]"
                print(f"{stamp} {res.get('action')}: "
                      f"{res.get('reason') or res.get('title') or res.get('episode_id') or ''}")
                last_sig = sig
            if res.get("action") == "idle" and res.get("reason") == "menunggu ACC":
                pass
        except Exception as e:
            failures += 1
            delay = min(300, max(tick, 5 * 2 ** (failures - 1)))
            state["next_retry_at"] = (datetime.now() + timedelta(seconds=delay)).isoformat(timespec="seconds")
            state["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"
            res = {"action": "error", "reason": state["last_error"], "retry_in_sec": delay}
            save_state(state)
            if not quiet:
                print(f"  ✖ langkah gagal: {state['last_error']}")

        if once:
            return res
        time.sleep(tick)


if __name__ == "__main__":
    from .config import load_config

    run(load_config())
