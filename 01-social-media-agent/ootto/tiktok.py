"""Konektor TikTok resmi untuk Ootto.

Tidak meminta/menyimpan password. OAuth v2, token disimpan di .env lokal.
Mode bawaan adalah upload ke inbox/draf; pemilik menyelesaikan posting di app.
TikTok Content Posting API tidak menyediakan jadwal publik native untuk semua
akun, jadi Ootto menjadwalkan pengiriman secara lokal lalu mengunggah saat jatuh
tempo. Jangan menjanjikan tayang publik otomatis sebelum audit TikTok lulus.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from src.config import ROOT

API = "https://open.tiktokapis.com/v2"
AUTH = "https://www.tiktok.com/v2/auth/authorize/"
ENV_PATH = ROOT / ".env"
_LOCK = threading.RLock()


def _env_value(key: str) -> str:
    return os.getenv(key, "")


def _save_env(updates: dict[str, str]) -> None:
    """Simpan token OAuth ke .env, bukan ke kode/Git."""
    with _LOCK:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
        seen = set()
        out = []
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line and not line.strip().startswith("#") else None
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
            else:
                out.append(line)
        for key, value in updates.items():
            if key not in seen:
                out.append(f"{key}={value}")
        ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
        try:
            ENV_PATH.chmod(0o600)
        except OSError:
            pass
        os.environ.update(updates)


def authorization_url(redirect_uri: str, scope: str = "video.upload") -> tuple[str, str]:
    client_key = _env_value("TIKTOK_CLIENT_KEY")
    if not client_key:
        raise RuntimeError("TIKTOK_CLIENT_KEY belum diisi di .env")
    state = secrets.token_urlsafe(24)
    query = urllib.parse.urlencode({
        "client_key": client_key, "scope": scope, "response_type": "code",
        "redirect_uri": redirect_uri, "state": state,
    })
    return AUTH + "?" + query, state


def _post_form(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def exchange_code(code: str, redirect_uri: str) -> dict:
    data = _post_form(API + "/oauth/token/", {
        "client_key": _env_value("TIKTOK_CLIENT_KEY"),
        "client_secret": _env_value("TIKTOK_CLIENT_SECRET"),
        "code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri,
    })
    if "access_token" not in data:
        raise RuntimeError("TikTok tidak mengembalikan access_token: " + json.dumps(data)[:300])
    _save_env({
        "TIKTOK_ACCESS_TOKEN": data["access_token"],
        "TIKTOK_REFRESH_TOKEN": data.get("refresh_token", ""),
        "TIKTOK_OPEN_ID": data.get("open_id", ""),
        "TIKTOK_TOKEN_EXPIRES": str(int(time.time()) + int(data.get("expires_in", 86400))),
    })
    return {"open_id": data.get("open_id"), "scope": data.get("scope"), "expires_in": data.get("expires_in")}


def refresh_token() -> dict:
    refresh = _env_value("TIKTOK_REFRESH_TOKEN")
    if not refresh:
        raise RuntimeError("Belum ada refresh token; jalankan otorisasi OAuth dulu")
    data = _post_form(API + "/oauth/token/", {
        "client_key": _env_value("TIKTOK_CLIENT_KEY"),
        "client_secret": _env_value("TIKTOK_CLIENT_SECRET"),
        "grant_type": "refresh_token", "refresh_token": refresh,
    })
    if "access_token" not in data:
        raise RuntimeError("Refresh token gagal: " + json.dumps(data)[:300])
    _save_env({
        "TIKTOK_ACCESS_TOKEN": data["access_token"],
        "TIKTOK_REFRESH_TOKEN": data.get("refresh_token", refresh),
        "TIKTOK_TOKEN_EXPIRES": str(int(time.time()) + int(data.get("expires_in", 86400))),
    })
    return {"expires_in": data.get("expires_in")}


def access_token() -> str:
    token = _env_value("TIKTOK_ACCESS_TOKEN")
    expires = int(_env_value("TIKTOK_TOKEN_EXPIRES") or 0)
    if token and time.time() < expires - 300:
        return token
    refresh_token()
    return _env_value("TIKTOK_ACCESS_TOKEN")


def revoke() -> dict:
    token = _env_value("TIKTOK_ACCESS_TOKEN")
    if not token:
        return {"ok": True, "note": "tidak ada token"}
    data = _post_form(API + "/oauth/revoke/", {
        "client_key": _env_value("TIKTOK_CLIENT_KEY"),
        "client_secret": _env_value("TIKTOK_CLIENT_SECRET"),
        "token": token,
    })
    _save_env({"TIKTOK_ACCESS_TOKEN": "", "TIKTOK_REFRESH_TOKEN": "", "TIKTOK_TOKEN_EXPIRES": "0"})
    return data


def _api(path: str, payload: dict) -> dict:
    req = urllib.request.Request(API + path, data=json.dumps(payload).encode(), headers={
        "Authorization": "Bearer " + access_token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        return {"error": {"http": exc.code, "body": exc.read()[:500].decode(errors="ignore")}}


def _check(resp: dict) -> dict:
    err = resp.get("error") or {}
    if err and err.get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok {err.get('code')}: {err.get('message')}")
    if resp.get("error") and isinstance(resp["error"], dict) and resp["error"].get("http"):
        raise RuntimeError("TikTok HTTP error: " + json.dumps(resp["error"])[:300])
    return resp.get("data") or {}


def upload_draft(item: dict) -> dict:
    """Upload ke inbox TikTok sebagai draf. Pemilik tetap menekan tayang sendiri."""
    video = Path(item["video"])
    size = video.stat().st_size
    resp = _api("/post/publish/inbox/video/init/", {
        "source_info": {
            "source": "FILE_UPLOAD", "video_size": size,
            "chunk_size": size, "total_chunk_count": 1,
        }
    })
    data = _check(resp)
    upload_url, publish_id = data.get("upload_url"), data.get("publish_id")
    if not upload_url or not publish_id:
        raise RuntimeError("TikTok tidak mengembalikan upload_url/publish_id")
    with video.open("rb") as f:
        req = urllib.request.Request(upload_url, data=f.read(), method="PUT", headers={
            "Content-Range": f"bytes 0-{size-1}/{size}", "Content-Type": "video/mp4"})
        with urllib.request.urlopen(req, timeout=300) as r:
            if r.status not in (200, 201, 206):
                raise RuntimeError(f"Upload TikTok gagal: HTTP {r.status}")
    return {"publish_id": publish_id, "status": "draf_di_inbox", "mode": "draft",
            "note": "Buka notifikasi inbox TikTok, aktifkan label AI, lalu tayang manual."}


def direct_post(item: dict) -> dict:
    """Direct post hanya untuk mode yang diminta pemilik dan aplikasi lolos audit."""
    video = Path(item["video"])
    size = video.stat().st_size
    caption = (item.get("caption") or "")[:2200]
    resp = _api("/post/publish/video/init/", {
        "post_info": {
            "title": caption, "privacy_level": "SELF_ONLY",
            "disable_comment": False, "video_cover_timestamp_ms": 1000,
            "is_aigc": True,
        },
        "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                        "chunk_size": size, "total_chunk_count": 1},
    })
    data = _check(resp)
    upload_url, publish_id = data.get("upload_url"), data.get("publish_id")
    if not upload_url or not publish_id:
        raise RuntimeError("TikTok tidak mengembalikan upload_url/publish_id")
    with video.open("rb") as f:
        req = urllib.request.Request(upload_url, data=f.read(), method="PUT", headers={
            "Content-Range": f"bytes 0-{size-1}/{size}", "Content-Type": "video/mp4"})
        with urllib.request.urlopen(req, timeout=300) as r:
            if r.status not in (200, 201, 206):
                raise RuntimeError(f"Upload TikTok gagal: HTTP {r.status}")
    return {"publish_id": publish_id, "status": "terkirim_direct", "mode": "direct",
            "privacy": "SELF_ONLY", "is_aigc": True}


def post_status(publish_id: str) -> dict:
    return _check(_api("/post/publish/status/fetch/", {"publish_id": publish_id}))
