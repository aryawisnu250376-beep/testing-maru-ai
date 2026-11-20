"""Nara Studio: responsive, accessible single-file application shell.

Operational data uses authenticated same-origin requests. Optional CDN scripts
are loaded only for the 3D office; the 2D roster is independently available.
"""
from pathlib import Path

PAGE = (Path(__file__).parent / "studio.html").read_text(encoding="utf-8")
