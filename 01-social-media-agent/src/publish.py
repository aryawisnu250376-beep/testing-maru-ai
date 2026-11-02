"""PUBLISH ADAPTER — last mile ke TikTok, dengan tiga jalur.

  manual  : bikin paket siap-upload (mp4 + caption.txt + cover + copy-paste blok).
            Paling aman, 0 risiko.  ← default
  draft   : upload ke inbox TikTok (post_mode=MEDIA_UPLOAD), kamu tinggal buka
            aplikasi dan tap publish. Aman, butuh app TikTok + OAuth.
  direct  : auto-post publik (post_mode=DIRECT_POST).
            ⚠️ BUTUH AUDIT TikTok. Selama belum audit, konten dipaksa SELF_ONLY
            dan akun harus private. Jangan dipakai sebelum lulus audit.

Semua jalur menerima input yang sama, jadi pindah jalur = ganti satu setting.
"""
from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import db
from .config import out_dir

TIKTOK_API = "https://open.tiktokapis.com/v2"
MAX_CAPTION = 2200


def build_package(episode_id: str, script: dict, cfg: dict) -> dict:
    """Paket siap-upload. Ini juga yang dipakai kalau mode=manual."""
    d = out_dir(episode_id)
    pub = d / "publish"
    pub.mkdir(exist_ok=True)

    video = d / "final.mp4"
    cover = d / "cover.png"
    if video.exists():
        shutil.copy2(video, pub / "video.mp4")
    if cover.exists():
        shutil.copy2(cover, pub / "cover.png")

    caption = (script.get("caption") or "").strip()
    tags = " ".join(script.get("hashtags") or cfg.get("publish", {}).get("default_hashtags", []))
    disclosure = "🤖 konten dibuat dengan bantuan AI" if cfg.get("publish", {}).get("disclosure", {}).get("ai_generated") else ""
    full = f"{caption}\n\n{tags}"
    if disclosure:
        full += f"\n\n{disclosure}"
    full = full[:MAX_CAPTION]

    (pub / "caption.txt").write_text(full, encoding="utf-8")
    package = {
        "episode_id": episode_id,
        "video": str(pub / "video.mp4"),
        "cover": str(pub / "cover.png"),
        "caption": caption,
        "hashtags": tags,
        "disclosure": disclosure,
        "full_caption": full,
        "sources": script.get("sources", []),
        "mode": cfg.get("publish", {}).get("mode", "manual"),
        "note": "Buka TikTok → upload video.mp4 → tempel isi caption.txt → pilih cover.png",
    }
    (pub / "package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    (pub / "SIAP_UPLOAD.md").write_text(_howto_md(package), encoding="utf-8")
    import zipfile
    with zipfile.ZipFile(d / "upload-package.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in (pub / "video.mp4", pub / "cover.png", pub / "caption.txt", pub / "SIAP_UPLOAD.md"):
            if p.is_file():
                z.write(p, p.name)
        z.writestr("sources.json", json.dumps(script.get("sources", []), ensure_ascii=False, indent=2))
        z.writestr("script.json", json.dumps(script, ensure_ascii=False, indent=2))

    return package


def _howto_md(p: dict) -> str:
    src = "\n".join(f"- {s['title']} — {s['url']}" for s in p["sources"])
    return f"""# Siap upload — {p['episode_id']}

Video : `video.mp4`  (1080x1920, siap TikTok)
Cover : `cover.png`
Mode  : `{p['mode']}`

## Langkah (manual, ±30 detik)
1. Kirim `video.mp4` + `cover.png` ke HP (WhatsApp sendiri / Google Drive / kabel).
2. Buka TikTok → **+** → Upload → pilih `video.mp4`.
3. Pilih cover → `cover.png`.
4. Tempel caption di bawah.
5. **Wajib:** aktifkan label *"Konten yang dihasilkan AI"* di menu lainnya.
6. Posting.

## Caption (copy-paste)
```
{p['full_caption']}
```

## Sumber (taruh di komentar pertama, biar kredibel)
{src}
"""


# ---------------------------------------------------------------- tiktok api

def _api(path: str, payload: dict, token: str) -> dict:
    req = urllib.request.Request(
        TIKTOK_API + path,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": {"http": e.code, "body": e.read()[:500].decode(errors="ignore")}}


def creator_info(token: str) -> dict:
    """Wajib dipanggil sebelum post: TikTok mewajibkan menampilkan info creator
    dan privacy_level harus salah satu dari privacy_level_options."""
    return _api("/post/publish/creator_info/query/", {}, token)


def init_video_post(token: str, video_path: Path, caption: str, mode: str,
                    privacy: str = "SELF_ONLY") -> dict:
    """Dua mode:
    - draft  (MEDIA_UPLOAD) : masuk inbox, user selesaikan di app
    - direct (DIRECT_POST)  : langsung publish (butuh audit)
    """
    size = video_path.stat().st_size
    payload = {
        "post_info": {
            "title": caption,
            "privacy_level": privacy if mode == "direct" else "SELF_ONLY",
            "disable_comment": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": size,
            "total_chunk_count": 1,
        },
        "post_mode": "DIRECT_POST" if mode == "direct" else "MEDIA_UPLOAD",
        "media_type": "VIDEO",
    }
    return _api("/post/publish/video/init/", payload, token)


def upload_chunk(upload_url: str, data: bytes) -> int:
    req = urllib.request.Request(upload_url, data=data, method="PUT",
                                 headers={"Content-Type": "video/mp4",
                                          "Content-Range": f"bytes 0-{len(data) - 1}/{len(data)}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.status


def publish_status(token: str, publish_id: str) -> dict:
    return _api("/post/publish/status/fetch/", {"publish_id": publish_id}, token)


def publish(episode_id: str, script: dict, cfg: dict, mode: str | None = None,
            privacy: str = "SELF_ONLY") -> dict:
    mode = mode or cfg.get("publish", {}).get("mode", "manual")
    package = build_package(episode_id, script, cfg)

    if mode == "manual":
        db.init()
        db.save_episode(episode_id, "rendered", {}, script, {"publish_package": package["video"]})
        print(f"  📦 paket siap upload: {Path(package['video']).parent}")
        print(f"     lihat: {Path(package['video']).parent / 'SIAP_UPLOAD.md'}")
        return {"mode": "manual", "package": package, "published": False,
                "reason": "menunggu upload manual (jalur paling aman)"}

    token = cfg["tiktok"]["access_token"]
    if not token:
        print("  [warn] mode API dipilih tapi TIKTOK_ACCESS_TOKEN kosong → fallback manual")
        return publish(episode_id, script, cfg, mode="manual")

    info = creator_info(token)
    if "error" in info:
        print(f"  [warn] creator_info gagal: {info['error']} → fallback manual")
        return publish(episode_id, script, cfg, mode="manual")
    allowed = info.get("data", {}).get("privacy_level_options", [])
    if privacy not in allowed:
        privacy = allowed[0] if allowed else "SELF_ONLY"

    video = Path(package["video"])
    init = init_video_post(token, video, package["full_caption"], mode, privacy)
    if "error" in init:
        err = json.dumps(init["error"], ensure_ascii=False)
        hint = ""
        if "unaudited_client" in err:
            hint = ("\n  ⚠️ Client belum lulus audit TikTok → posting publik ditolak. "
                    "Pakai mode 'draft' atau 'manual' sampai audit lulus.")
        print(f"  [error] init gagal: {err}{hint}")
        return {"mode": mode, "published": False, "error": init["error"], "hint": hint}

    data = init.get("data", {})
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")
    if upload_url:
        upload_chunk(upload_url, video.read_bytes())

    db.init()
    db.save_episode(episode_id, "published" if mode == "direct" else "rendered", {},
                    script, {"publish_id": publish_id,
                             "publish_url": data.get("upload_url", "")})
    db.log_event(episode_id, "publish", {"mode": mode, "publish_id": publish_id})
    print(f"  ✔ {mode} terkirim (publish_id={publish_id})")
    return {"mode": mode, "publish_id": publish_id, "published": True, "package": package}


def check_status(episode_id: str, cfg: dict) -> dict:
    ep = db.get_episode(episode_id)
    if not ep:
        return {"error": "episode tidak ditemukan"}
    pid = ep["paths"].get("publish_id")
    if not pid:
        return {"error": "episode ini belum punya publish_id"}
    return publish_status(cfg["tiktok"]["access_token"], pid)
