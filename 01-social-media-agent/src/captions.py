"""Caption sinkron per kata — gratis, tanpa whisper.

edge-tts dengan `boundary="WordBoundary"` mengirim timestamp per kata
(offset & duration dalam satuan 100-nanosecond). Dari situ kita bangun file ASS
yang di-burn oleh libass di ffmpeg.

Gaya caption: 2-4 kata per grup, muncul persis saat diucapkan, kata aktif
di-highlight. Ini format yang paling terbukti menahan retensi di short-form.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

TICKS = 10_000_000  # 100ns per detik

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Plus Jakarta Sans,58,&H002B3020,&H002B3020,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,2,95,95,350,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


@dataclass
class Word:
    text: str
    start: float
    end: float


def _ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


async def _words_async(text: str, voice: str, rate: str) -> list[Word]:
    import edge_tts

    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words: list[Word] = []
    async for ch in comm.stream():
        if ch.get("type") != "WordBoundary":
            continue
        start = ch["offset"] / TICKS
        dur = max(0.08, ch["duration"] / TICKS)
        token = (ch.get("text") or "").strip()
        if token:
            words.append(Word(token, start, start + dur))
    return words


def word_timings(text: str, voice: str, rate: str = "+0%") -> list[Word]:
    try:
        return asyncio.run(_words_async(text, voice, rate))
    except Exception as e:
        print(f"  [warn] word boundary gagal: {e}")
        return []


def group_lines(words: list[Word], max_words: int = 3, max_chars: int = 24) -> list[list[Word]]:
    """Kelompokkan kata jadi potongan pendek biar kebaca di layar HP."""
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        trial = cur + [w]
        if (len(trial) > max_words
                or sum(len(x.text) + 1 for x in trial) > max_chars
                or (cur and re.search(r"[.!?,]$", cur[-1].text))):
            groups.append(cur)
            cur = [w]
        else:
            cur = trial
    if cur:
        groups.append(cur)
    return groups


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
            .replace("\n", " "))


def build_ass(scenes: list[list[list[Word]]], path: Path,
              highlight: str = "&H005CE2FF", style: str = "box") -> Path:
    """`scenes` = [scene][grup][Word]. Offset sudah digeser ke timeline global."""
    lines = [ASS_HEADER]
    groups = [g for scene in scenes for g in scene]
    for group in groups:
        if not group:
            continue
        text = " ".join(_escape(w.text) for w in group)
        start, end = group[0].start, min(group[-1].end + .08, group[0].start + 4.5)
        if end <= start:
            continue
        if style == "word":
            # Explicit opt-in for the legacy karaoke renderer.
            for active in range(len(group)):
                a = group[active].start
                b = group[active].end if active < len(group)-1 else group[active].end+.06
                parts = [(f"{{{{\\c{highlight}}}}}{_escape(w.text)}{{{{\\c&H002B3020&}}}}" if i == active else _escape(w.text))
                         for i,w in enumerate(group)]
                lines.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{' '.join(parts)}")
        else:
            # One stable white box per phrase; no flashing word-by-word highlight.
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def captions_for_scenes(scene_words: list[list[Word]], durations: list[float],
                        path: Path, max_words: int = 6, style: str = "box") -> Path:
    """Gabungkan semua scene jadi satu file ASS dengan offset global."""
    offset = 0.0
    per_scene = []
    for words, dur in zip(scene_words, durations):
        shifted = [Word(w.text, w.start + offset, min(w.end + offset, offset + dur))
                   for w in words]
        per_scene.append(group_lines(shifted, max_words=max_words, max_chars=42))
        offset += dur
    return build_ass(per_scene, path, style=style)
