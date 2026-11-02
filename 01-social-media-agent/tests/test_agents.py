"""Test untuk lapisan otonom: roster agent, bus task, orkestrator, studio.

Yang paling penting di sini bukan "apakah kodenya jalan", tapi **apakah
otonomi merusak gerbang ACC**. Agent boleh mengambil keputusan sendiri soal
apa yang dikerjakan; ia tidak boleh mengambil keputusan menggantikan manusia.
"""

import pytest

from src import agents, db, orchestrator


# ---------------------------------------------------------------- roster

def test_roster_lengkap_dan_unik():
    assert len(agents.AGENTS) == 8
    ids = [a["id"] for a in agents.AGENTS]
    assert len(set(ids)) == len(ids)
    for a in agents.AGENTS:
        assert a["name"] and a["duty"] and a["color"].startswith("#")
        assert isinstance(a["stage"], int)
    # urutan stage harus 1..8 tanpa lubang
    assert sorted(a["stage"] for a in agents.AGENTS) == list(range(1, 9))


def test_order_mengikuti_stage():
    assert agents.ORDER[0] == "riset"
    assert agents.ORDER[-1] == "publikasi"
    assert agents.get("tidak-ada")["name"] == "tidak-ada"   # tidak meledak


# ---------------------------------------------------------------- bus task

def test_task_lifecycle(fresh_db):
    with agents.task("riset", "Pindai tren") as t:
        t["report"](0.5, "setengah jalan")
        snap = {a["id"]: a for a in agents.snapshot()["agents"]}
        assert snap["riset"]["state"] == "working"
        assert 0.49 < snap["riset"]["progress"] < 0.51
        assert snap["riset"]["task"] == "Pindai tren"

    snap = {a["id"]: a for a in agents.snapshot()["agents"]}
    assert snap["riset"]["state"] == "idle"
    assert snap["riset"]["done_recent"] == 1


def test_task_gagal_dicatat_dan_exception_diteruskan(fresh_db):
    with pytest.raises(ValueError):
        with agents.task("skrip", "Tulis naskah") as t:
            t["report"](0.2, "mulai")
            raise ValueError("LLM mati")

    rows = db.tasks_recent(limit=5)
    assert rows[0]["status"] == "failed"
    assert "LLM mati" in rows[0]["detail"]
    # task gagal tidak boleh terus tampil sebagai "sedang bekerja"
    assert agents.snapshot()["active_count"] == 0


def test_waiting_dan_clear(fresh_db):
    db.save_episode("ep-w", "pending_approval", {"theme": "on_device"}, {"title": "t"}, {})
    agents.wait_for_human("Menunggu ACC kamu", "ep-w", "judul")

    snap = {a["id"]: a for a in agents.snapshot()["agents"]}
    assert snap["revisi"]["state"] == "waiting"
    assert snap["revisi"]["episode_id"] == "ep-w"

    assert agents.clear_waiting("ep-w", "done") == 1
    snap = {a["id"]: a for a in agents.snapshot()["agents"]}
    assert snap["revisi"]["state"] == "idle"


# ------------------------------------------------ gerbang ACC di mode otonom

def _seed_episode(ep_id: str, status: str, approved: bool = False) -> str:
    script = {
        "title": "Judul uji", "theme": "on_device", "generator": "template",
        "beats": [{"kind": "hook", "narration": "Satu.", "headline": "H",
                   "visual": {"type": "card", "props": {}}}],
        "sources": [{"title": "s", "url": "https://example.com"}],
    }
    db.save_episode(ep_id, status, {"theme": "on_device"}, script, {})
    if approved:
        from src.config import out_dir

        d = out_dir(ep_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "decision.json") .write_text('{"status": "approve"}', encoding="utf-8")
    return ep_id


def test_otonomi_tidak_pernah_render_tanpa_acc(fresh_db, cfg, tmp_path, monkeypatch):
    """Episode berstatus `approved` TANPA file keputusan tetap ditolak.

    Ini jaring pengaman utama: kalau orkestrator keliru menaikkan status,
    `read_decision` yang jadi penentu terakhir, bukan status di DB.
    """
    from src import render as rn

    ep = _seed_episode("ep-noacc", "approved", approved=False)

    def _boom(*a, **k):     # render tidak boleh sampai dipanggil
        raise AssertionError("render dipanggil tanpa ACC!")

    monkeypatch.setattr(rn, "render_episode", _boom)

    res = orchestrator.step(cfg, {"last_episode_at": None})
    assert res["action"] == "blocked"
    assert "ACC" in res["reason"]
    assert db.get_episode(ep)["status"] == "pending_approval"  # fail closed: kembali ke manusia


