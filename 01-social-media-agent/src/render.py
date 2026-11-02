"""RENDER v2 — script JSON -> MP4 vertikal 1080x1920.

Alur per episode:
  1. TTS per beat (edge-tts) + ambil timestamp per kata
  2. Ukur durasi tiap scene
  3. Stream frame animasi per scene ke ffmpeg (src/anim.py + src/visuals.py)
  4. Bangun caption ASS dengan timing per kata, burn ke video (libass)
  5. Gabung audio, loudnorm -14 LUFS
  6. Cek layout: tidak ada teks yang keluar area aman TikTok

Fallback berlapis:
  - TTS gagal -> durasi estimasi + audio senyap (video tetap jadi)
  - libass tidak ada -> caption dilewati (log jelas, bukan crash)
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path


from . import audio as audio_mod
from . import captions as cap
from . import voice as narration
from .anim import frames_to_video
from .config import find_ffmpeg, load_config, out_dir
from .manim_scene import render_manim_clip
from .visuals import (BOTTOM_SAFE, Ctx, TOP_SAFE, manim_spec, overlay_chrome_on_clip,
                      render_frame, suggested_duration, wants_manim)

FF = find_ffmpeg()
W, H = 1080, 1920


# ---------------------------------------------------------------- audio

def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def probe_duration(path: str | Path) -> float:
    r = _run([FF, "-hide_banner", "-i", str(path)])
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if not m:
        raise RuntimeError(f"tidak bisa baca durasi {path}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


async def _tts(text: str, voice: str, rate: str, out: Path) -> bool:
    try:
        import edge_tts

        await edge_tts.Communicate(text, voice, rate=rate).save(str(out))
        return out.exists() and out.stat().st_size > 1000
    except Exception as e:
        print(f"       [warn] TTS: {e}")
        return False


def synthesize(text: str, voice: str, rate: str, mp3: Path, retries: int = 3) -> bool:
    for _ in range(retries):
        if asyncio.run(_tts(text, voice, rate, mp3)):
            return True
    return False


def to_wav(mp3: Path, wav: Path, pad: float = 0.0) -> float:
    args = [FF, "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp3),
            "-ar", "44100", "-ac", "1"]
    if pad > 0:
        args += ["-af", f"apad=pad_dur={pad}"]
    args += [str(wav)]
    if _run(args).returncode != 0:
        raise RuntimeError("konversi wav gagal")
    return probe_duration(wav)


def silent_wav(duration: float, wav: Path) -> float:
    _run([FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
          "-i", "anullsrc=r=44100:cl=mono", "-t", f"{duration:.2f}", str(wav)])
    return duration


def concat(parts: list[Path], out: Path, workdir: Path, reencode_audio: bool = False) -> None:
    lst = workdir / f"list_{out.stem}.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    args = [FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(lst)]
    args += (["-ar", "44100", "-ac", "1"] if reencode_audio else ["-c", "copy"])
    args += [str(out)]
    result = _run(args)
    if result.returncode != 0:
        raise RuntimeError(f"concat gagal {out.stem}: {result.stderr[-200:]}")


# ---------------------------------------------------------------- layout QC

def check_layout(ctxs: list[Ctx]) -> dict:
    """Pastikan tidak ada blok teks yang masuk area UI TikTok atau keluar layar."""
    problems, checked = [], 0
    for ctx in ctxs:
        for (x0, y0, x1, y1) in ctx.bboxes:
            checked += 1
            if y0 < TOP_SAFE - 6:
                problems.append({"scene": ctx.idx, "issue": "masuk area atas TikTok",
                                 "y0": y0, "limit": TOP_SAFE})
            if y1 > BOTTOM_SAFE + 6:
                problems.append({"scene": ctx.idx, "issue": "masuk area bawah TikTok",
                                 "y1": y1, "limit": BOTTOM_SAFE})
            if x0 < 0 or x1 > W:
                problems.append({"scene": ctx.idx, "issue": "keluar tepi layar",
                                 "x0": x0, "x1": x1})
    return {"ok": not problems, "checked": checked, "problems": problems[:12]}


# ---------------------------------------------------------------- mux

def mux(video: Path, audio: Path, out: Path, subtitles: Path | None = None,
        loudnorm: bool = True) -> None:
    af = "loudnorm=I=-14:TP=-1.5:LRA=11" if loudnorm else "anull"
    base = [FF, "-y", "-hide_banner", "-loglevel", "error", "-threads", "1", "-filter_threads", "1", "-filter_complex_threads", "1", "-i", str(video), "-i", str(audio)]

    if subtitles and not subtitles.exists():
        raise RuntimeError("Caption diminta tetapi berkas ASS tidak tersedia")
    if subtitles and subtitles.exists():
        # burn caption via libass
        esc = str(subtitles).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        vf = f"subtitles='{esc}':fontsdir=assets/fonts"
        cmd = base + ["-vf", vf, "-c:v", "libx264", "-threads", "1", "-preset", "ultrafast", "-x264-params", "sliced-threads=1:lookahead_threads=1:rc-lookahead=5:sync-lookahead=0", "-crf", "29",
                      "-af", af, "-ar", "44100", "-ac", "1", "-c:a", "aac", "-b:a", "160k",
                      "-movflags", "+faststart", "-shortest", str(out)]
        r = _run(cmd)
        if r.returncode == 0:
            return
        raise RuntimeError("Caption burn-in gagal: " + r.stderr[-300:])

    cmd = base + ["-c:v", "copy", "-af", af, "-ar", "44100", "-ac", "1",
                  "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", str(out)]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError("mux audio gagal: " + result.stderr[-300:])


# ---------------------------------------------------------------- cover

def render_cover(script: dict, cfg: dict, path: Path) -> Path:
    beats = script.get("beats", [])
    first = beats[0] if beats else {"kind": "hook", "headline": script.get("title", "")}
    ctx = Ctx(beat={**first, "visual": {"type": "card"}}, idx=0, total=max(1, len(beats)),
              cfg=cfg, sources=_domains(script))
    img = render_frame(ctx, 4.0, (W, H))
    img.save(path, "PNG")
    return path


def _domains(script: dict) -> list[str]:
    out = []
    for s in script.get("sources", []):
        m = re.match(r"https?://(?:www\.)?([^/]+)", s.get("url", "") or "")
        if not m:
            continue
        d = m.group(1)
        d = {"news.ycombinator.com": "hackernews", "trends.google.com": "google trends"}.get(d, d)
        if d not in out:
            out.append(d)
    return out


# ---------------------------------------------------------------- episode

def _emit(on_step, phase: str, frac: float, detail: str) -> None:
    """Lapor progres ke pemanggil (orkestrator) tanpa pernah menggagalkan render."""
    if not on_step:
        return
    try:
        on_step(phase, max(0.0, min(1.0, frac)), detail)
    except Exception:
        pass


def render_episode(script: dict, cfg: dict | None = None, episode_id: str = "demo",
                   voice: str | None = None, burn_captions: bool = True,
                   on_step=None) -> dict:
    """Render penuh satu episode.

    `on_step(phase, frac, detail)` opsional: dipanggil saat masuk fase baru
    (`dubbing` = sintesis suara/musik, `animasi` = bangun frame & mux). Dipakai
    orkestrator untuk mengatribusikan pekerjaan ke agent yang benar di dashboard.
    """
    cfg = cfg or load_config()
    from .approve import require_approval
    require_approval(episode_id, script)
    from .scriptwriter import validate_script
    valid, errors, _ = validate_script(script, cfg)
    if not valid:
        raise ValueError("Naskah tidak valid: " + "; ".join(errors))
    v = cfg.get("video", {})
    voice = voice or v.get("voice", "id-ID-ArdiNeural")
    rate = v.get("rate", "+12%")
    pad = float(v.get("tail_padding_sec", 0.35))
    fps = int(v.get("fps", 24))
    crf = int(v.get("crf", 23))

    d = out_dir(episode_id)
    work = d / "work"
    work.mkdir(exist_ok=True)

    beats = script.get("beats", [])
    n = len(beats)
    domains = _domains(script)
    ctxs = [Ctx(beat=b, idx=i, total=n, cfg=cfg, sources=domains) for i, b in enumerate(beats)]

    # 1. audio + timing
    scene_words: list[list[cap.Word]] = []
    audio_mode: list[str] = []          # edge-tts | silent-fallback, per beat
    durations: list[float] = []
    audio_parts: list[Path] = []
    timeline: list[dict] = []

    alignments = []
    recordings = script.get("recordings") or {}
    profile = v.get("beat_voice") or {}
    for i, b in enumerate(beats):
        text = b.get("narration") or b.get("body") or ""
        wav = work / f"voice_{i:02d}.wav"
        rec = recordings.get(str(i))
        pause = float(profile.get(b.get("story_stage"), {}).get("pause_sec", pad))
        if rec:
            source = Path(rec["path"])
            if not source.is_file():
                raise RuntimeError(f"Rekaman beat {i+1} tidak ditemukan")
            import hashlib
            if hashlib.sha256(source.read_bytes()).hexdigest() != rec.get("file_sha256"):
                raise RuntimeError(f"Rekaman beat {i+1} berubah; unggah ulang dan ACC ulang")
            dur = narration.to_wav(source, wav, pause)
            words, alignment = narration.align_recording(source,text,dur,v.get("recording_alignment","estimated"))
            mode = "user-recording"
        else:
            rate_delta = float(profile.get(b.get("story_stage"), {}).get("rate_delta", 0))
            base_rate = float(str(rate).replace("%", "").replace("+", ""))
            beat_rate = f"{max(-30,min(30,base_rate+rate_delta)):+.0f}%"
            mp3 = work / f"voice_{i:02d}.mp3"
            try:
                result = narration.synth(text,mp3,voice,beat_rate)
                dur = narration.to_wav(mp3,wav,pause)
                words, mode, alignment = result.words, result.mode, "tts"
            except Exception:
                if not v.get("allow_silent_fallback", False):
                    raise
                dur = suggested_duration(ctxs[i])
                narration.subprocess.run([FF,"-y","-loglevel","error","-f","lavfi","-i",
                                          "anullsrc=r=44100:cl=mono","-t",str(dur),str(wav)],check=True)
                words, mode, alignment = narration.estimated_words(text,dur), "silent-fallback", "none"
        if not words and mode != "silent-fallback":
            words = narration.estimated_words(text,dur)
            alignment = "estimated"
        scene_words.append(words)
        durations.append(dur)
        audio_mode.append(mode)
        alignments.append(alignment)
        audio_parts.append(wav)
        _emit(on_step, "dubbing", 0.05 + 0.30 * (i + 1) / max(n, 1),
              f"narasi beat {i + 1}/{n} · {mode}")
        print(f"  [{i + 1}/{n}] {b.get('kind', '?'):5} {dur:5.1f}s {mode}")

    # 2. frames per scene -> segmen (Manim kalau cocok, Pillow kalau tidak)
    video_parts: list[Path] = []
    total = 0.0
    animator_mode = str(v.get("animator", "pillow")).lower()
    for i, (ctx, dur) in enumerate(zip(ctxs, durations)):
        seg = work / f"seg_{i:02d}.mp4"
        used = "pillow"

        if animator_mode != "pillow" and wants_manim(ctx, cfg):
            raw = work / f"manim_{i:02d}.mp4"
            clip = render_manim_clip(manim_spec(ctx), dur, raw, kind=ctx.beat.get("kind", "point"))
            if clip:
                seg = overlay_chrome_on_clip(clip, ctx, work / f"segm_{i:02d}.mp4", dur,
                                             fps=fps, cfg=cfg)
                used = "manim"

        if used == "pillow":
            nframes = max(2, int(round(dur * fps)))

            def gen(ctx=ctx, nframes=nframes):
                for k in range(nframes):
                    yield render_frame(ctx, k / fps, (W, H))

            frames_to_video(gen(), seg, W, H, fps, crf=crf)
        seg_animator = used
        _emit(on_step, "animasi", 0.35 + 0.45 * (i + 1) / max(n, 1),
              f"scene {i + 1}/{n} ({used})")
        video_parts.append(seg)
        timeline.append({"beat": i, "kind": beats[i].get("kind"), "start": round(total, 2),
                         "duration": round(dur, 2), "visual": ctx.vtype,
                         "animator": seg_animator,
                         "headline": beats[i].get("headline"),
                         "words": len(scene_words[i]),
                         "audio": audio_mode[i]})
        total += dur

    silent = work / "video_silent.mp4"
    concat(video_parts, silent, work)
    voice_only = work / "voice_only.wav"
    concat(audio_parts, voice_only, work, reencode_audio=True)

    # audio final: voice + musik latar (disintesis, bebas royalti) + sfx transisi
    voice_full = voice_only
    if v.get("music", True):
        try:
            bed = audio_mod.bed_for_episode(total, work, theme=script.get("theme"),
                                            style=v.get("music_style"))
            cues: list[tuple[Path, float]] = []
            if v.get("sfx", True):
                whoosh = audio_mod.sfx("whoosh", out=work / "sfx_whoosh.wav")
                cues.append((whoosh, 0.05))              # transisi di awal episode
                for tl in timeline[1:4]:
                    cues.append((audio_mod.sfx("pop", out=work / "sfx_pop.wav",
                                               seed=int(tl["beat"]) + 1), tl["start"]))
            _emit(on_step, "dubbing", 0.86, "musik latar + ducking")
            voice_full = audio_mod.mix(voice_only, work / "voice_mix.wav", bed, cues,
                                       music_db=float(v.get("music_db", -12.0)))
            print(f"  musik latar + {len(cues)} sfx dicampur (ducking aktif)")
        except Exception as e:
            print(f"  [warn] pencampuran audio gagal ({str(e)[:90]}), pakai voice saja")
            voice_full = voice_only

    # 3. caption
    subs = None
    if burn_captions and not any(scene_words):
        raise RuntimeError("Caption diminta tetapi timing tidak tersedia; render tidak boleh lanjut tanpa caption")
    if burn_captions and any(scene_words):
        subs = work / "captions.ass"
        cap.captions_for_scenes(scene_words, durations, subs,
                                max_words=int(v.get("caption_words", 6)), style=v.get("caption_style", "box"))

    final = d / "final.mp4"
    _emit(on_step, "animasi", 0.95, "menyusun final.mp4")
    mux(silent, voice_full, final, subs)
    if burn_captions and not (subs and subs.exists()):
        raise RuntimeError("Caption gagal dibuat")

    # 4. cover + laporan layout
    cover = render_cover(script, cfg, d / "cover.png")
    layout = check_layout(ctxs)

    meta = {
        "episode_id": episode_id,
        "video": str(final),
        "cover": str(cover),
        "duration_sec": round(probe_duration(final), 2),
        "voice": voice,
        "captions": bool(subs and subs.exists()),
        "caption_style": v.get("caption_style","box"),
        "caption_alignment": alignments,
        "style": v.get("style","motion"),
        "audio_modes": audio_mode,
        "generator": script.get("generator","unknown"),
        "layout": layout,
        "timeline": timeline,
        "width": W, "height": H, "fps": fps,
    }
    (d / "render_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    flag = "✔" if layout["ok"] else "⚠"
    print(f"\n{flag} {final}  ({meta['duration_sec']}s, {n} scene, caption={meta['captions']})")
    if not layout["ok"]:
        print(f"   layout: {len(layout['problems'])} blok keluar area aman")
    return meta
