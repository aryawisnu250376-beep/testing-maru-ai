"""CLI — satu pintu masuk untuk semua langkah pipeline.

Semua subcommand mengeluarkan JSON di baris terakhir kalau diberi flag --json,
supaya aman dipanggil dari Hermes Agent / cron / GitHub Actions.

  python -m src.cli scan                      # radar trend
  python -m src.cli script --theme <id>       # tulis script + validasi
  python -m src.cli approve <episode_id>      # approval gate (Telegram/CLI)
  python -m src.cli resume <episode_id>       # lanjut setelah decision file diedit
  python -m src.cli render <episode_id>       # render mp4
  python -m src.cli qc <episode_id>           # QC teknis
  python -m src.cli publish <episode_id>      # paket upload / kirim TikTok
  python -m src.cli run                       # alur lengkap sekali jalan
  python -m src.cli list                      # status semua episode
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import approve as approve_mod
from . import db, learning, publish as publish_mod, qc as qc_mod, queue as queue_mod
from . import render as render_mod, scriptwriter, trend_radar
from .config import load_config, out_dir
from .llm import LLM


def _slug(text: str, n: int = 28) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:n] or "episode").strip("-")


def _find_cluster(cfg: dict, theme: str | None) -> dict:
    p = Path(cfg["_root"]) / "data" / "last_trend_report.json"
    if not p.exists():
        print("  radar belum pernah jalan, menjalankan sekarang…")
        return trend_radar.run(cfg)["clusters"][0]
    report = json.loads(p.read_text(encoding="utf-8"))
    clusters = report.get("clusters") or []
    if not clusters:
        raise SystemExit("tidak ada cluster trend. Jalankan: python -m src.cli scan")
    if not theme:
        return clusters[0]
    for c in clusters:
        if c.get("theme") == theme:
            return c
    print(f"  tema '{theme}' tidak ada, pakai topik teratas")
    return clusters[0]


# ---------------------------------------------------------------- commands

def cmd_scan(args, cfg) -> dict:
    return trend_radar.run(cfg)


def cmd_script(args, cfg) -> dict:
    cluster = _find_cluster(cfg, args.theme)
    llm = LLM.from_config(cfg)
    script = scriptwriter.write_script(cluster, cfg, llm)
    ok, errors, warnings = scriptwriter.validate_script(script, cfg)

    attempts = 0
    while not ok and llm.available and attempts < 2:
        attempts += 1
        print(f"  validasi gagal, minta LLM revisi (percobaan {attempts})…")
        msgs = scriptwriter.build_messages(cluster, cfg)
        msgs.append({"role": "user", "content":
                     "Script sebelumnya melanggar aturan ini:\n- " + "\n- ".join(errors)
                     + "\nTulis ulang, patuhi semua aturan."})
        try:
            script = llm.chat_json(msgs, tier="strong", temperature=0.7)
            script["generator"] = "llm"
            script["theme"] = cluster.get("theme")
            ok, errors, warnings = scriptwriter.validate_script(script, cfg)
        except Exception as e:
            print(f"  [warn] revisi gagal: {e}")
            break

    ep_id = db.new_episode_id(_slug(script.get("title", "episode")))
    d = out_dir(ep_id)
    (d / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    db.init()
    db.save_episode(ep_id, "draft", cluster, script, {"script": str(d / "script.json")})

    print(f"\nEpisode: {ep_id}")
    print(f"Judul  : {script.get('title')}")
    print(f"Sumber : {len(script.get('sources', []))} | validasi: {'OK' if ok else 'GAGAL'}")
    for e in errors:
        print("  ERROR:", e)
    for w in warnings:
        print("  WARN :", w)
    return {"episode_id": ep_id, "script": script,
            "validation": {"ok": ok, "errors": errors, "warnings": warnings}}


def cmd_approve(args, cfg) -> dict:
    ep = db.get_episode(args.episode_id)
    if not ep:
        raise SystemExit(f"episode {args.episode_id} tidak ada")
    script = ep["script"] or json.loads((out_dir(args.episode_id) / "script.json").read_text())
    cover = str(out_dir(args.episode_id) / "cover.png")
    res = approve_mod.request_approval(args.episode_id, script, cfg, ep.get("topic"),
                                       cover if Path(cover).exists() else None,
                                       wait_sec=args.wait)
    return res


def cmd_resume(args, cfg) -> dict:
    ep = db.get_episode(args.episode_id)
    if not ep:
        raise SystemExit(f"episode {args.episode_id} tidak ada")
    dec = approve_mod.read_decision(args.episode_id)
    if not dec or dec.get("status") == "pending":
        raise SystemExit("decision.json masih 'pending'. ACC dulu di Telegram atau edit file itu.")
    status = dec["status"]
    if status == "edit":
        print(f"  instruksi revisi: {dec.get('instruction')}")
        # revisi script pakai LLM kalau ada
        llm = LLM.from_config(cfg)
        script = ep["script"]
        if llm.available:
            msgs = scriptwriter.build_messages(ep["topic"], cfg)
            msgs.append({"role": "user", "content":
                         f"Revisi script ini sesuai instruksi: {dec.get('instruction')}\n"
                         f"Script lama: {json.dumps(script, ensure_ascii=False)[:3000]}"})
            script = llm.chat_json(msgs, tier="strong")
            script["generator"] = "llm"
            script, _ = scriptwriter.sanitize(script, ep["topic"], cfg)
            valid, errors, _ = scriptwriter.validate_script(script, cfg)
            if not valid:
                raise SystemExit("Revisi LLM tidak valid: "+"; ".join(errors))
            approve_mod.invalidate(args.episode_id, "Revisi LLM")
        return cmd_approve(args, cfg)
    res = approve_mod.apply_decision(args.episode_id, status, dec.get("instruction", ""))
    if res["status"] == "approved":
        return cmd_render(argparse.Namespace(episode_id=args.episode_id,
                                             voice=getattr(args, "voice", None)), cfg)
    return res


def _require_approved(episode_id: str) -> None:
    error = approve_mod.approval_error(episode_id)
    if error:
        raise SystemExit("Render diblokir: " + error)


def cmd_render(args, cfg) -> dict:
    _require_approved(args.episode_id)
    ep = db.get_episode(args.episode_id)
    script = ep["script"]
    db.set_status(args.episode_id, "rendering")
    try:
        meta = render_mod.render_episode(script, cfg, episode_id=args.episode_id, voice=args.voice)
    except Exception as e:
        db.set_status(args.episode_id, "failed", reason=str(e)[:300])
        raise
    db.save_episode(args.episode_id, "rendered", ep["topic"], script,
                    {"video": meta["video"], "cover": meta["cover"]})
    return meta


def cmd_qc(args, cfg) -> dict:
    ep = db.get_episode(args.episode_id)
    video = Path(ep["paths"].get("video") or out_dir(args.episode_id) / "final.mp4")
    if not video.exists():
        raise SystemExit(f"⛔ belum ada video untuk {args.episode_id}. Render dulu.")
    r = qc_mod.run_qc(video, cfg)
    print(f"QC: {'LULUS' if r['passed'] else 'GAGAL'}")
    for c in r["checks"]:
        print(f"  {'✔' if c['ok'] else '✖'} {c['check']:14} {c['detail']}")
    return r


def cmd_publish(args, cfg) -> dict:
    ep = db.get_episode(args.episode_id)
    if not ep:
        raise SystemExit("episode tidak ada")
    if not Path(ep["paths"].get("video") or out_dir(args.episode_id) / "final.mp4").exists():
        raise SystemExit(f"⛔ video belum dirender. Jalankan: python -m src.cli render {args.episode_id}")
    if args.mode:
        cfg["publish"]["mode"] = args.mode
    approve_mod.require_approval(args.episode_id)
    qpath = out_dir(args.episode_id)/"qc_report.json"
    if not qpath.is_file() or not json.loads(qpath.read_text()).get("passed"):
        raise SystemExit("QC harus lulus sebelum paket upload dibuat")
    return publish_mod.publish(args.episode_id, ep["script"], cfg)


def cmd_metrics(args, cfg) -> dict:
    db.init()
    db.save_metrics(args.episode_id, {"views": args.views, "avg_watch": args.avg_watch,
                                      "likes": args.likes, "comments": args.comments,
                                      "shares": args.shares})
    print(f"  metrik tersimpan untuk {args.episode_id}")
    try:
        pat = learning.apply_insights(cfg)
        print(f"  pola pemenang: {'diperbarui' if pat['has_patterns'] else 'belum cukup data'}")
    except Exception as e:
        pat = {"error": str(e)}
    return {"saved": True, "patterns": pat}


def cmd_enqueue(args, cfg) -> dict:
    jid = queue_mod.enqueue(args.kind, args.episode_id, {"theme": args.theme,
                                                         "mode": args.mode,
                                                         "voice": args.voice})
    print(f"  job #{jid} ({args.kind}) masuk antrean")
    print("  jalankan worker: python -m src.cli worker")
    return {"job_id": jid, "kind": args.kind}


def cmd_worker(args, cfg) -> dict:
    queue_mod.worker(poll_sec=args.poll, once=args.once, max_jobs=args.max_jobs)
    return {"finished": True, "pending": queue_mod.pending_count()}


def cmd_jobs(args, cfg) -> dict:
    jobs = queue_mod.list_jobs(limit=args.limit)
    if not args.json:
        print(f"{'#':>4} {'jenis':10} {'status':9} {'coba':6} error")
        print("-" * 74)
        for j in jobs:
            print(f"{j['id']:4} {j['kind']:10} {j['status']:9} "
                  f"{j['attempts']}/{j['max_attempts']:<4} {(j['error'] or '')[:36]}")
    return {"jobs": jobs, "pending": queue_mod.pending_count()}


def cmd_learn(args, cfg) -> dict:
    r = learning.report()
    if not args.json:
        if not r.get("n"):
            print(r.get("message", "belum ada data"))
        else:
            print(f"video dengan metrik: {r['n']} | cukup menyimpulkan: {r['ready']}")
            print(f"retensi rata-rata: {r['overall']['avg_retention']:.0%} | "
                  f"views rata-rata: {r['overall']['avg_views']}")
            for k, groups in r["dimensions"].items():
                if len(groups) < 2:
                    continue
                print(f"\n  {k}:")
                for g in groups:
                    mark = "✓" if g["confident"] else "·"
                    print(f"    {mark} {g['value']:14} n={g['n']:2}  retensi {g['avg_retention']:.0%}")
            print("\n  insight:")
            for i in r["insights"]:
                print(f"    - {i}")
            pat = learning.apply_insights(cfg)
            print(f"\n  pola disimpan: {pat['path']}")
    return r


def cmd_watch(args, cfg) -> dict:
    from . import watch

    watch.run(cfg, interval_hours=args.interval, once=args.once)
    return {"stopped": True}


def cmd_doctor(args, cfg) -> dict:
    from .health import diagnose
    result = diagnose(network=getattr(args, "network", False))
    for check in result["checks"]:
        mark = "OK" if check["ok"] else ("GAGAL" if check["required"] else "OPSIONAL")
        print(f"  {mark:8} {check['name']}: {check['detail']}")
    return result


def cmd_studio(args, cfg) -> dict:
    """Studio otonom: agent bekerja sendiri, tanpa trigger."""
    from . import orchestrator

    from .health import require_healthy
    require_healthy()
    return orchestrator.run(cfg, once=args.once, tick=args.tick, quiet=args.quiet)


def cmd_revise(args, cfg) -> dict:
    from . import revisor

    if args.aspect == "list" and not args.shortcut:
        print("aspek yang bisa direvisi:")
        for k, v in revisor.ASPECTS.items():
            print(f"  {k:12} {v}")
        print("\n shortcut siap pakai:")
        for k, (aspect, instr) in revisor.SHORTCUTS.items():
            print(f"  {k:24} -> {aspect}: {instr[:50]}")
        return {"aspects": revisor.ASPECTS, "shortcuts": revisor.SHORTCUTS}

    if args.shortcut:
        aspect, instruction = revisor.SHORTCUTS.get(args.shortcut, (None, None))
        if not aspect:
            raise SystemExit(f"shortcut tidak dikenal: {args.shortcut}")
    else:
        aspect, instruction = args.aspect, (args.instruction or "perbaiki bagian ini")

    if not args.episode_id:
        raise SystemExit("episode_id wajib (kecuali untuk 'revise list')")
    res = revisor.apply_revision(args.episode_id, aspect, instruction, cfg)
    if args.json:
        res.pop("script", None)
        return res
    print(f"revisi '{aspect}': {'OK' if res.get('ok') else 'GAGAL'}")
    for n in res.get("notes", []):
        print(f"  · {n}")
    for e in res.get("errors", []):
        print(f"  ✖ {e}")
    print(f"  sebelum: {json.dumps(res.get('before'), ensure_ascii=False)[:150]}")
    print(f"  sesudah: {json.dumps(res.get('after'), ensure_ascii=False)[:150]}")
    return res


def cmd_harvest(args, cfg) -> dict:
    """Ubah watchlist referensi jadi sinyal radar, lalu tampilkan hasilnya."""
    from .trend_radar import collect_reference_watchlist

    refs = collect_reference_watchlist()
    print(f"  {len(refs)} pola referensi terbaca")
    for r in refs:
        print(f"    · {r['title'][:70]}")
        print(f"      tema: {r['meta']['theme']} | hook: {r['meta']['hook_type']}")
    if not refs:
        print("  isi dulu data/reference_watchlist.json (url + transcript)")
        return {"references": 0}
    report = trend_radar.run(cfg)
    db.init()
    db.save_trends([{**r, "hash": trend_radar._h(r["title"])} for r in refs])
    return {"references": len(refs), "clusters": len(report["clusters"])}


def cmd_references(args, cfg) -> dict:
    from . import trends_tiktok

    out = trends_tiktok.run(args.url, args.transcript or "", cfg)
    return out


def cmd_providers(args, cfg) -> dict:
    from . import providers

    base = args.base_url or cfg.get("llm", {}).get("base_url") or "http://localhost:20128/v1"
    key = args.api_key or cfg.get("llm", {}).get("api_key", "")
    models = args.model or None
    out = providers.check_all(base, key, models=models, verbose=not args.json)
    if not args.json:
        print("\n  .env yang disarankan:")
        for line in providers.env_snippet(out["recommend"]).splitlines():
            print("   ", line)
    return out


def cmd_dashboard(args, cfg) -> dict:
    from . import dashboard

    dashboard.serve(args.host, args.port, worker=not args.no_worker)
    return {"served": True}


def cmd_list(args, cfg) -> dict:
    db.init()
    rows = db.list_episodes(limit=args.limit)
    if not args.json:
        print(f"{'episode':44} {'status':17} judul")
        print("-" * 100)
        for r in rows:
            t = json.loads(r["script_json"] or "{}").get("title", "-")
            print(f"{r['id']:44} {r['status']:17} {t[:36]}")
    return {"episodes": rows}


def cmd_run(args, cfg) -> dict:
    """Alur penuh: scan → script → approval → render → QC → paket publish."""
    print("▸ 1/5 Trend Radar")
    report = trend_radar.run(cfg)
    if not report["clusters"]:
        raise SystemExit("tidak ada trend yang lolos filter")
    # _find_cluster() memvalidasi bahwa ada cluster; hasilnya diambil di langkah berikut
    _find_cluster(cfg, args.theme)

    print("\n▸ 2/5 Tulis script")
    res = cmd_script(args, cfg)
    ep_id = res["episode_id"]
    if not res["validation"]["ok"] and args.strict:
        raise SystemExit("script gagal validasi (mode strict)")

    print("\n▸ 3/5 Approval")
    dec = cmd_approve(argparse.Namespace(episode_id=ep_id, wait=args.wait), cfg)
    if dec.get("status") != "approved":
        print(f"\n⏸ berhenti di approval. Lanjutkan dengan: python -m src.cli resume {ep_id}")
        return {"episode_id": ep_id, "stopped_at": "approval", "status": dec.get("status")}

    print("\n▸ 4/5 Render + QC")
    meta = cmd_render(argparse.Namespace(episode_id=ep_id, voice=args.voice), cfg)
    qc_res = cmd_qc(argparse.Namespace(episode_id=ep_id, json=True), cfg)
    if not qc_res["passed"] and args.strict:
        raise SystemExit("QC gagal (mode strict)")

    print("\n▸ 5/5 Publish")
    pub = publish_mod.publish(ep_id, db.get_episode(ep_id)["script"], cfg)
    return {"episode_id": ep_id, "render": meta, "qc": qc_res, "publish": pub}


# ---------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ai-edukasi-agent", description="Pipeline konten AI edukasi TikTok")
    p.add_argument("--json", action="store_true", help="output JSON (untuk agent/cron)")
    # --json harus bisa dipakai SEBELUM maupun SESUDAH subcommand
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="output JSON (untuk agent/cron)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="pindai trend", parents=[common])
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("script", help="tulis script dari tema", parents=[common])
    s.add_argument("--theme", default=None)
    s.set_defaults(fn=cmd_script)

    s = sub.add_parser("approve", help="kirim script untuk ACC", parents=[common])
    s.add_argument("episode_id")
    s.add_argument("--wait", type=int, default=0, help="detik menunggu balasan Telegram")
    s.set_defaults(fn=cmd_approve)

    s = sub.add_parser("resume", help="lanjut dari decision.json", parents=[common])
    s.add_argument("episode_id")
    s.add_argument("--wait", type=int, default=0)
    s.add_argument("--voice", default=None)
    s.set_defaults(fn=cmd_resume)

    s = sub.add_parser("render", help="render video", parents=[common])
    s.add_argument("episode_id")
    s.add_argument("--voice", default=None)
    s.set_defaults(fn=cmd_render)

    s = sub.add_parser("qc", help="QC teknis video", parents=[common])
    s.add_argument("episode_id")
    s.set_defaults(fn=cmd_qc)

    s = sub.add_parser("publish", help="paket upload / kirim TikTok", parents=[common])
    s.add_argument("episode_id")
    s.add_argument("--mode", choices=["manual", "draft", "direct"], default=None)
    s.set_defaults(fn=cmd_publish)

    s = sub.add_parser("metrics", help="catat performa", parents=[common])
    s.add_argument("episode_id")
    for f in ("views", "likes", "comments", "shares"):
        s.add_argument(f"--{f}", type=int, default=0)
    s.add_argument("--avg-watch", dest="avg_watch", type=float, default=0.0)
    s.set_defaults(fn=cmd_metrics)

    s = sub.add_parser("list", help="lihat semua episode", parents=[common])
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("enqueue", help="masukkan job ke antrean", parents=[common])
    s.add_argument("kind", choices=["scan", "script", "approve", "render", "qc", "publish", "learn"])
    s.add_argument("episode_id", nargs="?", default=None)
    s.add_argument("--theme", default=None)
    s.add_argument("--mode", default=None)
    s.add_argument("--voice", default=None)
    s.set_defaults(fn=cmd_enqueue)

    s = sub.add_parser("worker", help="jalankan worker antrean", parents=[common])
    s.add_argument("--once", action="store_true")
    s.add_argument("--poll", type=float, default=2.0)
    s.add_argument("--max-jobs", type=int, default=0)
    s.set_defaults(fn=cmd_worker)

    s = sub.add_parser("jobs", help="lihat antrean", parents=[common])
    s.add_argument("--limit", type=int, default=25)
    s.set_defaults(fn=cmd_jobs)

    s = sub.add_parser("learn", help="laporan learning loop", parents=[common])
    s.set_defaults(fn=cmd_learn)

    s = sub.add_parser("doctor", help="diagnosa lingkungan (ffmpeg, paket, 9Router)",
                       parents=[common])
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("studio", help="agent bekerja sendiri: riset→skrip→ACC→produksi",
                       parents=[common])
    s.add_argument("--once", action="store_true", help="satu langkah kerja lalu keluar")
    s.add_argument("--tick", type=float, default=None, help="detik antar langkah (default 15)")
    s.add_argument("--quiet", action="store_true", help="tanpa log progres")
    s.add_argument("--network", action="store_true", help="doctor: uji respons LLM")
    s.set_defaults(fn=cmd_studio)

    s = sub.add_parser("watch", help="mode kerja selama laptop menyala", parents=[common])
    s.add_argument("--interval", type=float, default=6.0, help="jam antar siklus")
    s.add_argument("--once", action="store_true", help="satu siklus lalu keluar")
    s.set_defaults(fn=cmd_watch)

    s = sub.add_parser("revise", help="revisi satu aspek script", parents=[common])
    s.add_argument("episode_id", nargs="?", default=None)
    s.add_argument("aspect", nargs="?", default="list",
                   help="hook|body|narration|visual|length|caption|sources|list")
    s.add_argument("instruction", nargs="?", default=None, help="instruksi revisi")
    s.add_argument("--shortcut", default=None, help="pakai instruksi siap pakai")
    s.set_defaults(fn=cmd_revise)

    s = sub.add_parser("harvest", help="proses watchlist referensi jadi sinyal", parents=[common])
    s.set_defaults(fn=cmd_harvest)

    s = sub.add_parser("references", help="amati pola video TikTok/YouTube", parents=[common])
    s.add_argument("url", nargs="?", default="")
    s.add_argument("--transcript", default=None, help="transkrip/ringkasan video referensi")
    s.set_defaults(fn=cmd_references)

    s = sub.add_parser("providers", help="cek model mana yang benar-benar jalan", parents=[common])
    s.add_argument("--base-url", default=None, help="default http://localhost:20128/v1")
    s.add_argument("--api-key", default=None)
    s.add_argument("--model", action="append", default=None, help="cek model tertentu (bisa diulang)")
    s.set_defaults(fn=cmd_providers)

    s = sub.add_parser("dashboard", help="jalankan dashboard web", parents=[common])
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--no-worker", action="store_true")
    s.set_defaults(fn=cmd_dashboard)

    s = sub.add_parser("run", help="alur lengkap sekali jalan", parents=[common])
    s.add_argument("--theme", default=None)
    s.add_argument("--wait", type=int, default=0)
    s.add_argument("--voice", default=None)
    s.add_argument("--strict", action="store_true", help="berhenti kalau validasi/QC gagal")
    s.set_defaults(fn=cmd_run)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.json = getattr(args, "json", False)
    cfg = load_config()
    try:
        if args.json:  # log manusia jangan mengotori stdout yang diparse agent
            import contextlib
            import io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = args.fn(args, cfg)
            for line in buf.getvalue().splitlines():
                print(line, file=sys.stderr)
        else:
            result = args.fn(args, cfg)
    except SystemExit:
        raise
    except Exception as e:
        print(f"✖ gagal: {e}", file=sys.stderr)
        if args.json:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