def test_otonomi_menghormati_batas_pending(fresh_db, cfg):
    for i in range(2):
        _seed_episode(f"ep-p{i}", "pending_approval")
    res = orchestrator.step(cfg, {})
    assert res["action"] in ("idle", "learned")
    # tidak boleh membuat episode baru saat antrean ACC sudah penuh
    assert len(db.list_episodes(status="pending_approval", limit=9)) == 2


def test_belajar_tidak_diulang_tiap_tick(fresh_db, cfg):
    """Idle tidak boleh membanjiri tabel task dengan pekerjaan 'belajar'."""
    for i in range(2):
        _seed_episode(f"ep-q{i}", "pending_approval")
    state = {"last_learn_at": db.now()}
    before = len(db.tasks_recent(limit=100))
    for _ in range(3):
        orchestrator.step(cfg, state)
    assert len(db.tasks_recent(limit=100)) == before   # tidak ada task baru


def test_jeda_antar_episode_dihormati(fresh_db, cfg):
    state = {"last_episode_at": db.now()}
    res = orchestrator.step(cfg, state)
    assert res["action"] == "idle"
    assert "jeda" in res["reason"]


def test_riot_autonomy_default_aman():
    auto = orchestrator._cfg_autonomy({})
    assert auto["auto_publish"] is False, "publish publik tidak boleh otomatis"
    assert auto["max_pending_approval"] >= 1
    assert auto["tick_sec"] >= 1


# ---------------------------------------------------------------- studio API

def test_studio_state_bentuk_json(fresh_db, cfg):
    from src.dashboard import studio_state

    _seed_episode("ep-s", "pending_approval")
    st = studio_state()
    assert set(st) >= {"agents", "pending", "shortcuts", "human", "totals"}
    assert len(st["agents"]) == 8
    assert st["pending"][0]["id"] == "ep-s"
    assert st["pending"][0]["beats"] == 1
    assert isinstance(st["shortcuts"], list) and len(st["shortcuts"]) >= 5
    for s in st["shortcuts"]:
        assert s["key"] and s["label"]


def test_studio_page_tidak_punya_tombol_pemicu():
    """Halaman hanya boleh mengekspos aksi manusia: ACC & revisi."""
    from src.studio_html import PAGE

    for terlarang in ("/api/action\",{action:\"scan", ">Scan<", ">Render<", ">Tulis Script<"):
        assert terlarang not in PAGE
    # tombol yang memang harus ada
    for wajib in ('id="btnJobs"', 'id="btnAcc"', 'id="approveBtn"', 'id="rejectBtn"'):
        assert wajib in PAGE


def test_prune_tasks_membuang_riwayat_lama(fresh_db):
    tid = db.task_start("qc", "Lama")
    db.task_finish(tid, "done")
    with db.conn() as c:      # paksa tanggalnya jadi 30 hari lalu
        c.execute("UPDATE agent_tasks SET created_at='2000-01-01T00:00:00' WHERE id=?", (tid,))
    assert db.prune_tasks(keep_days=7) >= 1
    assert db.tasks_recent(limit=10) == []


def test_step_tidak_menulis_state_global(fresh_db, cfg, tmp_path):
    """Regresi: `step()` dulu menyimpan state sendiri.

    Akibatnya test (atau proses lain) yang memanggil step() dengan dict kosong
    menghapus `last_episode_at` milik studio yang sedang jalan → orkestrator
    mengira belum pernah bikin episode → membuat episode baru tiap tick.
    """
    from src import orchestrator

    orchestrator.set_state_path(tmp_path / "state_isolated.json")
    orchestrator.save_state({"last_episode_at": db.now(), "steps": 0})

    for i in range(2):
        _seed_episode(f"ep-z{i}", "pending_approval")

    state = {}
    for _ in range(3):
        orchestrator.step(cfg, state)      # dict kosong milik pemanggil

    on_disk = orchestrator.load_state()
    assert on_disk["last_episode_at"], "step() menghapus last_episode_at di disk"
    assert on_disk["steps"] == 0, "step() tidak boleh menaikkan counter milik run()"


def test_state_file_bisa_dialihkan(tmp_path):
    from src import orchestrator

    orchestrator.set_state_path(tmp_path / "a.json")
    orchestrator.save_state({"steps": 7})
    assert orchestrator.load_state()["steps"] == 7
    assert (tmp_path / "a.json").exists()
