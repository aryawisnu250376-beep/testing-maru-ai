"""APPROVAL GATE — titik di mana manusia memegang kendali.

Tiga mode, dipilih otomatis:
  1. telegram  — kalau TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID diisi (rekomendasi:
                 bisa ACC dari HP sambil rebahan, ini yang dipakai Hermes)
  2. cli       — kalau dijalankan di terminal interaktif
  3. file      — default aman untuk otomasi: menunggu file `decision.json`

Aturan: TIDAK ADA render yang jalan sebelum status = approved.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import db
from .config import out_dir


# ---------------------------------------------------------------- message

def build_message(script: dict, cluster: dict | None = None) -> str:
    lines = [
        "🎬 *SCRIPT SIAP DIREVIEW*",
        f"_{script.get('title', '')}_",
        f"format: `{script.get('format')}` · generator: `{script.get('generator')}`",
        "",
    ]
    for i, b in enumerate(script.get("beats", []), 1):
        icon = {"hook": "🪝", "point": "•", "limit": "⚠️", "cta": "➡️"}.get(b.get("kind"), "•")
        lines.append(f"{icon} *{i}. {b.get('headline', '')}*")
        lines.append(f"   {b.get('narration', '')}")
    lines += [
        "",
        f"📝 caption: {script.get('caption', '')}",
        f"#️⃣ {' '.join(script.get('hashtags', []))}",
        "",
        f"📚 sumber ({len(script.get('sources', []))}):",
    ]
    for s in script.get("sources", [])[:5]:
        lines.append(f"   – {s.get('title', '')[:60]} → {s.get('url', '')}")
    est = sum(len(b.get("narration", "").split()) for b in script.get("beats", []))
    lines += ["", f"≈ {est} kata ≈ {est / 2.6:.0f} detik video"]
    lines += ["", "Balas: *ACC* / *TOLAK* / *EDIT: <instruksi>*"]
    return "\n".join(lines)


# ---------------------------------------------------------------- transports

def _tg_call(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _send_telegram(cfg: dict, episode_id: str, script: dict, cluster: dict | None,
                   cover: str | None = None) -> str | None:
    token = cfg["telegram"]["bot_token"]
    chat = cfg["telegram"]["chat_id"]
    text = build_message(script, cluster)
    if len(text) > 4000:
        text = text[:3900] + "\n… (dipotong)"
    r = _tg_call(token, "sendMessage", {
        "chat_id": chat, "text": text, "parse_mode": "Markdown",
        "disable_web_page_preview": "true",
        "reply_markup": json.dumps({"inline_keyboard": [[
            {"text": "✅ ACC", "callback_data": f"acc:{episode_id}"},
            {"text": "❌ Tolak", "callback_data": f"rej:{episode_id}"},
        ]]})
    })
    if not r.get("ok"):
        print(f"  [warn] telegram gagal: {r}")
        return None
    msg_id = r.get("result", {}).get("message_id")
    if cover and Path(cover).exists():
        _tg_call(token, "sendPhoto", {"chat_id": chat, "caption": "preview scene 1"})
    return str(msg_id)


def _poll_telegram(cfg: dict, episode_id: str, timeout_sec: int) -> tuple[str, str] | None:
    """Long-poll balasan. Return (decision, instruction) atau None kalau timeout."""
    token = cfg["telegram"]["bot_token"]
    chat = str(cfg["telegram"]["chat_id"])
    deadline = time.time() + timeout_sec
    offset = None
    while time.time() < deadline:
        payload = {"timeout": "25"}
        if offset:
            payload["offset"] = str(offset)
        r = _tg_call(token, "getUpdates", payload)
        for upd in r.get("result", []):
            offset = upd["update_id"] + 1
            msg = upd.get("message") or {}
            cb = upd.get("callback_query") or {}
            if cb:
                data = cb.get("data", "")
                if data.startswith(f"acc:{episode_id}"):
                    return "approve", ""
                if data.startswith(f"rej:{episode_id}"):
                    return "reject", ""
                continue
            if str(msg.get("chat", {}).get("id")) != chat:
                continue
            text = (msg.get("text") or "").strip()
            low = text.lower()
            if low in ("acc", "acc ✅", "ok", "yes", "ya", "setuju"):
                return "approve", ""
            if low in ("tolak", "reject", "no", "tidak", "gak"):
                return "reject", ""
            if low.startswith("edit:"):
                return "edit", text[5:].strip()
    return None


def _ask_cli(episode_id: str, script: dict) -> tuple[str, str]:
    print("\n" + "=" * 68)
    print(build_message(script))
    print("=" * 68)
    while True:
        ans = input("\n[acc / tolak / edit: instruksi] > ").strip()
        low = ans.lower()
        if low in ("acc", "a", "ok", "ya", "y"):
            return "approve", ""
        if low in ("tolak", "t", "no", "n"):
            return "reject", ""
        if low.startswith("edit:"):
            return "edit", ans[5:].strip()


# ---------------------------------------------------------------- main

def request_approval(episode_id: str, script: dict, cfg: dict,
                     cluster: dict | None = None, cover: str | None = None,
                     wait_sec: int = 0) -> dict:
    """Kirim script untuk direview. `wait_sec=0` -> tidak menunggu (mode queue)."""
    d = out_dir(episode_id)
    previous = db.get_episode(episode_id)
    if previous and previous.get("script") and script_fingerprint(previous["script"]) != script_fingerprint(script):
        invalidate(episode_id, "Naskah dikirim ulang dengan isi berbeda")
    (d / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    db.init()
    db.save_episode(episode_id, "pending_approval", cluster or {}, script,
                    {"script": str(d / "script.json")})

    has_tg = bool(cfg["telegram"]["bot_token"] and cfg["telegram"]["chat_id"])
    msg_id = None
    if has_tg:
        msg_id = _send_telegram(cfg, episode_id, script, cluster, cover)
        print(f"  → script dikirim ke Telegram (msg {msg_id})")

    if not wait_sec:
        _write_pending(episode_id, script, "telegram" if msg_id else "manual")
        return {"status": "pending_approval", "channel": "telegram" if msg_id else "manual",
                "decision_file": str(d / "decision.json")}

    if msg_id:
        got = _poll_telegram(cfg, episode_id, wait_sec)
    elif sys.stdin.isatty():
        got = _ask_cli(episode_id, script)
    else:
        got = None  # non-interaktif (cron/Hermes): tunggu decision.json

    if got is None:
        _write_pending(episode_id, script, "waiting")
        return {"status": "pending_approval", "channel": "timeout",
                "decision_file": str(d / "decision.json")}

    decision, instruction = got
    return apply_decision(episode_id, decision, instruction)


def _write_pending(episode_id: str, script: dict, channel: str) -> None:
    d = out_dir(episode_id)
    p = d / "decision.json"
    if not p.exists():
        p.write_text(json.dumps({
            "status": "pending",
            "channel": channel,
            "how_to": "Tinjau naskah dan sumber, lalu ACC lewat studio/CLI. Keputusan manusia dicatat dengan sidik naskah oleh python -m src.cli resume " + episode_id,
            "title": script.get("title"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")


def read_decision(episode_id: str) -> dict | None:
    p = out_dir(episode_id) / "decision.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def script_fingerprint(script: dict) -> str:
    """ACC binds to the exact script, not merely to an episode ID."""
    raw = json.dumps(script, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _atomic_json(path: Path, value: dict) -> None:
    fd, name = tempfile.mkstemp(prefix=".decision-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def approval_error(episode_id: str, script: dict | None = None) -> str | None:
    ep = db.get_episode(episode_id)
    if not ep:
        return "Episode tidak ditemukan."
    dec = read_decision(episode_id)
    if not dec or dec.get("status") != "approve":
        return "Belum di-ACC. Render diblokir."
    current = script if script is not None else (ep.get("script") or {})
    if dec.get("script_sha256") != script_fingerprint(current):
        return "Naskah berubah setelah ACC. Tinjau dan setujui ulang sebelum render."
    if ep.get("status") not in ("approved", "rendering", "rendered", "published"):
        return "Status episode tidak mengizinkan render."
    return None


def require_approval(episode_id: str, script: dict | None = None) -> None:
    error = approval_error(episode_id, script)
    if error:
        raise PermissionError(error)


def invalidate(episode_id: str, reason: str = "Naskah direvisi") -> None:
    _atomic_json(out_dir(episode_id) / "decision.json", {
        "status": "pending", "at": db.now(), "reason": reason,
    })
    db.log_event(episode_id, "approval_invalidated", {"reason": reason})


def apply_decision(episode_id: str, decision: str, instruction: str = "") -> dict:
    db.init()
    ep = db.get_episode(episode_id)
    if not ep:
        raise ValueError("Episode tidak ditemukan.")
    if decision not in ("approve", "reject", "edit"):
        raise ValueError("Keputusan tidak valid.")
    d = out_dir(episode_id)
    if decision == "approve":
        if ep["status"] not in ("pending_approval", "draft", "approved"):
            raise ValueError("Hanya naskah draft/menunggu ACC yang dapat disetujui.")
        from .config import load_config
        from .scriptwriter import validate_script
        ok, errors, _ = validate_script(ep.get("script") or {}, load_config())
        if not ok:
            raise ValueError("Naskah belum lolos validasi: " + "; ".join(errors))
        digest = script_fingerprint(ep["script"])
        _atomic_json(d / "decision.json", {"status": "approve", "at": db.now(),
                                          "script_sha256": digest, "via": "human"})
        db.set_status(episode_id, "approved", via="human", script_sha256=digest)
        return {"status": "approved", "script_sha256": digest}
    if decision == "reject":
        _atomic_json(d / "decision.json", {"status": "reject", "at": db.now(), "via": "human"})
        db.set_status(episode_id, "rejected", via="human")
        return {"status": "rejected"}
    invalidate(episode_id, "Revisi diminta manusia")
    db.set_status(episode_id, "pending_approval", via="human")
    db.log_event(episode_id, "edit_request", {"instruction": instruction[:2000]})
    return {"status": "edit", "instruction": instruction}
