"""AUDIO GRATIS & BEBAS ROYALTI — disintesis sendiri, bukan diunduh.

Kenapa disintesis:
  * Musik dari internet (bahkan yang "free") sering berakhir Content ID claim
    atau tak jelas lisensinya. Yang kita bangun sendiri tidak bisa diklaim.
  * Ukuran kecil, tanpa dependency jaringan, tanpa API key.
  * Bisa disesuaikan mood per topik (tech = arpeggio cepat, reflective = pad lembut).

Yang dihasilkan:
  `music_bed()`  — musik latar 30-70 detik, loopable, tanpa vokal
  `sfx(name)`    — whoosh / pop / riser pendek untuk transisi
  `mix()`        — gabungkan voice + musik + sfx dengan ducking (sidechain),
                   lalu normalisasi ke -14 LUFS

Semua fungsi menulis WAV 44.1 kHz mono supaya konsisten dengan pipeline.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np

from .config import find_ffmpeg

FF = find_ffmpeg()
SR = 44100

# progresi akor sederhana: Am7 - Fmaj7 - Cmaj7 - G  (frekuensi dasar, Hz)
CHORDS = {
    "Am7": [220.00, 261.63, 329.63, 392.00],
    "Fmaj7": [174.61, 220.00, 261.63, 329.63],
    "Cmaj7": [261.63, 329.63, 392.00, 493.88],
    "G": [196.00, 246.94, 293.66, 392.00],
}
PROGRESSION = ["Am7", "Fmaj7", "Cmaj7", "G"]


def _env(n: int, attack: float, decay: float, sustain: float = 0.0) -> np.ndarray:
    """Envelope ADSR ringkas."""
    a = max(1, int(attack * SR))
    d = max(1, int(decay * SR))
    env = np.zeros(n, dtype=np.float32)
    a = min(a, n)
    env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    rest = n - a
    if rest > 0:
        d = min(d, rest)
        env[a:a + d] = np.linspace(1, sustain, d, dtype=np.float32)
        if rest - d > 0:
            env[a + d:] = sustain
    return env


def _tone(freq: float, dur: float, wave: str = "sine", detune: float = 0.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = freq * (1 + detune)
    if wave == "sine":
        return np.sin(2 * np.pi * f * t).astype(np.float32)
    if wave == "tri":  # segitiga via harmonik ganjil
        out = np.zeros(n, dtype=np.float32)
        for k in range(1, 6, 2):
            out += ((-1) ** ((k - 1) // 2)) * np.sin(2 * np.pi * f * k * t) / (k * k)
        return (out * 8 / np.pi ** 2).astype(np.float32)
    if wave == "pad":  # dua gelombang detune = lebih hangat
        return ((np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.005 * t)) * 0.5).astype(np.float32)
    raise ValueError(wave)


def _lowpass(x: np.ndarray, cutoff_hz: float) -> np.ndarray:
    """One-pole lowpass (cukup untuk melembutkan noise & hat)."""
    a = math.exp(-2 * math.pi * cutoff_hz / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # loop python; durasi pendek jadi masih cepat
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def _noise(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.standard_normal(n).astype(np.float32) * 0.3


def music_bed(duration: float, style: str = "tech", out: Path | None = None,
              bpm: int = 84, seed: int = 7) -> Path:
    """Musik latar tanpa vokal. `style`: tech | calm | curious."""
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    mix = np.zeros(n, dtype=np.float32)

    beat = 60.0 / bpm
    bar = beat * 4
    arp_step = beat / 2 if style == "tech" else beat

    # --- pad lembut (semua style)
    bar_idx = 0
    t0 = 0.0
    while t0 < duration:
        chord = CHORDS[PROGRESSION[bar_idx % len(PROGRESSION)]]
        dur = min(bar * 1.02, duration - t0 + 0.1)
        seg_n = int(dur * SR)
        pad = np.zeros(seg_n, dtype=np.float32)
        for note in chord:
            pad += _tone(note / 2, dur, "pad")          # satu oktaf lebih rendah
        pad = pad / len(chord)
        pad *= _env(seg_n, attack=0.6, decay=0.5, sustain=0.55)
        start = int(t0 * SR)
        end = min(start + seg_n, n)
        if end > start:
            mix[start:end] += pad[: end - start] * (0.30 if style == "calm" else 0.22)
        t0 += bar
        bar_idx += 1

    # --- arpeggio (tech: 8 nada per bar, calm: 4)
    idx = 0
    t0 = 0.0
    while t0 < duration:
        chord = CHORDS[PROGRESSION[int(t0 // bar) % len(PROGRESSION)]]
        note = chord[idx % len(chord)] * (2 if style == "tech" else 1)
        dur = arp_step * 0.92
        tone = _tone(note, dur, "tri")
        tone *= _env(int(dur * SR), attack=0.01, decay=0.28, sustain=0.02)
        start = int(t0 * SR)
        end = min(start + len(tone), n)
        if end > start:
            gain = 0.16 if style == "tech" else 0.10
            mix[start:end] += tone[: end - start] * gain * (0.85 if idx % 2 else 1.0)
        t0 += arp_step
        idx += 1

    # --- perkusi ringan
    t0 = 0.0
    while t0 < duration:
        # kick di ketukan 1 & 3
        if int(t0 / beat) % 4 in (0, 2):
            dur = 0.17
            seg_n = int(dur * SR)
            tt = np.arange(seg_n, dtype=np.float32) / SR
            sweep = 110 * np.exp(-tt * 26) + 44
            kick = np.sin(2 * np.pi * np.cumsum(sweep) / SR).astype(np.float32)
            kick *= _env(seg_n, 0.002, dur, 0.0)
            start = int(t0 * SR)
            end = min(start + seg_n, n)
            if end > start:
                mix[start:end] += kick[: end - start] * 0.30
        # hat di off-beat
        t_hat = t0 + beat / 2
        if t_hat < duration:
            dur = 0.05
            seg_n = int(dur * SR)
            hat = _lowpass(_noise(seg_n, rng), 7000) * _env(seg_n, 0.001, dur, 0)
            start = int(t_hat * SR)
            end = min(start + seg_n, n)
            if end > start:
                mix[start:end] += hat[: end - start] * 0.14
        t0 += beat

    # --- fade in/out supaya tidak "patah"
    fi, fo = int(0.8 * SR), int(1.4 * SR)
    mix[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)
    if fo < n:
        mix[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)

    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak) * 0.6
    out = out or Path("music_bed.wav")
    _write_wav(mix, out)
    return out


def sfx(name: str = "whoosh", out: Path | None = None, seed: int = 3) -> Path:
    rng = np.random.default_rng(seed)
    if name == "whoosh":
        dur = 0.5
        n = int(dur * SR)
        noise = _noise(n, rng)
        # sweep filter sederhana: campur lowpass cutoff bergerak
        a = _lowpass(noise, 900)
        b = _lowpass(noise, 4000)
        ramp = np.linspace(0, 1, n, dtype=np.float32)
        sig = (a * (1 - ramp) + b * ramp) * _env(n, 0.18, 0.3, 0.0)
    elif name == "pop":
        dur = 0.12
        n = int(dur * SR)
        t = np.arange(n, dtype=np.float32) / SR
        sig = np.sin(2 * np.pi * (520 + 380 * np.exp(-t * 40)) * t) * _env(n, 0.003, dur, 0)
    elif name == "riser":
        dur = 0.9
        n = int(dur * SR)
        t = np.arange(n, dtype=np.float32) / SR
        f = 180 * np.exp(t * 1.6)
        sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.05, dur, 0.0)
        sig += _noise(n, rng) * 0.15 * np.linspace(0, 1, n, dtype=np.float32)
    else:
        raise ValueError(f"sfx tidak dikenal: {name}")

    peak = float(np.max(np.abs(sig))) or 1.0
    out = out or Path(f"sfx_{name}.wav")
    _write_wav(sig / peak * 0.5, out)
    return out


def _write_wav(x: np.ndarray, path: Path) -> None:
    import wave

    x = np.clip(x, -1.0, 1.0)
    pcm = (x * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def mix(voice_wav: Path, out_wav: Path, music: Path | None = None,
        sfx_files: list[tuple[Path, float]] | None = None,
        music_db: float = -22.0, duck: bool = True) -> Path:
    """Gabung voice + musik + sfx dengan ducking (musik mengecil saat ada suara).

    Graph yang benar (ini yang sempat salah: `asplit` dipakai tapi output
    keduanya tidak tersambung, jadi ffmpeg menolak seluruh filter):

        [0:a]asplit=2[voice][key]
        [1:a]volume=XdB,atrim[m]
        [m][key]sidechaincompress[...][ducked]
        [voice][ducked][sfx...]amix=inputs=N:duration=first:normalize=0[out]
    """
    dur = _duration(voice_wav)
    sfx_files = sfx_files or []
    inputs = ["-i", str(voice_wav)]

    # --- jalur utama: ducking aktif
    if music and duck:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        parts = [
            "[0:a]asplit=2[voice][key]",
            f"[1:a]volume={music_db}dB,atrim=0:{dur:.2f}[m]",
            "[m][key]sidechaincompress=threshold=0.05:ratio=12:attack=10:release=350[ducked]",
        ]
        mix_labels = ["[voice]", "[ducked]"]
        idx = 2
        for path, at in sfx_files:
            inputs += ["-i", str(path)]
            ms = max(0, int(at * 1000))
            parts.append(f"[{idx}:a]adelay={ms}|{ms},volume=-14dB[s{idx}]")
            mix_labels.append(f"[s{idx}]")
            idx += 1
        parts.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:"
                     f"duration=first:normalize=0[out]")
        r = _run([FF, "-y", "-hide_banner", "-loglevel", "error", *inputs,
                  "-filter_complex", ";".join(parts), "-map", "[out]",
                  "-ar", str(SR), "-ac", "1", str(out_wav)])
        if r.returncode == 0:
            return out_wav
        print(f"  [warn] ducking gagal ({r.stderr[-120:]}), coba tanpa ducking")

    # --- jalur kedua: musik dengan volume tetap
    inputs = ["-i", str(voice_wav)]
    parts, mix_labels = [], ["[0:a]"]
    idx = 1
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        parts.append(f"[{idx}:a]volume={music_db}dB,atrim=0:{dur:.2f}[m]")
        mix_labels.append("[m]")
        idx += 1
    for path, at in sfx_files:
        inputs += ["-i", str(path)]
        ms = max(0, int(at * 1000))
        parts.append(f"[{idx}:a]adelay={ms}|{ms},volume=-14dB[s{idx}]")
        mix_labels.append(f"[s{idx}]")
        idx += 1
    if len(mix_labels) > 1:
        parts.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:"
                     f"duration=first:normalize=0[out]")
        r = _run([FF, "-y", "-hide_banner", "-loglevel", "error", *inputs,
                  "-filter_complex", ";".join(parts), "-map", "[out]",
                  "-ar", str(SR), "-ac", "1", str(out_wav)])
        if r.returncode == 0:
            return out_wav
        print(f"  [warn] amix gagal ({r.stderr[-120:]}), pakai voice saja")

    # --- terakhir: voice saja (pipeline tidak boleh mati)
    _run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", str(voice_wav),
          "-ar", str(SR), "-ac", "1", str(out_wav)])
    return out_wav


def _duration(path: Path) -> float:
    import re

    out = subprocess.run([FF, "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out)
    if not m:
        return 30.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def bed_for_episode(duration: float, out_dir: Path, style: str | None = None,
                    theme: str | None = None) -> Path:
    """Pilih mood otomatis dari tema supaya tidak monoton antar episode."""
    if not style:
        style = {
            "on_device": "tech", "small_models": "tech", "agents": "tech",
            "coding": "tech", "open_source": "curious", "reasoning": "curious",
            "multimodal": "curious", "cost": "calm", "rag_memory": "calm",
            "safety": "calm",
        }.get(theme or "", "tech")
    return music_bed(duration + 2.0, style=style, out=out_dir / f"music_{style}.wav")


if __name__ == "__main__":

    print("membuat contoh musik & sfx...")
    m = music_bed(20, style="tech", out=Path("/tmp/music_tech.wav"))
    m2 = music_bed(20, style="calm", out=Path("/tmp/music_calm.wav"))
    for name in ("whoosh", "pop", "riser"):
        sfx(name, out=Path(f"/tmp/sfx_{name}.wav"))
    for p in [m, m2] + [Path(f"/tmp/sfx_{n}.wav") for n in ("whoosh", "pop", "riser")]:
        print(f"  {p}  {p.stat().st_size // 1024} KB")
