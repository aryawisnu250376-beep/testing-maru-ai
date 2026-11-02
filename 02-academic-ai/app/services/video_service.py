"""OpenMontage-style explainer video pipeline (local, Rp 0, no AGPL code).

Stages: preflight -> research -> script -> narration -> slides -> render -> review.
Research reuses grounded summaries; the script split is heuristic (no extra LLM).
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import uuid
import wave
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.services import tts as tts_engine

logger = logging.getLogger(__name__)

SLIDE_WIDTH = 1280
SLIDE_HEIGHT = 720
FFMPEG_INSTALL_HINT = "winget install --id Gyan.FFmpeg"
BG_TOP = (18, 28, 48)
BG_BOTTOM = (38, 68, 108)
ACCENT = (80, 203, 211)
TEXT_MAIN = (235, 240, 250)
TEXT_DIM = (160, 178, 200)


@dataclass
class Scene:
    title: str
    narration: str
    bullets: list[str]


def ffmpeg_binary() -> str | None:
    return shutil.which("ffmpeg")


def ffmpeg_version(binary: str) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 - binary resolved via PATH, args fixed
            [binary, "-version"], capture_output=True, timeout=15, check=False
        )
        first = (completed.stdout or b"").decode("utf-8", "replace").splitlines()
        return first[0][:120] if first else binary
    except Exception:
        return binary


def preflight(settings) -> dict[str, str]:
    """Check the render chain first (fail fast, before any LLM cost)."""
    ffmpeg = ffmpeg_binary()
    if not ffmpeg:
        raise ValueError(f"ffmpeg tidak ditemukan. Instal: {FFMPEG_INSTALL_HINT}.")
    engine = tts_engine.pick_engine(getattr(settings, "tts_provider", "auto"))
    return {"ffmpeg": ffmpeg, "tts_engine": engine}


def split_script(answer: str, max_scenes: int) -> list[Scene]:
    """Split a summary into scenes. Deterministic, no LLM."""
    paragraphs = [part.strip() for part in answer.split("\n") if part.strip()]
    if not paragraphs:
        raise ValueError("Tidak ada teks rangkuman untuk dijadikan video.")
    limit = max(1, max_scenes)
    bundle = max(1, -(-len(paragraphs) // limit))
    scenes: list[Scene] = []
    groups = [paragraphs[i : i + bundle] for i in range(0, len(paragraphs), bundle)]
    for group in groups[:limit]:
        text = " ".join(group)
        head = group[0]
        title = (head[:57] + "...") if len(head) > 60 else head
        scenes.append(Scene(title=title, narration=text[:900], bullets=group[:4]))
    return scenes


def _load_font(size: int, bold: bool = False):
    names = ["DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_slide(
    scene: Scene, index: int, total: int, subject_code: str, topic: str, path: Path
) -> Path:
    image = Image.new("RGB", (SLIDE_WIDTH, SLIDE_HEIGHT), BG_TOP)
    pixels = image.load()
    for y in range(SLIDE_HEIGHT):
        mix = y / SLIDE_HEIGHT
        pixels_color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * mix) for i in range(3))
        for x in range(SLIDE_WIDTH):
            pixels[x, y] = pixels_color
    draw = ImageDraw.Draw(image)
    chip_font, title_font, body_font, foot_font = (
        _load_font(30, bold=True),
        _load_font(56, bold=True),
        _load_font(34),
        _load_font(26),
    )
    draw.text(
        (70, 46),
        f"{subject_code} - {topic[:60]}" if topic else subject_code,
        font=chip_font,
        fill=ACCENT,
    )
    draw.line([(70, 96), (SLIDE_WIDTH - 70, 96)], fill=ACCENT, width=3)
    y = 130
    for line in _wrap(draw, scene.title, title_font, SLIDE_WIDTH - 160)[:3]:
        draw.text((80, y), line, font=title_font, fill=TEXT_MAIN)
        y += 72
    y += 10
    for bullet in scene.bullets[:4]:
        for line in _wrap(draw, "- " + bullet, body_font, SLIDE_WIDTH - 180)[:2]:
            draw.text((100, y), line, font=body_font, fill=TEXT_DIM)
            y += 48
        y += 6
        if y > SLIDE_HEIGHT - 120:
            break
    draw.text(
        (70, SLIDE_HEIGHT - 60),
        f"Academic AI - Adegan {index + 1}/{total}",
        font=foot_font,
        fill=TEXT_DIM,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate() or 1
        return max(0.5, handle.getnframes() / float(rate))


def _srt_time(seconds: float) -> str:
    total_ms = int(seconds * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt(scenes: list[Scene], durations: list[float], path: Path) -> Path:
    cursor, blocks = 0.0, []
    for number, (scene, duration) in enumerate(zip(scenes, durations, strict=True), start=1):
        blocks.append(
            f"{number}\n{_srt_time(cursor)} --> {_srt_time(cursor + duration)}\n"
            f"{scene.title}\n{scene.narration[:200]}"
        )
        cursor += duration
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path


def normalize_audio(ffmpeg: str, source: Path, dest: Path) -> Path:
    completed = subprocess.run(  # noqa: S603 - binary resolved via PATH, args fixed
        [ffmpeg, "-y", "-i", str(source), "-ar", "16000", "-ac", "1", str(dest)],
        capture_output=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0 or not dest.is_file():
        detail = (completed.stderr or b"").decode("utf-8", "replace")[-300:]
        raise ValueError(f"Konversi audio gagal. {detail}".strip())
    return dest


def assemble_video(
    ffmpeg: str,
    slides: list[Path],
    wavs: list[Path],
    durations: list[float],
    subtitles: Path,
    output: Path,
) -> Path:
    count = len(slides)
    inputs: list[str] = []
    for slide, duration in zip(slides, durations, strict=True):
        inputs += ["-loop", "1", "-framerate", "2", "-t", f"{duration:.2f}", "-i", str(slide)]
    concat_list = output.parent / "audio.txt"
    concat_list.write_text("".join(f"file '{wav.as_posix()}'\n" for wav in wavs), encoding="utf-8")
    video_chain = "".join(f"[{i}]" for i in range(count)) + f"concat=n={count}:v=1:a=0[v]"
    command = [
        ffmpeg,
        "-y",
        *inputs,
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-i",
        str(subtitles),
        "-filter_complex",
        video_chain,
        "-map",
        "[v]",
        "-map",
        f"{count}:a",
        "-map",
        f"{count + 1}:s?",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-c:s",
        "mov_text",
        "-shortest",
        str(output),
    ]
    try:
        completed = subprocess.run(  # noqa: S603 - binary resolved via PATH, args fixed
            command, capture_output=True, timeout=900, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Render ffmpeg kehabisan waktu (15 menit).") from exc
    if completed.returncode != 0 or not output.is_file():
        detail = (completed.stderr or b"").decode("utf-8", "replace")[-400:]
        raise ValueError(f"Render video gagal. {detail}".strip())
    return output


class VideoService:
    def __init__(self, settings, academic_manager, database) -> None:
        self.settings = settings
        self.manager = academic_manager
        self.database = database

    async def build_video(
        self,
        *,
        subject_code: str,
        topic: str,
        question_message_id: int | None = None,
        progress: Callable[[str, str], None] | None = None,
    ) -> dict[str, Any]:
        def report(stage: str, detail: str = "") -> None:
            if progress is not None:
                progress(stage, detail)

        report("preflight", "cek ffmpeg + TTS")
        checks = await asyncio.to_thread(preflight, self.settings)
        engine = checks["tts_engine"]
        voice = tts_engine.voice_for_engine(engine, getattr(self.settings, "tts_voice", ""))

        report("research", topic)
        summary = await self.manager.summarize(
            subject_code, question_message_id=question_message_id, topic=topic
        )
        answer = (summary.answer or "").strip()
        if not answer:
            raise ValueError("Rangkuman kosong; video tidak dibuat.")

        report("script", "pecah adegan")
        scenes = await asyncio.to_thread(split_script, answer, self.settings.video_max_scenes)
        video_id = uuid.uuid4().hex[:12]
        workdir = Path(self.settings.videos_dir) / video_id
        workdir.mkdir(parents=True, exist_ok=True)
        title = f"{subject_code}: {topic}".strip()
        await self.database.create_video(
            video_id=video_id, subject_code=subject_code, topic=topic, title=title
        )
        try:
            report("narration", f"{len(scenes)} adegan ({engine})")
            wavs = await asyncio.to_thread(
                self._narrate_all, scenes, workdir, engine, voice, checks["ffmpeg"]
            )
            durations = [wav_duration(wav) for wav in wavs]
            report("slides", f"{len(scenes)} slide")
            slides = await asyncio.to_thread(self._slides_all, scenes, workdir, subject_code, topic)
            subtitles = await asyncio.to_thread(build_srt, scenes, durations, workdir / "subs.srt")
            report("render", "ffmpeg")
            output = await asyncio.to_thread(
                assemble_video,
                checks["ffmpeg"],
                slides,
                wavs,
                durations,
                subtitles,
                workdir / f"{video_id}.mp4",
            )
        except Exception as exc:
            await self.database.update_video_status(video_id, "failed", error=str(exc))
            raise
        total = round(sum(durations), 1)
        decision_log = {
            "tts_engine": engine,
            "voice": voice,
            "ffmpeg": ffmpeg_version(checks["ffmpeg"]),
            "scenes": len(scenes),
            "duration_sec": total,
            "rendered_at": datetime.now(UTC).isoformat(),
        }
        await self.database.update_video_status(
            video_id,
            "done",
            file_path=str(output),
            duration_sec=total,
            scene_count=len(scenes),
            decision_log=json.dumps(decision_log),
        )
        logger.info("[INFO] Video %s selesai (%s adegan, %ss).", video_id, len(scenes), total)
        return {
            "video_id": video_id,
            "title": title,
            "subject_code": subject_code,
            "topic": topic,
            "duration_sec": total,
            "scene_count": len(scenes),
            "download_url": f"/api/videos/{video_id}/download",
            "file_path": str(output),
            "decision_log": decision_log,
        }

    def _narrate_all(
        self, scenes: list[Scene], workdir: Path, engine: str, voice: str, ffmpeg: str
    ) -> list[Path]:
        wavs: list[Path] = []
        for index, scene in enumerate(scenes):
            raw = tts_engine.synthesize(
                scene.narration,
                workdir / f"scene{index}.media",
                engine=engine,
                voice=voice,
            )
            wavs.append(normalize_audio(ffmpeg, raw, workdir / f"scene{index}.wav"))
        return wavs

    def _slides_all(
        self, scenes: list[Scene], workdir: Path, subject_code: str, topic: str
    ) -> list[Path]:
        return [
            render_slide(
                scene, index, len(scenes), subject_code, topic, workdir / f"slide{index}.png"
            )
            for index, scene in enumerate(scenes)
        ]
