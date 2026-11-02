"""Renderer visual per-scene: 8 tipe scene yang di-animasikan.

Dipilih berdasarkan `visual.type` di script JSON:
  card      teks besar + penjelasan
  diagram   kotak berurutan dengan panah yang tergambar
  steps     daftar langkah bernomor
  bars      bar chart tumbuh (perbandingan)
  stat      angka besar menghitung naik
  compare   dua kolom (lama vs baru, salah vs benar)
  code      blok kode/monospace yang mengetik
  quote     kutipan besar

Semua renderer menerima `t` (detik) dan menggambar frame. Tidak ada state global
selain cache background + font, jadi render script yang sama selalu menghasilkan
video yang sama.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

from pathlib import Path

from .anim import (background, block_h, center_block, ease_in_out, ease_out_back,
                   ease_out_cubic, ease_out_expo, fit, font, mix, prog, rgba,
                   text_block)

INK = (247, 250, 255)
SUB = (198, 212, 232)
MUTED = (132, 148, 172)
PANEL = (255, 255, 255)

ACCENT = {
    "hook": (94, 234, 212),
    "point": (125, 211, 252),
    "limit": (252, 165, 165),
    "cta": (167, 139, 250),
}

MARGIN = 84
CONTENT_W = 1080 - 2 * MARGIN
TOP_SAFE, BOTTOM_SAFE = 240, 1600


@dataclass
class Ctx:
    """Konteks satu scene: data + kotak yang dilaporkan untuk QC."""
    beat: dict
    idx: int
    total: int
    cfg: dict
    sources: list[str] = field(default_factory=list)
    bboxes: list[tuple] = field(default_factory=list)

    @property
    def accent(self) -> tuple:
        return ACCENT.get(self.beat.get("kind", "point"), ACCENT["point"])

    @property
    def visual(self) -> dict:
        v = self.beat.get("visual") or {}
        return v if isinstance(v, dict) else {}

    @property
    def vtype(self) -> str:
        t = self.visual.get("type")
        if t in ("card", "diagram", "steps", "bars", "stat", "compare", "code", "quote", "character", "clock", "thermometer", "manim"):
            return t
        # fallback otomatis dari jenis beat
        return "card"

    @property
    def props(self) -> dict:
        p = self.visual.get("props") or {}
        return p if isinstance(p, dict) else {}


# ---------------------------------------------------------------- chrome

def render_chrome_overlay(ctx: Ctx, t: float, size: tuple[int, int]) -> Image.Image:
    """Chrome saja di atas latar transparan — untuk ditempel ke clip Manim."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_chrome(img, ctx, t)
    return img


def draw_chrome(img: Image.Image, ctx: Ctx, t: float) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    accent = ctx.accent
    brand = ctx.cfg.get("brand", {})
    W = img.width

    a = ease_out_cubic(prog(t, 0.0, 0.45))
    # brand pill
    f = font("bold", 27, 700)
    label = str(brand.get("name", "AI DALAM 60 DETIK")).upper()
    tw = int(f.getlength(label))
    x0, y0 = MARGIN, 104 - int(10 * (1 - a))
    d.rounded_rectangle([x0, y0, x0 + tw + 56, y0 + 58], radius=29,
                        fill=rgba(accent, 0.10 * a), outline=rgba(accent, 0.72 * a), width=2)
    d.text((x0 + 28, y0 + 29), label, font=f, fill=rgba(accent, a), anchor="lm")

    # counter
    cf = font("body", 25, 600)
    d.text((W - MARGIN, y0 + 29), f"{ctx.idx + 1:02d}/{ctx.total:02d}", font=cf,
           fill=rgba(MUTED, a), anchor="rm")

    # progress segments
    gap, y = 8, 190
    seg_w = (CONTENT_W - gap * (ctx.total - 1)) / max(1, ctx.total)
    for i in range(ctx.total):
        sx = MARGIN + i * (seg_w + gap)
        if i < ctx.idx:
            d.rounded_rectangle([sx, y, sx + seg_w, y + 5], radius=3, fill=rgba(accent, 0.9))
        elif i == ctx.idx:
            grow = ease_out_cubic(prog(t, 0.0, 1.2))
            d.rounded_rectangle([sx, y, sx + max(6, seg_w * grow), y + 5], radius=3,
                                fill=rgba(accent, 1.0))
        else:
            d.rounded_rectangle([sx, y, sx + seg_w, y + 5], radius=3, fill=rgba(PANEL, 0.13))

    # footer
    ff = font("bold", 29, 700)
    d.text((MARGIN, 1652), str(brand.get("handle", "@aipelan60")), font=ff, fill=rgba(SUB, a))
    d.text((MARGIN, 1698), "satu konsep AI, satu menit", font=font("body", 24, 400),
           fill=rgba(MUTED, a))

    # source chips
    if ctx.sources:
        cf2 = font("body", 22, 500)
        x, cy = MARGIN, 1540
        for s in ctx.sources[:3]:
            tw2 = int(cf2.getlength(s))
            bw = tw2 + 36
            if x + bw > W - MARGIN:
                break
            d.rounded_rectangle([x, cy, x + bw, cy + 44], radius=22,
                                fill=rgba(PANEL, 0.07 * a), outline=rgba(PANEL, 0.16 * a))
            d.text((x + 18, cy + 22), s, font=cf2, fill=rgba(MUTED, a), anchor="lm")
            x += bw + 12


