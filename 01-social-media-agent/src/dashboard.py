"""Authenticated mobile studio. HTTP requests enqueue work; they never render.

The UI and all data endpoints require a bearer session. Only login, health and
non-sensitive PWA shell assets are public. No API key is accepted from a browser.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import db, health, learning, queue, queue4, security
from .config import load_config, out_dir
from .llm import LLM
from .studio_html import PAGE

CFG = load_config()
LLM_INSTANCE = LLM.from_config(CFG)
RUNTIME = security.Runtime(security.AuthManager(""))
SAFE_EP = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
ARTEFACTS = {"script.json", "decision.json", "render_meta.json", "qc_report.json"}
RUNTIME_INFO = {"preflight": {}, "orchestrator": "stopped", "worker": "stopped", "started_at": time.time()}
MAX_BODY = 12 * 1024 * 1024


def _episode_summary(e: dict) -> dict:
    script = e.get("script") or {}
    paths = e.get("paths") or {}
    qc = None
    qpath = out_dir(e["id"])/"qc_report.json"
    if qpath.exists():
        try:
            qc = json.loads(qpath.read_text()).get("passed")
        except Exception:
            pass
    return {"id":e["id"],"status":e["status"],"title":script.get("title","Tanpa judul"),
            "theme":script.get("theme") or (e.get("topic") or {}).get("theme"),
            "generator":script.get("generator","unknown"),"updated_at":e["updated_at"],
            "duration_sec":paths.get("duration_sec"),"has_video":bool(paths.get("video")) and Path(paths["video"]).is_file(),
            "has_cover":(out_dir(e["id"])/"cover.png").is_file(),"qc_passed":qc,
            "beats":len(script.get("beats") or []),"hook":script.get("hook",""),
            "hook_variant":script.get("hook_variant","A"),"experiment_id":script.get("experiment_id"),
            "sources":len(script.get("sources") or []),"recordings":len(script.get("recordings") or {}),
            "metrics":db.latest_metrics(e["id"])}


def state() -> dict:
    db.init()
    episodes = [_episode_summary(e) for e in db.list_episodes(limit=100)]
    report = learning.report()
    llm_cfg = CFG.get("llm",{})
    return {"brand":CFG.get("brand",{}),"episodes":episodes,
            "totals":{"episodes":len(episodes),"rendered":sum(e["has_video"] for e in episodes),
                      "pending":sum(e["status"]=="pending_approval" for e in episodes)},
            "jobs":queue.list_jobs(limit=20),"learning":report,
            "runtime":{**RUNTIME_INFO,"uptime_sec":round(time.time()-RUNTIME_INFO["started_at"])},
            "video":{k:CFG.get("video",{}).get(k) for k in ("style","caption_style","voice","allow_silent_fallback")},
            "llm":{"configured":LLM_INSTANCE.available,"verified":any(p.calls > 0 for p in LLM_INSTANCE.providers),
                   "model":llm_cfg.get("model",""),"stats":LLM_INSTANCE.stats().get("providers",[])},
            "publish_mode":"manual","autonomy":CFG.get("autonomy",{}),
            "aspects":__import__("src.revisor",fromlist=["ASPECTS"]).ASPECTS,
            "shortcuts":[{"key":k,"label":v[0].replace("_"," ")+" · "+v[1][:65]} for k,v in __import__("src.revisor",fromlist=["SHORTCUTS"]).SHORTCUTS.items()],
            "server_time":db.now(),
            "queue4":queue4.list_items()}


def studio_state() -> dict:
    from .agents import snapshot
    db.init()
    snap = snapshot()
    pending = [_episode_summary(e) for e in db.list_episodes(status="pending_approval",limit=20)]
    from .revisor import SHORTCUTS
    shortcuts = [{"key":k,"label":v[0].replace("_"," ")+" · "+v[1][:70]} for k,v in SHORTCUTS.items()]
    return {**snap,"pending":pending,"shortcuts":shortcuts,"totals":{"pending":len(pending)},
            "runtime":RUNTIME_INFO,"server_time":db.now()}


def episode_detail(ep: str) -> dict:
    e = db.get_episode(ep)
    if not e:
        raise ValueError("Episode tidak ditemukan")
    from .revisor import history
    from .scriptwriter import validate_script
    ok, errors, warnings = validate_script(e.get("script") or {},CFG)
    return {**_episode_summary(e),"script":e.get("script"),"topic":e.get("topic"),
            "validation":{"ok":ok,"errors":errors,"warnings":warnings},
            "revisions":history(ep),"tasks":db.tasks_for_episode(ep)}


def _require_ep(ep: str) -> dict:
    if not SAFE_EP.fullmatch(ep or ""):
        raise ValueError("ID episode tidak valid")
    e = db.get_episode(ep)
    if not e:
        raise ValueError("Episode tidak ditemukan")
    return e


def action(payload: dict) -> dict:
    if not isinstance(payload,dict):
        raise ValueError("Payload harus objek")
    act = payload.get("action","")
    ep = str(payload.get("episode_id") or "").strip()
    if act in ("approve","reject","render","qc","revise","metrics","select_hook","upload_voice","delete_voice"):
        _require_ep(ep)
    if act == "approve":
        if payload.get("confirmed") is not True:
            raise ValueError("Konfirmasi tinjauan naskah dan sumber diperlukan")
        from . import agents, approve
        res = approve.apply_decision(ep,"approve")
        agents.clear_waiting(ep,"done")
        return res
    if act == "reject":
        if payload.get("confirmed") is not True:
            raise ValueError("Konfirmasi penolakan diperlukan")
        from . import agents, approve
        res = approve.apply_decision(ep,"reject")
        agents.clear_waiting(ep,"done")
        return res
    if act == "revise":
        from . import approve, revisor
        e = db.get_episode(ep)
        if e["status"] in ("rendering","approved"):
            raise ValueError("Episode sedang diproduksi; tunggu selesai sebelum revisi")
        aspect = str(payload.get("aspect") or "hook")
        instruction = str(payload.get("instruction") or "")[:2000]
        if payload.get("shortcut"):
            pair = revisor.SHORTCUTS.get(payload["shortcut"])
            if not pair:
                raise ValueError("Shortcut tidak dikenal")
            aspect,instruction = pair
        if aspect not in revisor.ASPECTS:
            raise ValueError("Aspek revisi tidak valid")
        res = revisor.apply_revision(ep,aspect,instruction,CFG)
        res.pop("script",None)
        return res
    if act == "render":
        from . import approve
        approve.require_approval(ep)
        e = db.get_episode(ep)
        if e["status"] == "rendering":
            raise ValueError("Episode sedang dirender")
        if e["status"] == "failed":
            db.set_status(ep,"approved",reason="Percobaan ulang diminta manusia")
        return {"queued":queue.enqueue("render",ep,max_attempts=3)}
    if act == "qc":
        e = db.get_episode(ep)
        if not (e.get("paths") or {}).get("video"):
            raise ValueError("Video belum tersedia")
        return {"queued":queue.enqueue("qc",ep)}
    if act == "publish":
        e = _require_ep(ep)
        if not e.get("paths",{}).get("video"):
            raise ValueError("Video belum tersedia")
        from . import approve
        approve.require_approval(ep)
        qpath=out_dir(ep)/"qc_report.json"
        if not qpath.is_file() or not json.loads(qpath.read_text()).get("passed"):
            raise ValueError("QC harus lulus sebelum paket upload dibuat")
        return {"queued":queue.enqueue("publish",ep,{"mode":"manual"})}
    if act == "metrics":
        m = db.validate_metrics(ep,payload)
        db.save_metrics(ep,m)
        insight = learning.apply_insights(CFG)
        db.log_event(ep,"metrics_recorded",{"views":m["views"],"hook_variant":m["hook_variant"]})
        return {"saved":True,"metrics":db.latest_metrics(ep),"learning":insight}
    if act == "select_hook":
        from . import approve
        e = db.get_episode(ep)
        if e["status"] not in ("draft","pending_approval"):
            raise ValueError("Pilih hook sebelum ACC")
        script = e["script"]
        choice = payload.get("variant")
        option = next((o for o in script.get("hook_options",[]) if o["id"]==choice),None)
        if not option:
            raise ValueError("Varian hook tidak tersedia")
        script["hook"] = option["text"]
        script["hook_variant"] = choice
        script["beats"][0]["narration"] = option["text"]
        script.setdefault("experiment_id",ep)
        approve.invalidate(ep,"Varian hook diganti")
        db.save_episode(ep,"pending_approval",e["topic"],script)
        (out_dir(ep)/"script.json").write_text(json.dumps(script,ensure_ascii=False,indent=2))
        return {"saved":True,"variant":choice}
    if act in ("upload_voice","delete_voice"):
        from . import approve, voice
        e = db.get_episode(ep)
        if e["status"] not in ("draft","pending_approval"):
            raise ValueError("Ubah rekaman hanya sebelum ACC")
        script = e["script"]
        index = payload.get("beat_index")
        if type(index) is not int or not 0 <= index < len(script.get("beats",[])):
            raise ValueError("Indeks beat tidak valid")
        recordings = dict(script.get("recordings") or {})
        if act == "upload_voice":
            target = out_dir(ep)/"work"/f"recording_{index:02d}.wav"
            meta = voice.import_recording(str(payload.get("audio_base64") or ""),target,payload.get("consent"))
            import hashlib
            meta["source_sha256"] = meta.pop("sha256")
            meta["file_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            meta["at"] = db.now()
            recordings[str(index)] = meta
        else:
            recordings.pop(str(index),None)
        script["recordings"] = recordings
        approve.invalidate(ep,"Rekaman narasi berubah")
        db.save_episode(ep,"pending_approval",e["topic"],script)
        (out_dir(ep)/"script.json").write_text(json.dumps(script,ensure_ascii=False,indent=2))
        return {"saved":True,"recordings":len(recordings)}
    if act == "check_models":
        if not CFG.get("llm",{}).get("base_url"):
            return {"error":"LLM belum dikonfigurasi. Isi .env di server, lalu restart. Jangan kirim API key lewat browser."}
        return {"queued":queue.enqueue("check_models",max_attempts=1)}
    if act == "learn":
        return learning.apply_insights(CFG)
    if act == "queue4_decision":
        cid = str(payload.get("content_id") or "")
        decision = str(payload.get("decision") or "").upper()
        reason = str(payload.get("reason") or "")[:500]
        jadwal = payload.get("jadwal") or None
        return queue4.owner_decision(cid, decision, reason, jadwal)
    if act == "queue4_hermes":
        path = str(payload.get("path") or "")
        topic = str(payload.get("topic") or "")[:120]
        return {"queued": queue.enqueue("hermes", payload={"path": path, "topic": topic}, max_attempts=1)}
    if act == "ootto_schedule":
        from ootto import jadwalkan
        return jadwalkan(str(payload.get("content_id") or ""), str(payload.get("waktu") or ""))
    if act == "ootto_cancel":
        from ootto import batalkan
        return batalkan(str(payload.get("content_id") or ""))
    if act == "ootto_run_due":
        from ootto import run_due
        return {"processed": len(run_due())}
    if act == "router_test":
        from . import router9
        return router9.test_question()
    raise ValueError("Aksi tidak dikenal atau tidak tersedia dari handphone")


def _worker_thread() -> None:
    RUNTIME_INFO["worker"] = "running"
    try:
        queue.worker(poll_sec=2)
    except Exception:
        RUNTIME_INFO["worker"] = "failed"
        RUNTIME_INFO["worker_error"] = "Worker berhenti. Periksa log server dan restart."


def _orchestrator_thread() -> None:
    from . import orchestrator
    RUNTIME_INFO["orchestrator"] = "running"
    try:
        orchestrator.run(CFG,once=False,quiet=False)
    except Exception:
        RUNTIME_INFO["orchestrator"] = "failed"


class Handler(BaseHTTPRequestHandler):
    server_version = "NaraStudio/2.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Never log request paths (episode IDs) or authorization headers.
        pass

    def _token(self) -> str:
        value = self.headers.get("Authorization","")
        return value[7:] if value.startswith("Bearer ") else ""

    def _send(self,code:int,body:bytes,ctype="application/json",extra=None):
        self.send_response(code)
        self.send_header("Content-Type",ctype)
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        origin = self.headers.get("Origin", "")
        allowed = set(filter(None,os.getenv("STUDIO_ALLOWED_ORIGINS","").split(",")))
        allowed.update(("null","https://"+self.headers.get("Host","")))
        if origin in allowed:
            self.send_header("Access-Control-Allow-Origin",origin)
            self.send_header("Vary","Origin")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Permissions-Policy","microphone=(self), camera=(), geolocation=()")
        # No frame restriction: the Arena live preview embeds this application.
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'")
        for k,v in (extra or {}).items():
            self.send_header(k,v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):
            pass

    def _json(self,obj,code=200):
        self._send(code,json.dumps(obj,ensure_ascii=False,default=str).encode())

    def do_OPTIONS(self):
        self._send(204,b"",extra={"Access-Control-Allow-Methods":"GET, POST, OPTIONS",
                                 "Access-Control-Allow-Headers":"Authorization, Content-Type",
                                 "Access-Control-Max-Age":"600"})

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self,head=False):
        path=urllib.parse.urlparse(self.path).path
        if path=="/healthz":
            return self._json({"ok":True,"service":"nara-studio"})
        if path=="/manifest.webmanifest":
            data={"name":"Nara — AI Edukasi Studio","short_name":"Nara Studio","lang":"id","start_url":"/","scope":"/","display":"standalone","background_color":"#f6f7f2","theme_color":"#205c4b","icons":[{"src":"/icon-192.png","sizes":"192x192","type":"image/png","purpose":"any maskable"},{"src":"/icon-512.png","sizes":"512x512","type":"image/png","purpose":"any maskable"}]}
            return self._send(200,json.dumps(data).encode(),"application/manifest+json")
        if path in ("/icon.svg","/icon-192.png","/icon-512.png"):
            from .config import ROOT
            if path!="/icon.svg":
                return self._send(200,(ROOT/"assets"/path[1:]).read_bytes(),"image/png",{"Cache-Control":"public,max-age=86400"})
            svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"><rect width="192" height="192" rx="44" fill="#205c4b"/><rect x="45" y="45" width="102" height="102" rx="20" fill="#deedbd"/><text x="96" y="117" font-family="sans-serif" font-size="75" font-weight="bold" text-anchor="middle" fill="#205c4b">n.</text></svg>'
            return self._send(200,svg.encode(),"image/svg+xml")
        if path=="/sw.js":
            return self._send(200,b"self.addEventListener('fetch',()=>{});","application/javascript")
        if path in ("/","/index.html"):
            return self._send(200,b"" if head else PAGE.encode(),"text/html; charset=utf-8")
        if not RUNTIME.auth.valid(self._token()):
            return self._json({"error":"Silakan masuk kembali"},401)
        try:
            if path=="/api/state":
                return self._json(state())
            if path=="/api/studio":
                return self._json(studio_state())
            if path=="/api/queue4":
                return self._json({"items":queue4.list_items()})
            if path.startswith("/api/episode/"):
                return self._json(episode_detail(path.rsplit("/",1)[-1]))
            if path.startswith("/video/"):
                return self._file(path.rsplit("/",1)[-1],"final.mp4","video/mp4",head)
            if path.startswith("/cover/"):
                return self._file(path.rsplit("/",1)[-1],"cover.png","image/png",head)
            if path.startswith("/artefact/"):
                parts=path.split("/")
                if len(parts)==4 and parts[3] in ARTEFACTS:
                    return self._file(parts[2],parts[3],"application/json",head)
            if path.startswith("/package/"):
                return self._file(path.rsplit("/",1)[-1],"upload-package.zip","application/zip",head)
        except Exception:
            return self._json({"error":"Data tidak dapat dibaca. Periksa log server."},500)
        return self._json({"error":"Tidak ditemukan"},404)

    def _file(self,ep,filename,ctype,head=False):
        if not SAFE_EP.fullmatch(ep) or not db.get_episode(ep):
            return self._json({"error":"Tidak ditemukan"},404)
        path=out_dir(ep)/filename
        if not path.is_file():
            return self._json({"error":"Berkas belum tersedia"},404)
        size=path.stat().st_size
        start,end=0,size-1
        code=200
        rng=self.headers.get("Range")
        if rng:
            m=re.fullmatch(r"bytes=(\d*)-(\d*)",rng)
            if not m or not any(m.groups()):
                return self._send(416,b"",ctype,{"Content-Range":f"bytes */{size}"})
            if m[1]:
                start=int(m[1])
                end=min(end,int(m[2]) if m[2] else end)
            else:
                start=max(0,size-int(m[2]))
            if start>=size or end<start:
                return self._send(416,b"",ctype,{"Content-Range":f"bytes */{size}"})
            code=206
        length=end-start+1
        self.send_response(code)
        self.send_header("Content-Type",ctype)
        self.send_header("Content-Length",str(length))
        self.send_header("Accept-Ranges","bytes")
        self.send_header("Cache-Control","private, no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        if code==206:
            self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
        if filename.endswith(".zip"):
            self.send_header("Content-Disposition",'attachment; filename="nara-upload-package.zip"')
        self.end_headers()
        if head:
            return
        with path.open("rb") as f:
            f.seek(start)
            remaining=length
            while remaining:
                data=f.read(min(65536,remaining))
                if not data:
                    break
                self.wfile.write(data)
                remaining-=len(data)

    def do_POST(self):
        path=urllib.parse.urlparse(self.path).path
        if path not in ("/api/login","/api/logout","/api/action"):
            return self._json({"error":"Tidak ditemukan"},404)
        # Bearer authentication is not ambient; also reject cross-origin browser writes.
        origin=self.headers.get("Origin")
        if origin:
            parsed=urllib.parse.urlparse(origin)
            allowed = set(filter(None,os.getenv("STUDIO_ALLOWED_ORIGINS","").split(",")))
            if parsed.netloc and parsed.netloc!=self.headers.get("Host") and origin not in allowed:
                return self._json({"error":"Origin tidak diizinkan"},403)
        if not self.headers.get("Content-Type","").startswith("application/json"):
            return self._json({"error":"Gunakan application/json"},415)
        try:
            n=int(self.headers.get("Content-Length","0"))
            if not 0<n<=MAX_BODY:
                self.close_connection=True
                return self._json({"error":"Ukuran permintaan tidak valid"},413)
            payload=json.loads(self.rfile.read(n))
            if not isinstance(payload,dict):
                raise ValueError()
        except Exception:
            self.close_connection=True
            return self._json({"error":"JSON tidak valid"},400)
        if path=="/api/login":
            token,wait=RUNTIME.auth.login(str(payload.get("password") or ""),self.client_address[0])
            if not token:
                return self._json({"error":"Kata sandi salah atau terlalu banyak percobaan.","retry_after":wait},429 if wait else 401)
            return self._json({"token":token,"expires_in":wait})
        if not RUNTIME.auth.valid(self._token()):
            return self._json({"error":"Silakan masuk kembali"},401)
        if path=="/api/logout":
            RUNTIME.auth.logout(self._token())
            return self._json({"ok":True})
        try:
            result=action(payload)
            return self._json(result,400 if result.get("error") else 200)
        except (ValueError,PermissionError) as exc:
            return self._json({"error":str(exc)},400)
        except FileNotFoundError:
            return self._json({"error":"Berkas belum tersedia"},404)
        except Exception:
            return self._json({"error":"Aksi gagal. Periksa status sistem dan log server."},500)


def serve(host="127.0.0.1",port=8080,worker=True,orchestrate=True,skip_preflight=False):
    global RUNTIME
    RUNTIME=security.from_environment(host)
    RUNTIME.orchestrate=orchestrate
    db.init()
    report=health.diagnose() if skip_preflight else health.require_healthy()
    RUNTIME_INFO["preflight"]=report
    RUNTIME_INFO["started_at"]=time.time()
    if orchestrate and CFG.get("autonomy",{}).get("enabled",True):
        threading.Thread(target=_orchestrator_thread,daemon=True).start()
    else:
        RUNTIME_INFO["orchestrator"]="paused"
    if worker:
        threading.Thread(target=_worker_thread,daemon=True).start()
    else:
        RUNTIME_INFO["worker"]="paused"
    httpd=ThreadingHTTPServer((host,port),Handler)
    httpd.daemon_threads=True
    print(f"Nara Studio siap di port {port}; login wajib; autonomy={RUNTIME_INFO['orchestrator']}",flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--host",default=os.getenv("HOST","127.0.0.1"))
    ap.add_argument("--port",type=int,default=os.getenv("PORT","8080"))
    ap.add_argument("--no-worker",action="store_true")
    ap.add_argument("--no-orchestrator",action="store_true")
    ap.add_argument("--skip-preflight",action="store_true",help="Mode diagnosa saja; produksi tetap menolak render jika alat hilang")
    a=ap.parse_args()
    serve(a.host,a.port,not a.no_worker,not a.no_orchestrator,a.skip_preflight)
