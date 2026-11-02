"""Startup preflight: required failures block production; optional stays honest."""
from __future__ import annotations

import importlib
import os
import shutil
import subprocess
from pathlib import Path

from .config import ROOT, find_ffmpeg


def diagnose(network: bool = False) -> dict:
    checks = []
    def add(name, ok, detail, required=True, fix=""):
        checks.append({"name":name,"ok":bool(ok),"detail":detail,"required":required,"fix":fix})
    import sys
    add("python",sys.version_info >= (3,11),sys.version.split()[0],fix="Gunakan Python 3.11+")
    for mod, package in (("PIL","Pillow"),("numpy","numpy"),("yaml","PyYAML"),("edge_tts","edge-tts")):
        try:
            importlib.import_module(mod)
            add(package,True,"terpasang")
        except ImportError:
            add(package,False,"tidak terpasang",fix="python -m pip install -r requirements.txt")
    try:
        ff = find_ffmpeg()
            # find_ffmpeg may return a missing 'ffmpeg'; explicitly verify execution.
        filters = subprocess.run([ff,"-hide_banner","-filters"],capture_output=True,text=True,timeout=15)
        add("ffmpeg + libass",filters.returncode == 0 and " subtitles " in filters.stdout,
            ff,fix="Pasang ffmpeg sistem dengan libass; imageio-ffmpeg saja tidak cukup.")
    except Exception as exc:
        add("ffmpeg + libass",False,str(exc)[:100],fix="sudo apt install ffmpeg")
    add("ffprobe",bool(shutil.which("ffprobe")),"diperlukan untuk QC",required=False,fix="Pasang paket ffmpeg sistem")
    for name in ("data","out"):
        try:
            d=Path(ROOT)/name
            d.mkdir(exist_ok=True,parents=True)
            p=d/".preflight"
            p.write_text("ok")
            p.unlink()
            add(name,True,"bisa ditulis")
        except Exception as exc:
            add(name,False,str(exc)[:100])
    for name in ("PlusJakarta.ttf","Outfit.ttf"):
        add(name,(Path(ROOT)/"assets"/"fonts"/name).is_file(),"font video")
    try:
        from . import db
        db.init()
        with db.conn() as c:
            ver=c.execute("PRAGMA user_version").fetchone()[0]
        add("database",True,f"schema v{ver}")
    except Exception as exc:
        add("database",False,str(exc)[:100],fix="Periksa izin dan backup database; jangan hapus data.")
    configured=bool(os.getenv("LLM_BASE_URL") and os.getenv("LLM_MODEL"))
    add("LLM",configured,"terkonfigurasi; belum membuktikan respons" if configured else "belum dikonfigurasi → template berlabel",required=False,
        fix="Isi LLM_BASE_URL, LLM_MODEL dan LLM_API_KEY di .env server")
    if network and configured:
        from .providers import probe_model
        r=probe_model(os.getenv("LLM_BASE_URL"),os.getenv("LLM_API_KEY",""),os.getenv("LLM_MODEL"),timeout=8)
        add("LLM: uji respons",r.get("status")=="ok",r.get("status","unknown"),required=False)
    failed=[c for c in checks if c["required"] and not c["ok"]]
    return {"ok":not failed,"checks":checks,"required_failed":[c["name"] for c in failed]}


def require_healthy() -> dict:
    report=diagnose()
    if not report["ok"]:
        details="; ".join(c["name"]+": "+c["fix"] for c in report["checks"] if c["required"] and not c["ok"])
        raise RuntimeError("Preflight gagal — "+details)
    return report
