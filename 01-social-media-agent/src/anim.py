"""Engine animasi: easing, font, dan streaming frame ke ffmpeg.

Kenapa frame-by-frame, bukan zoompan:
  zoompan cuma bisa geser/zoom satu gambar statis. Untuk konten edukasi kita
  butuh elemen yang MASUK bergantian: kotak muncul satu-satu, panah tergambar,
  bar tumbuh dari nol, angka menghitung naik. Itu semua butuh gambar ulang per
  frame.

Performa: background dibuat SEKALI per scene lalu di-copy per frame, jadi biaya
per frame cuma beberapa operasi draw. ~1400 frame ≈ 15-25 detik di 2 vCPU.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import find_ffmpeg

FF = find_ffmpeg()
ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "assets" / "fonts"

# nama file -> (family, default weight axis)
FONT_FILES = {
    "body": ("PlusJakarta.ttf", 500),
    "bold": ("PlusJakarta.ttf", 800),
    "display": ("Outfit.ttf", 700),
    "mono": ("Inter.ttf", 500),
}
_fallback = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_font_cache: dict[tuple, ImageFont.FreeTypeFont] = {}


def font(kind: str = "body", size: int = 48, weight: int | None = None) -> ImageFont.FreeTypeFont:
    fname, default_w = FONT_FILES.get(kind, FONT_FILES["body"])
    w = weight or default_w
    key = (kind, size, w)
    if key in _font_cache:
        return _font_cache[key]
    path = FONT_DIR / fname
    if path.exists():
        f = ImageFont.truetype(str(path), size)
        try:  # variable font: set sumbu berat
            axes = [a["name"] for a in f.get_variation_axes()]
            vals = []
            for name in axes:
                low = name.decode() if isinstance(name, bytes) else name
                if "Weight" in low:
                    vals.append(w)
                else:
                    vals.append(14 if "Optical" in low else 0)
            f.set_variation_by_axes(vals)
        except Exception:
            pass
    else:
        f = ImageFont.truetype(_fallback, size)
    _font_cache[key] = f
    return f


# ---------------------------------------------------------------- easing

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def ease_out_cubic(t: float) -> float:
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    t = clamp(t)
    return 3 * t ** 2 - 2 * t ** 3


def ease_out_back(t: float, s: float = 1.70158) -> float:
    t = clamp(t)
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


def ease_out_expo(t: float) -> float:
    t = clamp(t)
    return 1 if t >= 1 else 1 - 2 ** (-10 * t)


def prog(t: float, start: float, dur: float) -> float:
    """Progress lokal 0..1 untuk animasi yang mulai di `start`."""
    if dur <= 0:
        return 1.0 if t >= start else 0.0
    return clamp((t - start) / dur)


def rgba(color: tuple, a: float) -> tuple:
    return (color[0], color[1], color[2], int(clamp(a) * 255))


def mix(c1: tuple, c2: tuple, t: float) -> tuple:
    t = clamp(t)
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


# ---------------------------------------------------------------- text

def wrap(text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in str(text).split("\n"):
        words, cur = para.split(), ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if f.getlength(trial) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines or [""]


def fit(text: str, kind: str, max_w: int, max_lines: int, start: int, min_size: int,
        weight: int | None = None) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    size = start
    while size > min_size:
        f = font(kind, size, weight)
        lines = wrap(text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines
        size -= 3
    f = font(kind, min_size, weight)
    lines = wrap(text, f, max_w)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,") + "…"
    return f, lines


def text_block(img: Image.Image, lines: list[str], f: ImageFont.FreeTypeFont, xy: tuple,
               fill, line_gap: float = 1.24, anchor_y: bool = False) -> tuple[int, int, int, int]:
    """Gambar multi-baris. Return bbox (x0,y0,x1,y1) untuk QC."""
    d = ImageDraw.Draw(img)
    x, y = xy
    lh = int(f.size * line_gap)
    for i, line in enumerate(lines):
        d.text((x, y + i * lh), line, font=f, fill=fill)
    w = int(max(f.getlength(ln) for ln in lines)) if lines else 0
    return (int(x), int(y), int(x + w), int(y + lh * len(lines)))


def block_h(lines: list[str], f: ImageFont.FreeTypeFont, line_gap: float = 1.24) -> int:
    return int(len(lines) * f.size * line_gap)


def center_block(img: Image.Image, lines: list[str], f: ImageFont.FreeTypeFont, cx: int,
                 y: int, fill, line_gap: float = 1.24) -> tuple:
    d = ImageDraw.Draw(img)
    lh = int(f.size * line_gap)
    for i, line in enumerate(lines):
        d.text((cx, y + i * lh), line, font=f, fill=fill, anchor="ma")
    return (0, int(y), img.width, int(y + lh * len(lines)))


# ---------------------------------------------------------------- background

_bg_cache: dict[str, Image.Image] = {}


def background(w: int, h: int, accent: tuple, key: str = "default") -> Image.Image:
    ck = f"{w}x{h}:{accent}:{key}"
    if ck in _bg_cache:
        return _bg_cache[ck]
    img = Image.new("RGB", (w, h), (6, 8, 16))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = (y / (h - 1)) ** 0.9
        d.line([(0, y), (w, y)], fill=mix((6, 8, 16), (14, 21, 38), t))

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-260, -140, int(w * 0.92), int(h * 0.56)], fill=(*accent, 46))
    gd.ellipse([int(w * 0.35), int(h * 0.62), w + 280, h + 220], fill=(*accent, 26))
    glow = glow.filter(ImageFilter.GaussianBlur(int(w * 0.16)))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

    grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    step = max(48, w // 11)
    for x in range(0, w, step):
        gd.line([(x, 0), (x, h)], fill=(255, 255, 255, 6))
    for y in range(0, h, step):
        gd.line([(0, y), (w, y)], fill=(255, 255, 255, 6))
    img = Image.alpha_composite(img.convert("RGBA"), grid).convert("RGB")
    _bg_cache[ck] = img
    return img


# ---------------------------------------------------------------- encoder

def frames_to_video(frames_iter, out_path: Path, w: int, h: int, fps: int,
                    crf: int = 23, preset: str = "veryfast") -> None:
    """Stream RGB frame ke ffmpeg lewat stdin (tanpa menulis PNG ke disk)."""
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-an", "-c:v", "libx264", "-threads", "2", "-preset", preset,
           "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    try:
        for img in frames_iter:
            # Renderer 2D bisa menghasilkan RGBA; ffmpeg minta rgb24 (3 byte/px).
            # Tanpa konversi ini, stride tidak cocok dan video tampil rusak.
            if img.mode != "RGB":
                img = img.convert("RGB")
            proc.stdin.write(img.tobytes())
    except BrokenPipeError:
        pass
    finally:
        err = b""
        if proc.stdin:
            proc.stdin.close()
        err = proc.stderr.read() if proc.stderr else b""
        code = proc.wait()
    if code != 0:
        raise RuntimeError(f"encode frame gagal: {err[-400:].decode(errors='ignore')}")
