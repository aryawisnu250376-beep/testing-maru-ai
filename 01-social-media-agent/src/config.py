"""Loader config + path helper. Tidak ada dependency ke modul lain."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _read_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(path: str | Path | None = None) -> dict:
    cfg = _read_yaml(Path(path) if path else ROOT / "config" / "config.yaml")
    cfg["_root"] = str(ROOT)

    llm = cfg.setdefault("llm", {})
    for key, env in (
        ("base_url", "LLM_BASE_URL"),
        ("api_key", "LLM_API_KEY"),
        ("model", "LLM_MODEL"),
        ("model_cheap", "LLM_MODEL_CHEAP"),
        ("model_strong", "LLM_MODEL_STRONG"),
        ("model_qc", "LLM_MODEL_QC"),
    ):
        if os.getenv(env):
            llm[key] = os.getenv(env)

    auto = cfg.setdefault("autonomy", {})
    if os.getenv("AUTONOMY_ENABLED"):
        auto["enabled"] = os.getenv("AUTONOMY_ENABLED", "true").lower() in ("1", "true", "yes")
    cfg.setdefault("publish", {})
    if os.getenv("PUBLISH_MODE"):
        cfg["publish"]["mode"] = os.getenv("PUBLISH_MODE")

    cfg["telegram"] = {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    }
    cfg["tiktok"] = {
        "client_key": os.getenv("TIKTOK_CLIENT_KEY", ""),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET", ""),
        "access_token": os.getenv("TIKTOK_ACCESS_TOKEN", ""),
    }
    return cfg


def path(*parts: str) -> Path:
    p = ROOT.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def out_dir(episode_id: str) -> Path:
    d = ROOT / "out" / episode_id
    d.mkdir(parents=True, exist_ok=True)
    return d


_FF_CACHE: dict[str, str] = {}


def _has_subtitles_filter(binary: str) -> bool:
    import subprocess

    try:
        out = subprocess.run([binary, "-hide_banner", "-filters"],
                             capture_output=True, text=True, timeout=20).stdout
        return " subtitles " in out or " ass " in out
    except Exception:
        return False


def find_ffmpeg() -> str:
    """Pilih ffmpeg terbaik yang tersedia.

    Prioritas: FFMPEG_BINARY (eksplisit) -> ffmpeg sistem yang punya filter
    `subtitles` (perlu untuk caption burn-in) -> imageio-ffmpeg portable ->
    "ffmpeg" dari PATH.

    Ini penting: binary imageio tidak membawa libass, jadi caption tidak akan
    terbakar kalau selalu memakai dia.
    """
    if "bin" in _FF_CACHE:
        return _FF_CACHE["bin"]

    import os
    import shutil

    candidates: list[str] = []
    if os.getenv("FFMPEG_BINARY"):
        candidates.append(os.environ["FFMPEG_BINARY"])
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        candidates.append(sys_ff)
    try:
        import imageio_ffmpeg

        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    candidates.append("ffmpeg")

    chosen = candidates[-1]
    for c in candidates:
        if c != "ffmpeg" and os.path.exists(c) and _has_subtitles_filter(c):
            chosen = c
            break
    else:
        if sys_ff:
            chosen = sys_ff
    _FF_CACHE["bin"] = chosen
    return chosen
