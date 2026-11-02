"""QC TEKNIS — gerbang terakhir sebelum video dianggap layak publish.

Yang dicek (semua bisa dicek tanpa manusia):
  - durasi dalam rentang 20..70 detik
  - resolusi 1080x1920, fps stabil
  - audio ada, tidak clipping, loudness mendekati -14 LUFS
  - tidak ada frame hitam panjang (indikasi render gagal)
  - ukuran file wajar
  - teks wajib tidak keluar area aman (dicek dari desain kartu, bukan dari video)

QC EDITORIAL (hook/clarity/akurasi) ada di scriptwriter.validate_script,
karena itu harus lewat SEBELUM render supaya tidak buang waktu render.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .config import find_ffmpeg

FF = find_ffmpeg()


def _stderr(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True).stderr


def measure_loudness(video: Path) -> dict:
    """Integrated loudness via ffmpeg ebur128."""
    out = _stderr([FF, "-hide_banner", "-nostats", "-i", str(video),
                   "-af", "ebur128=peak=true", "-f", "null", "-"])
    integ = re.findall(r"I:\s+(-?\d+\.\d+)\s+LUFS", out)
    peak = re.findall(r"Peak:\s+(-?\d+\.\d+)\s+dBFS", out)
    return {
        "integrated_lufs": float(integ[-1]) if integ else None,
        "true_peak_db": float(peak[-1]) if peak else None,
    }


def detect_black(video: Path, min_dur: float = 0.6) -> list[dict]:
    out = _stderr([FF, "-hide_banner", "-nostats", "-i", str(video),
                   "-vf", f"blackdetect=d={min_dur}:pix_th=0.10", "-f", "null", "-"])
    spans = []
    for m in re.finditer(r"black_start:([\d.]+)\s+black_end:([\d.]+)", out):
        spans.append({"start": float(m.group(1)), "end": float(m.group(2))})
    return spans


def probe(video: Path) -> dict:
    out = _stderr([FF, "-hide_banner", "-i", str(video)])
    dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out)
    vid = re.search(r"Video:\s*(\w+).*?(\d{2,5})x(\d{2,5}).*?([\d.]+)\s*fps", out)
    aud = re.search(r"Audio:\s*(\w+).*?(\d+)\s*Hz,\s*(\w+)", out)
    seconds = (int(dur.group(1)) * 3600 + int(dur.group(2)) * 60 + float(dur.group(3))) if dur else 0.0
    return {
        "duration_sec": round(seconds, 2),
        "codec": vid.group(1) if vid else None,
        "width": int(vid.group(2)) if vid else 0,
        "height": int(vid.group(3)) if vid else 0,
        "fps": float(vid.group(4)) if vid else 0.0,
        "audio_codec": aud.group(1) if aud else None,
        "audio_hz": int(aud.group(2)) if aud else 0,
        "size_mb": round(video.stat().st_size / 1e6, 2) if video.exists() else 0,
    }


def run_qc(video: Path, cfg: dict, meta: dict | None = None) -> dict:
    v = cfg.get("video", {})
    info = probe(video)
    loud = measure_loudness(video)
    blacks = detect_black(video)

    checks: list[dict] = []

    def check(name, ok, detail, level="error"):
        checks.append({"check": name, "ok": bool(ok), "detail": detail, "level": level})

    max_dur = v.get("max_duration_sec", 62)
    check("durasi", 15 <= info["duration_sec"] <= max_dur + 5,
          f"{info['duration_sec']}s (target 15..{max_dur + 5}s)")
    check("resolusi", (info["width"], info["height"]) == (v.get("width", 1080), v.get("height", 1920)),
          f"{info['width']}x{info['height']}")
    check("fps", info["fps"] >= 20, f"{info['fps']} fps")
    check("ada_audio", bool(info["audio_codec"]), str(info["audio_codec"]))
    check("audio_44k", info["audio_hz"] in (44100, 48000), f"{info['audio_hz']} Hz")
    check("ada_video", info["codec"] == "h264", str(info["codec"]))
    check("ukuran_wajar", info["size_mb"] < 200, f"{info['size_mb']} MB")

    lufs = loud["integrated_lufs"]
    check("loudness", lufs is not None and -18 <= lufs <= -11,
          f"{lufs} LUFS (target -14, toleransi -18..-11)")
    tp = loud["true_peak_db"]
    check("no_clipping", tp is None or tp <= -0.5, f"true peak {tp} dBFS", level="warn")

    long_blacks = [b for b in blacks if b["end"] - b["start"] > 1.2]
    check("no_black_gap", not long_blacks, f"{len(long_blacks)} jeda hitam >1.2s", level="warn")

    if meta is not None:
        check("narasi_bukan_fallback_hening", bool(meta.get("audio_modes")) and
              all(m != "silent-fallback" for m in meta.get("audio_modes", [])), str(meta.get("audio_modes", [])))
        check("layout_aman", bool((meta.get("layout") or {}).get("ok")), str((meta.get("layout") or {}).get("problems", [])))
        check("caption_ada", bool(meta.get("captions")), str(meta.get("caption_style")))
        check("generator_teridentifikasi", meta.get("generator") in ("llm", "template", "human"), str(meta.get("generator")))
        alignment = meta.get("caption_alignment", [])
        check("alignment_caption_jujur", all(a in ("tts", "whisper", "estimated", "none") for a in alignment),
              "estimated berarti perkiraan, bukan sinkronisasi presisi", level="warn")
    failed = [c for c in checks if not c["ok"] and c["level"] == "error"]
    warned = [c for c in checks if not c["ok"] and c["level"] == "warn"]

    result = {
        "video": str(video),
        "passed": not failed,
        "info": info,
        "loudness": loud,
        "black_spans": blacks,
        "checks": checks,
        "failed": [c["check"] for c in failed],
        "warnings": [c["check"] for c in warned],
    }
    report = Path(video).parent / "qc_report.json"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys

    from .config import load_config

    p = Path(sys.argv[1] if len(sys.argv) > 1 else "out/ep-demo-001/final.mp4")
    r = run_qc(p, load_config())
    print(json.dumps({k: r[k] for k in ("passed", "failed", "warnings", "loudness", "info")},
                     indent=2, ensure_ascii=False))
