"""Narration: Edge TTS, or the user's own per-beat recording. No voice cloning.

A failed TTS request is an error by default, never an unnoticed silent video.
Recordings must be consented to and are decoded/validated by ffmpeg.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .captions import Word
from .config import find_ffmpeg

MAX_RECORDING_BYTES = 8 * 1024 * 1024


@dataclass
class Narration:
    path: Path
    duration: float
    words: list[Word]
    mode: str
    alignment: str = "tts"


def duration(path: Path) -> float:
    ff = find_ffmpeg()
    r = subprocess.run([ff, "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=30)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if not m:
        raise RuntimeError("Audio tidak dapat dibaca ffmpeg")
    return int(m[1])*3600+int(m[2])*60+float(m[3])


def estimated_words(text: str, seconds: float) -> list[Word]:
    tokens = text.split()
    if not tokens:
        return []
    weights = [max(2,len(t)) for t in tokens]
    total = sum(weights)
    cursor = 0.0
    out = []
    for token, weight in zip(tokens, weights):
        length = max(.08,seconds*weight/total)
        out.append(Word(token,cursor,min(seconds,cursor+length)))
        cursor += length
    return out


async def _edge(text: str, voice: str, rate: str, target: Path) -> list[Word]:
    import edge_tts
    words = []
    with target.open("wb") as f:
        stream = edge_tts.Communicate(text,voice,rate=rate,boundary="WordBoundary")
        async for chunk in stream.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"]/10_000_000
                end = start+max(.08,chunk["duration"]/10_000_000)
                words.append(Word(chunk["text"],start,end))
    return words


def synth(text: str, target: Path, voice: str = "id-ID-ArdiNeural", rate: str = "+8%",
          retries: int = 3) -> Narration:
    """Synthesize once: audio and word boundaries come from the SAME request."""
    target.parent.mkdir(parents=True,exist_ok=True)
    error = None
    for attempt in range(max(1,retries)):
        tmp = target.with_suffix(".partial.mp3")
        try:
            words = asyncio.run(asyncio.wait_for(_edge(text,voice,rate,tmp),timeout=60))
            if tmp.stat().st_size < 512:
                raise RuntimeError("Audio TTS kosong")
            tmp.replace(target)
            return Narration(target,duration(target),words,"edge-tts")
        except Exception as exc:
            error = exc
            tmp.unlink(missing_ok=True)
            if attempt+1 < retries:
                time.sleep(min(8,2**attempt))
    raise RuntimeError(f"Dubbing gagal setelah {retries} percobaan: {str(error)[:150]}")


def to_wav(source: Path, target: Path, pad: float = .3) -> float:
    r = subprocess.run([find_ffmpeg(),"-y","-hide_banner","-loglevel","error","-i",str(source),
                        "-af",f"apad=pad_dur={max(0,min(2,pad))}","-ar","44100","-ac","1",str(target)],
                       capture_output=True,text=True,timeout=90)
    if r.returncode:
        raise RuntimeError("Konversi audio gagal: "+r.stderr[-180:])
    return duration(target)


def import_recording(data_base64: str, target: Path, consent: bool) -> dict:
    if consent is not True:
        raise ValueError("Konfirmasi bahwa rekaman adalah suara Anda atau Anda punya izin.")
    try:
        data = base64.b64decode(data_base64,validate=True)
    except Exception as exc:
        raise ValueError("Data audio base64 tidak valid") from exc
    if not 128 <= len(data) <= MAX_RECORDING_BYTES:
        raise ValueError("Audio harus berukuran 128 byte sampai 8 MB per beat")
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        raw = Path(tmp)/"input.audio"
        raw.write_bytes(data)
        wav = Path(tmp)/"validated.wav"
        r = subprocess.run([find_ffmpeg(),"-y","-hide_banner","-loglevel","error","-i",str(raw),
                            "-t","90","-ar","44100","-ac","1",str(wav)],capture_output=True,text=True,timeout=60)
        if r.returncode or not wav.exists():
            raise ValueError("Format audio tidak didukung. Coba WAV, MP3, M4A, OGG, atau WebM.")
        seconds = duration(wav)
        if not .3 <= seconds <= 45:
            raise ValueError("Rekaman per beat harus 0,3–45 detik")
        wav.replace(target)
    return {"path":str(target),"sha256":hashlib.sha256(data).hexdigest(),"duration_sec":round(seconds,2),
            "consent":True}


def align_recording(path: Path, text: str, seconds: float, engine: str = "estimated") -> tuple[list[Word],str]:
    """Optional local Whisper alignment. Never label estimates as precise."""
    if engine != "whisper":
        return estimated_words(text,max(.1,seconds-.3)), "estimated"
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny",device="cpu",compute_type="int8")
        segments,_ = model.transcribe(str(path),language="id",word_timestamps=True)
        words = [Word(w.word.strip(),w.start,w.end) for seg in segments for w in (seg.words or [])]
        if words:
            return words,"whisper"
    except Exception as exc:
        print(f"[voice] Whisper tidak tersedia: {str(exc)[:100]}; caption estimasi")
    return estimated_words(text,max(.1,seconds-.3)), "estimated"
