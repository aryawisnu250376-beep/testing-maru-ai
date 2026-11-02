"""MANIM — animasi diagram sungguhan (Manim Community, MIT, gratis).

Kapan dipakai:
  Beat dengan `visual.type = "manim"`. Cocok untuk hal yang butuh gerak
  matematis/mekanis: proses bertahap, perbandingan besaran, transformasi bentuk,
  alur yang "tumbuh". Untuk teks biasa, renderer Pillow lebih cepat.

Cara kerja:
  1. Bangun file scene Manim dari spec JSON beat (tidak ada kode Manim yang
     ditulis manual per episode).
  2. Render via CLI `python -m manim` pada 1080x1920 @ 24 fps.
  3. Regangkan/potong hasilnya ke durasi narasi yang tepat.
  4. Tempel chrome (brand, progress, footer) dari PNG transparan supaya
     identitas visual tetap sama dengan scene Pillow.

Kalau Manim tidak terpasang atau gagal render, fungsi mengembalikan None dan
pemanggil otomatis jatuh ke renderer Pillow. Pipeline tidak pernah mati karena
satu tool opsional.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

W, H, FPS = 1080, 1920, 24
BG = "#0a0e18"
ACCENT = {"hook": "#5eead4", "point": "#7dd3fc", "limit": "#fca5a5", "cta": "#a78bfa"}

SCENE_TEMPLATE = '''
from manim import *

BG = "__BG__"
ACCENT = "__ACCENT__"
SPEC = __SPEC__


class EpisodeScene(Scene):
    def construct(self):
        self.camera.background_color = BG
        kind = SPEC.get("type", "diagram")
        getattr(self, "do_" + kind, self.do_diagram)()

    # ---------- util ----------
    def label(self, text, size=34, color=WHITE, weight=MEDIUM):
        return Text(str(text), font="Sans", font_size=size, color=color, weight=weight)

    def box(self, title, sub="", width=7.4, height=1.15):
        r = RoundedRectangle(corner_radius=0.22, width=width, height=height,
                             stroke_color=ACCENT, stroke_width=2.5,
                             fill_color="#121a2b", fill_opacity=0.92)
        items = VGroup(self.label(title, 32, "#eef4ff", MEDIUM))
        if sub:
            items.add(self.label(sub, 22, "#9fb0c9"))
        items.arrange(DOWN, buff=0.12).move_to(r)
        return VGroup(r, items)

    # ---------- tipe ----------
    def do_diagram(self):
        nodes = SPEC.get("nodes", [])[:4]
        if not nodes:
            return self.do_card()
        boxes = VGroup(*[self.box(n.get("title", ""), n.get("sub", "")) for n in nodes])
        boxes.arrange(DOWN, buff=0.75).move_to(UP * 0.6)
        arrows = VGroup(*[
            Arrow(boxes[i].get_bottom(), boxes[i + 1].get_top(), buff=0.12,
                  stroke_color=ACCENT, stroke_width=5, max_tip_length_to_length_ratio=0.15)
            for i in range(len(boxes) - 1)])
        self.play(LaggedStart(*[FadeIn(b, shift=UP * 0.25) for b in boxes],
                              lag_ratio=0.55), run_time=__T_IN__)
        if arrows:
            self.play(LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.5),
                      run_time=__T_ARROW__)
        self.wait(__T_HOLD__)

    def do_steps(self):
        items = SPEC.get("items", [])[:4]
        rows = VGroup()
        for i, it in enumerate(items):
            title = it.get("title") if isinstance(it, dict) else str(it)
            r = RoundedRectangle(corner_radius=0.2, width=7.6, height=0.95,
                                 stroke_color="#243049",
                                 stroke_width=2, fill_color="#121a2b", fill_opacity=0.9)
            num = Circle(radius=0.28, fill_color=ACCENT, fill_opacity=0.95, stroke_width=0)
            nt = self.label(str(i + 1), 22, "#0a0e18", BOLD).move_to(num)
            tx = self.label(title, 28, "#eef4ff").next_to(num, RIGHT, buff=0.35)
            rows.add(VGroup(r, num, nt, tx))
        rows.arrange(DOWN, buff=0.28).move_to(UP * 0.4)
        for row in rows:
            self.play(FadeIn(row, shift=RIGHT * 0.3), run_time=__T_STEP__)
        self.wait(__T_HOLD__)

    def do_bars(self):
        items = SPEC.get("items", [])[:4]
        vals = [float(i.get("value", 1)) for i in items]
        mx = max(vals) if vals else 1.0
        group = VGroup()
        for it, v in zip(items, vals):
            lab = self.label(it.get("label", ""), 24, "#c6d4e8")
            bar = Rectangle(width=max(0.15, 6.2 * v / mx), height=0.42,
                            stroke_width=0, fill_color=ACCENT, fill_opacity=0.9)
            bar.align_to(lab, DOWN).shift(DOWN * 0.12 + RIGHT * 0.05)
            grp = VGroup(lab, bar)
            group.add(grp)
        group.arrange(DOWN, buff=0.62, aligned_edge=LEFT).move_to(UP * 0.4)
        for grp in group:
            self.play(grp[0].animate.set_opacity(1), GrowFromEdge(grp[1], LEFT), run_time=__T_STEP__)
        self.wait(__T_HOLD__)

    def do_compare(self):
        left, right = SPEC.get("left", {}), SPEC.get("right", {})
        cols = VGroup()
        for data, tint, mark in ((left, "#fca5a5", "x"), (right, "#86efac", "v")):
            r = RoundedRectangle(corner_radius=0.24, width=3.5, height=5.2,
                                 stroke_color=tint, stroke_width=2.5,
                                 fill_color="#121a2b", fill_opacity=0.92)
            title = self.label(data.get("title", ""), 30, "#eef4ff", BOLD)
            rows = VGroup(*[self.label("- " + str(x)[:22], 21, "#c6d4e8")
                            for x in (data.get("items") or [])[:4]])
            rows.arrange(DOWN, buff=0.18, aligned_edge=LEFT)
            inner = VGroup(title, rows).arrange(DOWN, buff=0.34).move_to(r)
            cols.add(VGroup(r, inner))
        cols.arrange(RIGHT, buff=0.3).move_to(UP * 0.3)
        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.2) for c in cols], lag_ratio=0.4),
                  run_time=__T_IN__)
        self.wait(__T_HOLD__)

    def do_stat(self):
        val = str(SPEC.get("value", "0"))
        m = re.match(r"^([^0-9\\-+]*)([-+]?\\d+(?:[.,]\\d+)?)(.*)$", val)
        if m:
            pre, num, suf = m.group(1), float(m.group(2).replace(",", ".")), m.group(3)
            dec = 1 if ("," in m.group(2) or "." in m.group(2)) else 0
            tracker = ValueTracker(0)
            fmt = ",." + str(dec) + "f"
            sep = "." if dec == 0 else ","
            txt = always_redraw(lambda: self.label(
                pre + format(tracker.get_value(), fmt).replace(",", sep) + suf,
                150, "#eef4ff", BOLD))
            self.add(txt)
            self.play(tracker.animate.set_value(num), run_time=__T_COUNT__)
        else:
            txt = self.label(val, 150, "#eef4ff", BOLD)
            self.play(FadeIn(txt, scale=0.85), run_time=__T_IN__)
        label = self.label(SPEC.get("label", ""), 40, "#c6d4e8").next_to(txt, DOWN, buff=0.5)
        self.play(FadeIn(label, shift=UP * 0.2), run_time=0.5)
        self.wait(__T_HOLD__)

    def do_card(self):
        title = self.label(SPEC.get("text", ""), 52, "#eef4ff", BOLD)
        self.play(FadeIn(title, shift=UP * 0.25), run_time=__T_IN__)
        self.wait(__T_HOLD__)


import re  # dibutuhkan do_stat
'''

ALLOWED = {"diagram", "steps", "bars", "compare", "stat", "card"}


def manim_available() -> bool:
    try:
        import manim  # noqa: F401

        return shutil.which(sys.executable) is not None
    except Exception:
        return False


def build_scene_file(spec: dict, out_py: Path, accent: str, duration: float) -> Path:
    """Terjemahkan spec beat jadi file scene Manim."""
    t_in = max(0.9, min(2.2, duration * 0.30))
    t_arrow = max(0.6, min(1.4, duration * 0.16))
    t_step = max(0.35, min(0.9, duration * 0.11))
    t_count = max(1.0, min(2.5, duration * 0.45))
    t_hold = max(0.2, duration - (t_in + t_arrow + 0.4))
    src = (SCENE_TEMPLATE
           .replace("__BG__", BG)
           .replace("__ACCENT__", accent)
           .replace("__SPEC__", json.dumps(spec, ensure_ascii=False))
           .replace("__T_IN__", str(round(t_in, 2)))
           .replace("__T_ARROW__", str(round(t_arrow, 2)))
           .replace("__T_STEP__", str(round(t_step, 2)))
           .replace("__T_COUNT__", str(round(t_count, 2)))
           .replace("__T_HOLD__", str(round(t_hold, 2))))
    out_py.write_text(src, encoding="utf-8")
    return out_py


def render_manim_clip(spec: dict, duration: float, out_mp4: Path, kind: str = "point",
                      quality: str = "l", timeout: int = 300) -> Path | None:
    """Render satu clip Manim. Return None kalau gagal (pemanggil fallback ke Pillow)."""
    if spec.get("type") not in ALLOWED:
        return None
    if not manim_available():
        print("  [warn] manim tidak terpasang; pakai renderer Pillow")
        return None

    work = Path(tempfile.mkdtemp(prefix="manim_"))
    try:
        scene_py = build_scene_file(spec, work / "scene.py", ACCENT.get(kind, "#7dd3fc"), duration)
        cmd = [sys.executable, "-m", "manim", f"-q{quality}", "-r", f"{W},{H}",
               "--fps", str(FPS), "--media_dir", str(work / "media"),
               "--disable_caching", str(scene_py), "EpisodeScene"]
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout)[-260:]
            print(f"  [warn] manim gagal: {tail}")
            return None
        found = sorted((work / "media").rglob("EpisodeScene.mp4"))
        if not found:
            print("  [warn] manim tidak menghasilkan file")
            return None
        clip = found[-1]
        # regangkan/potong ke durasi narasi yang tepat
        from .config import find_ffmpeg

        ff = find_ffmpeg()
        fit = subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(clip),
             "-vf", f"tpad=stop_mode=clone:stop_duration={max(0.0, duration):.2f},"
                    f"trim=0:{duration:.3f},setpts=PTS-STARTPTS,fps={FPS}",
             "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", str(out_mp4)],
            capture_output=True, text=True)
        if fit.returncode != 0:
            print(f"  [warn] penyesuaian durasi manim gagal: {fit.stderr[-160:]}")
            return None
        return out_mp4
    except subprocess.TimeoutExpired:
        print("  [warn] manim timeout")
        return None
    except Exception as e:
        print(f"  [warn] manim error: {str(e)[:120]}")
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    demo = {"type": "diagram", "nodes": [
        {"title": "Model besar", "sub": "100B+ parameter"},
        {"title": "Distilasi", "sub": "murid meniru guru"},
        {"title": "Kuantisasi 4-bit", "sub": "ukuran dibagi 4"}]}
    out = Path("/tmp/manim_demo.mp4")
    p = render_manim_clip(demo, 6.0, out)
    print("hasil:", p)
    if p:
        from .config import find_ffmpeg

        r = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", str(p)],
                           capture_output=True, text=True)
        print([ln.strip() for ln in r.stderr.splitlines()
               if "Duration" in ln or "Stream" in ln])