def _headline(img, ctx, t, start=0.10, size=92, max_lines=3, y=340, center=False):
    """Headline yang naik + fade. Return y akhir."""
    text = (ctx.beat.get("headline") or "").strip()
    if not text:
        return y
    p = ease_out_cubic(prog(t, start, 0.55))
    f, lines = fit(text, "bold", CONTENT_W, max_lines, size, 54, weight=800)
    yy = y + int(46 * (1 - p))
    if center:
        bbox = center_block(img, lines, f, img.width // 2, yy, rgba(INK, p))
    else:
        bbox = text_block(img, lines, f, (MARGIN, yy), rgba(INK, p), 1.06)
    ctx.bboxes.append(bbox)
    return bbox[3]


def _accent_bar(img, ctx, t, y, width=132, height=10, start=0.32):
    p = ease_out_cubic(prog(t, start, 0.5))
    if p <= 0:
        return y
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([MARGIN, y, MARGIN + max(6, width * p), y + height], radius=height // 2,
                        fill=rgba(ctx.accent, 0.95))
    return y + height


def _body(img, ctx, t, y, size=52, max_lines=5, start=0.42, text=None):
    text = text if text is not None else (ctx.beat.get("body") or ctx.beat.get("narration") or "")
    if not text:
        return y
    p = ease_out_cubic(prog(t, start, 0.6))
    f, lines = fit(text, "body", CONTENT_W, max_lines, size, 32, weight=450)
    bbox = text_block(img, lines, f, (MARGIN, y + int(26 * (1 - p))), rgba(SUB, p), 1.40)
    ctx.bboxes.append(bbox)
    return bbox[3]


# ---------------------------------------------------------------- scene types

def draw_card(img, ctx, t):
    hl = (ctx.beat.get("headline") or "")
    body = (ctx.beat.get("body") or ctx.beat.get("narration") or "")
    size = 100 if ctx.beat.get("kind") == "hook" else 84
    hf, hl_lines = fit(hl, "bold", CONTENT_W, 3, size, 54, weight=800)
    bf, bl = fit(body, "body", CONTENT_W, 5, 52, 32, weight=450)
    content_h = block_h(hl_lines, hf, 1.06) + 42 + 10 + 44 + block_h(bl, bf, 1.40)
    top = TOP_SAFE + 60 + max(0, int((BOTTOM_SAFE - TOP_SAFE - 120 - content_h) * 0.34))
    y = _headline(img, ctx, t, size=size, max_lines=3, y=top)
    y = _accent_bar(img, ctx, t, y + 42)
    _body(img, ctx, t, y + 44, size=52, max_lines=5)


def draw_diagram(img, ctx, t):
    nodes = ctx.props.get("nodes") or []
    if len(nodes) < 2:
        return draw_card(img, ctx, t)
    d = ImageDraw.Draw(img, "RGBA")
    y0 = _headline(img, ctx, t, size=76, max_lines=2, y=330)
    y = max(y0 + 56, 520)

    n = min(len(nodes), 4)
    box_h = 132 if n <= 3 else 108
    gap = 92
    for i, node in enumerate(nodes[:n]):
        p = ease_out_back(prog(t, 0.30 + i * 0.22, 0.5), 1.2)
        if p <= 0:
            continue
        bx0 = MARGIN + int(70 * (1 - p))
        by0 = y + i * (box_h + gap)
        bx1, by1 = MARGIN + CONTENT_W, by0 + box_h
        d.rounded_rectangle([bx0, by0, bx1, by1], radius=26,
                            fill=rgba(mix((16, 22, 38), ctx.accent, 0.10), p),
                            outline=rgba(ctx.accent, 0.55 * p), width=2)
        title = str(node.get("title", ""))[:40]
        tx = bx0 + 76
        tf, tl = fit(title, "bold", CONTENT_W - 190, 1, 44, 28, weight=750)
        d.text((tx, by0 + box_h // 2 - (18 if node.get("sub") else 0)), tl[0],
               font=tf, fill=rgba(INK, p), anchor="lm")
        if node.get("sub"):
            sf, sl = fit(str(node["sub"])[:60], "body", CONTENT_W - 190, 1, 27, 21, weight=450)
            d.text((tx, by0 + box_h // 2 + 26), sl[0], font=sf,
                   fill=rgba(SUB, 0.9 * p), anchor="lm")
        # nomor bulat
        d.ellipse([bx0 + 14, by0 + 14, bx0 + 14 + 34, by0 + 14 + 34], fill=rgba(ctx.accent, 0.85 * p))
        d.text((bx0 + 31, by0 + 31), str(i + 1), font=font("bold", 22, 800),
               fill=rgba((10, 14, 24), p), anchor="mm")
        ctx.bboxes.append((bx0, by0, bx1, by1))

        if i < n - 1:  # panah
            ap = ease_in_out(prog(t, 0.46 + i * 0.22, 0.34))
            if ap > 0:
                ax = MARGIN + CONTENT_W / 2
                ay0 = by1 + 8
                ay1 = ay0 + (gap - 20)
                cut = ay0 + (ay1 - ay0) * ap
                d.line([(ax, ay0), (ax, cut)], fill=rgba(ctx.accent, 0.75), width=5)
                if ap > 0.92:
                    d.polygon([(ax - 13, cut - 6), (ax + 13, cut - 6), (ax, cut + 16)],
                              fill=rgba(ctx.accent, 0.95))


def draw_steps(img, ctx, t):
    items = ctx.props.get("items") or []
    if not items:
        return draw_card(img, ctx, t)
    d = ImageDraw.Draw(img, "RGBA")
    y0 = _headline(img, ctx, t, size=72, max_lines=2, y=320)
    y = max(y0 + 54, 480)
    for i, item in enumerate(items[:4]):
        p = ease_out_cubic(prog(t, 0.26 + i * 0.20, 0.5))
        if p <= 0:
            continue
        row_h = 128
        ry = y + i * (row_h + 22)
        d.rounded_rectangle([MARGIN + int(-60 * (1 - p)), ry, MARGIN + CONTENT_W, ry + row_h],
                            radius=24, fill=rgba(PANEL, 0.055 * p),
                            outline=rgba(PANEL, 0.11 * p))
        d.ellipse([MARGIN + 26, ry + row_h // 2 - 27, MARGIN + 26 + 54, ry + row_h // 2 + 27],
                  fill=rgba(ctx.accent, 0.9 * p))
        d.text((MARGIN + 53, ry + row_h // 2), str(i + 1), font=font("bold", 32, 800),
               fill=rgba((10, 14, 24), p), anchor="mm")
        txt = str(item.get("title") if isinstance(item, dict) else item)
        tf, tl = fit(txt, "bold", CONTENT_W - 150, 2, 44, 28, weight=650)
        d.text((MARGIN + 110, ry + row_h // 2), tl[0] if len(tl) == 1 else tl[0],
               font=tf, fill=rgba(INK, p), anchor="lm")
        if len(tl) > 1:
            d.text((MARGIN + 110, ry + row_h // 2 + 34), tl[1], font=tf, fill=rgba(INK, p), anchor="lm")
        ctx.bboxes.append((MARGIN, ry, MARGIN + CONTENT_W, ry + row_h))


def draw_bars(img, ctx, t):
    items = ctx.props.get("items") or []
    if not items:
        return draw_card(img, ctx, t)
    d = ImageDraw.Draw(img, "RGBA")
    y0 = _headline(img, ctx, t, size=72, max_lines=2, y=320)
    y = max(y0 + 70, 520)
    unit = ctx.props.get("unit", "")
    vals = []
    for it in items:
        try:
            vals.append(float(it.get("value", 0)))
        except Exception:
            vals.append(0.0)
    mx = max(vals) if vals and max(vals) > 0 else 1.0
    row_h, bar_h = 150, 46
    for i, it in enumerate(items[:4]):
        p = ease_out_expo(prog(t, 0.26 + i * 0.18, 0.8))
        ry = y + i * row_h
        label = str(it.get("label", ""))[:34]
        lf, ll = fit(label, "body", CONTENT_W, 1, 34, 24, weight=600)
        d.text((MARGIN, ry), ll[0], font=lf, fill=rgba(SUB, 0.95))
        bw = int((CONTENT_W - 180) * (vals[i] / mx) * p) if mx else 0
        col = ctx.accent if i == 0 else mix(ctx.accent, (110, 130, 160), 0.55)
        d.rounded_rectangle([MARGIN, ry + 48, MARGIN + max(4, bw), ry + 48 + bar_h],
                            radius=bar_h // 2, fill=rgba(col, 0.92))
        shown = vals[i] * p
        vtxt = f"{shown:,.0f}".replace(",", ".") + unit
        d.text((MARGIN + max(bw, 6) + 16, ry + 48 + bar_h // 2), vtxt,
               font=font("bold", 34, 700), fill=rgba(INK, p), anchor="lm")
        ctx.bboxes.append((MARGIN, ry, MARGIN + CONTENT_W, ry + 48 + bar_h))


def draw_stat(img, ctx, t):
    raw = str(ctx.props.get("value", ""))
    m = re.match(r"^([^\d\-+]*)([-+]?\d+(?:[.,]\d+)?)(.*)$", raw)
    p = ease_out_expo(prog(t, 0.15, 1.0))
    if m:
        pre, num, suf = m.group(1), m.group(2), m.group(3)
        target = float(num.replace(",", "."))
        cur = target * p
        dec = 1 if ("," in num or "." in num) else 0
        shown = f"{pre}{cur:,.{dec}f}{suf}".replace(",", "." if dec == 0 else ",")
    else:
        shown = raw

    sf, sl = fit(shown, "display", CONTENT_W, 1, 230, 100, weight=800)
    yy = 560 + int(30 * (1 - p))
    bbox = center_block(img, sl, sf, img.width // 2, yy, rgba(INK, p))
    ctx.bboxes.append(bbox)
    label = str(ctx.props.get("label") or ctx.beat.get("headline") or "")
    cursor = bbox[3] + 10
    if label:
        lf, ll = fit(label, "bold", CONTENT_W, 2, 54, 32, weight=700)
        lb = center_block(img, ll, lf, img.width // 2, cursor,
                          rgba(ctx.accent, ease_out_cubic(prog(t, 0.5, 0.5))))
        cursor = lb[3] + 26
    sub = ctx.props.get("sub") or ctx.beat.get("body")
    if sub:
        bf, bl = fit(str(sub), "body", CONTENT_W - 60, 3, 38, 26, weight=450)
        center_block(img, bl, bf, img.width // 2, cursor,
                     rgba(SUB, ease_out_cubic(prog(t, 0.75, 0.6))))


def draw_compare(img, ctx, t):
    d = ImageDraw.Draw(img, "RGBA")
    y0 = _headline(img, ctx, t, size=68, max_lines=2, y=310)
    y = max(y0 + 56, 500)
    cols = [ctx.props.get("left") or {}, ctx.props.get("right") or {}]
    col_w = (CONTENT_W - 24) // 2
    for ci, col in enumerate(cols):
        p = ease_out_back(prog(t, 0.26 + ci * 0.18, 0.55), 1.1)
        if p <= 0:
            continue
        x0 = MARGIN + ci * (col_w + 24)
        tint = (252, 165, 165) if ci == 0 else (134, 239, 172)
        n_items = len((col.get("items") or [])[:4])
        panel_h = 190 + n_items * 62
        d.rounded_rectangle([x0, y + int(50 * (1 - p)), x0 + col_w, y + panel_h], radius=26,
                            fill=rgba(mix((14, 20, 34), tint, 0.12), p),
                            outline=rgba(tint, 0.45 * p), width=2)
        cx, cy, r = x0 + col_w // 2, y + 52, 19
        if ci == 0:  # silang
            d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=rgba(tint, p), width=6)
            d.line([(cx + r, cy - r), (cx - r, cy + r)], fill=rgba(tint, p), width=6)
        else:  # centang
            d.line([(cx - r, cy), (cx - 4, cy + r - 2)], fill=rgba(tint, p), width=6)
            d.line([(cx - 4, cy + r - 2), (cx + r, cy - r)], fill=rgba(tint, p), width=6)
        tf, tl = fit(str(col.get("title", ""))[:26], "bold", col_w - 48, 2, 38, 26, weight=750)
        center_block(img, tl, tf, x0 + col_w // 2, y + 96, rgba(INK, p))
        yy = y + 96 + block_h(tl, tf) + 24
        for item in (col.get("items") or [])[:4]:
            if yy > y + panel_h - 40:
                break
            f2, l2 = fit("• " + str(item)[:40], "body", col_w - 52, 2, 30, 20, weight=450)
            bbox = text_block(img, l2, f2, (x0 + 24, yy), rgba(SUB, 0.95 * p), 1.3)
            yy = bbox[3] + 10
        ctx.bboxes.append((x0, y, x0 + col_w, y + panel_h))


def draw_code(img, ctx, t):
    d = ImageDraw.Draw(img, "RGBA")
    y0 = _headline(img, ctx, t, size=66, max_lines=2, y=300)
    lines = [str(x) for x in (ctx.props.get("lines") or [])][:8]
    if not lines:
        return draw_card(img, ctx, t)
    panel_y = max(y0 + 54, 470)
    ph = min(760, 60 + len(lines) * 62)
    p = ease_out_cubic(prog(t, 0.2, 0.5))
    d.rounded_rectangle([MARGIN, panel_y, MARGIN + CONTENT_W, panel_y + ph], radius=24,
                        fill=rgba((8, 12, 22), 0.92 * p), outline=rgba(PANEL, 0.14 * p), width=2)
    for i, dot in enumerate([(252, 165, 165), (253, 224, 71), (134, 239, 172)]):
        d.ellipse([MARGIN + 22 + i * 26, panel_y + 20, MARGIN + 34 + i * 26, panel_y + 32],
                  fill=rgba(dot, 0.85 * p))
    mf = font("mono", 30, 500)
    total_chars = sum(len(ln) for ln in lines) or 1
    budget = total_chars * ease_in_out(prog(t, 0.35, 1.4))
    used = 0
    for i, line in enumerate(lines):
        avail = max(0, budget - used)
        chunk = line[: int(avail)]
        used += len(line)
        if not chunk:
            break
        colour = ctx.accent if chunk.strip().startswith(("#", "//")) else INK
        d.text((MARGIN + 26, panel_y + 56 + i * 62), chunk, font=mf, fill=rgba(colour, p))
        if 0 < avail < len(line) and int(t * 3) % 2 == 0:  # kursor
            cw = mf.getlength(chunk)
            d.rectangle([MARGIN + 26 + cw + 3, panel_y + 56 + i * 62 + 4,
                         MARGIN + 26 + cw + 16, panel_y + 56 + i * 62 + 36], fill=rgba(ctx.accent, p))
    ctx.bboxes.append((MARGIN, panel_y, MARGIN + CONTENT_W, panel_y + ph))


def draw_quote(img, ctx, t):
    d = ImageDraw.Draw(img, "RGBA")
    p = ease_out_cubic(prog(t, 0.1, 0.6))
    f = font("display", 190, 800)
    d.text((MARGIN - 8, 360), "“", font=f, fill=rgba(ctx.accent, 0.5 * p))
    text = str(ctx.props.get("text") or ctx.beat.get("body") or ctx.beat.get("narration") or "")
    tf, tl = fit(text, "bold", CONTENT_W, 6, 74, 40, weight=700)
    bbox = text_block(img, tl, tf, (MARGIN, 540 + int(28 * (1 - p))), rgba(INK, p), 1.26)
    ctx.bboxes.append(bbox)
    attr = ctx.props.get("attribution") or ctx.beat.get("headline")
    if attr:
        af, al = fit(str(attr), "body", CONTENT_W, 1, 34, 24, weight=600)
        text_block(img, al, af, (MARGIN, bbox[3] + 34),
                   rgba(ctx.accent, ease_out_cubic(prog(t, 0.55, 0.5))))


RENDERERS = {
    "card": draw_card, "diagram": draw_diagram, "steps": draw_steps, "bars": draw_bars,
    "stat": draw_stat, "compare": draw_compare, "code": draw_code, "quote": draw_quote,
    # "manim" tidak punya renderer Pillow: clip dirender terpisah lalu di-overlay chrome.
    # Fallback di bawah menjaga pipeline tetap jalan kalau Manim mati.
    "manim": draw_diagram,
    "character": draw_card, "clock": draw_card, "thermometer": draw_card,
}

from .characters2d import render_story_frame  # noqa: E402


CLIP_DIR: dict[str, "object"] = {}   # episode_id -> Path folder clip manim


def render_frame(ctx: Ctx, t: float, size: tuple[int, int]) -> Image.Image:
    """Frame untuk renderer Pillow. Tipe 'manim' tidak lewat sini (dipakai clip)."""
    if ctx.cfg.get("video", {}).get("style", "motion") == "story2d":
        return render_story_frame(ctx, t, size).convert("RGBA")
    img = background(size[0], size[1], ctx.accent, key=ctx.beat.get("kind", "point")).copy()
    draw_chrome(img, ctx, t)
    RENDERERS[ctx.vtype](img, ctx, t)
    return img


def manim_spec(ctx: Ctx) -> dict:
    """Terjemahkan beat jadi spec scene Manim yang setara."""
    v = ctx.visual
    props = ctx.props
    if v.get("type") == "manim":
        # bentuk eksplisit: {"type":"manim","props":{"scene":"diagram","nodes":[...]}}
        scene = props.get("scene", "diagram")
        return {"type": scene, **{k: val for k, val in props.items() if k != "scene"}}
    # bentuk implisit: tipe visual apa pun bisa dipaksa jadi Manim
    return {"type": v.get("type", "diagram"), **props}


def wants_manim(ctx: Ctx, cfg: dict) -> bool:
    if cfg.get("video", {}).get("style") == "story2d":
        return False
    mode = str(cfg.get("video", {}).get("animator", "pillow")).lower()
    if mode == "pillow":
        return False
    explicit = ctx.vtype == "manim"
    if mode == "manim":
        return explicit or ctx.vtype in ("diagram", "steps", "bars", "compare", "stat")
    if mode == "auto":
        return explicit or (ctx.beat.get("kind") == "point" and ctx.vtype in
                            ("diagram", "bars", "compare", "stat"))
    return False


def overlay_chrome_on_clip(clip_mp4: Path, ctx: Ctx, out_mp4: Path, duration: float,
                           fps: int = 24, cfg: dict | None = None) -> Path:
    """Tempel chrome (brand/progress/footer) ke clip Manim supaya identitas tetap sama."""
    import subprocess
    import tempfile

    from .config import find_ffmpeg

    ff = find_ffmpeg()
    tmp = Path(tempfile.mkdtemp(prefix="chrome_"))
    png = tmp / "chrome.png"
    render_chrome_overlay(ctx, min(1.4, duration * 0.6), (1080, 1920)).save(png)
    r = subprocess.run(
        [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(clip_mp4),
         "-loop", "1", "-i", str(png), "-filter_complex",
         "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p",
         "-t", f"{duration:.3f}", "-r", str(fps), "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "20", "-an", str(out_mp4)],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [warn] overlay chrome gagal: {r.stderr[-160:]}")
        return clip_mp4
    return out_mp4


def suggested_duration(ctx: Ctx) -> float:
    """Dipakai kalau TTS mati: durasi layak supaya animasi selesai."""
    return max(2.6, 2.2 + 0.9 * len((ctx.beat.get("narration") or "").split()) / 3.0)
