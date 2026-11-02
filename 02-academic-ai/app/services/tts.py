"""Text-to-speech for video narration: offline Piper first, edge-tts fallback.

Both engines are optional binaries. Every failure is honest (install hint included).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

PIPER_INSTALL_HINT = "venv\\Scripts\\activate lalu pip install piper-tts"
EDGE_INSTALL_HINT = "venv\\Scripts\\activate lalu pip install edge-tts"
EDGE_VOICE_DEFAULT = "id-ID-ArdiNeural"


class TTSUnavailableError(ValueError):
    """Raised when no narration engine can speak."""


def available_engines() -> dict[str, str | None]:
    return {"piper": shutil.which("piper"), "edge": shutil.which("edge-tts")}


def pick_engine(preference: str) -> str:
    want = (preference or "auto").strip().lower()
    engines = available_engines()
    if want == "piper":
        if engines["piper"]:
            return "piper"
        raise TTSUnavailableError(f"Piper tidak ditemukan. Instal: {PIPER_INSTALL_HINT}.")
    if want == "edge":
        if engines["edge"]:
            return "edge"
        raise TTSUnavailableError(f"edge-tts tidak ditemukan. Instal: {EDGE_INSTALL_HINT}.")
    if engines["piper"]:
        return "piper"
    if engines["edge"]:
        return "edge"
    raise TTSUnavailableError(
        f"TTS tidak tersedia. Instal salah satu: {PIPER_INSTALL_HINT} ATAU {EDGE_INSTALL_HINT}."
    )


def voice_for_engine(engine: str, configured_voice: str) -> str:
    """Resolve the effective voice (edge needs an id-ID-* voice, not a piper model)."""
    voice = (configured_voice or "").strip()
    if engine == "edge" and ("_" in voice or not voice):
        return EDGE_VOICE_DEFAULT
    return voice or ("id_ID-fajri-medium" if engine == "piper" else EDGE_VOICE_DEFAULT)


def synthesize(
    text: str,
    output: Path,
    *,
    engine: str,
    voice: str,
    timeout_seconds: int = 300,
) -> Path:
    """Speak text to an audio file (format detected later by ffmpeg)."""
    clean = " ".join(text.split())
    if not clean:
        raise ValueError("Teks narasi kosong.")
    output.parent.mkdir(parents=True, exist_ok=True)
    binary = available_engines().get(engine)
    if not binary:
        raise TTSUnavailableError(f"Engine TTS '{engine}' tidak ditemukan.")
    if engine == "piper":
        command = [binary, "--model", voice, "--output_file", str(output)]
        stdin: bytes | None = clean.encode("utf-8")
    else:
        command = [
            binary,
            "--voice",
            voice,
            "--text",
            clean,
            "--write-media",
            str(output),
        ]
        stdin = None
    try:
        completed = subprocess.run(  # noqa: S603 - binary resolved via PATH, args fixed
            command, input=stdin, capture_output=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise TTSUnavailableError(f"TTS {engine} kehabisan waktu ({timeout_seconds}s).") from exc
    if completed.returncode != 0 or not output.is_file():
        detail = (completed.stderr or b"").decode("utf-8", "replace")[-300:]
        raise TTSUnavailableError(f"TTS {engine} gagal. {detail}".strip())
    logger.info("[INFO] Narasi TTS selesai (%s, %d karakter).", engine, len(clean))
    return output
