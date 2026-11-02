"""Nara Studio: responsive, accessible single-file application shell.

All data is loaded through authenticated same-origin requests. No external font,
image, script or stylesheet is required. User/script content is always escaped.
"""
from pathlib import Path

PAGE = (Path(__file__).parent / "studio.html").read_text(encoding="utf-8")
