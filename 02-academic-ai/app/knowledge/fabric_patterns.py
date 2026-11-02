"""Fabric-inspired prompt patterns (ours, license-safe). Rendered with {variables}."""

from __future__ import annotations

from pathlib import Path

PATTERNS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "academic"


def list_patterns() -> list[str]:
    if not PATTERNS_DIR.is_dir():
        return []
    return sorted(path.stem for path in PATTERNS_DIR.glob("*.md"))


def render(name: str, **variables: str) -> str:
    path = PATTERNS_DIR / f"{name}.md"
    if not path.is_file():
        raise ValueError(f"Pola prompt tidak dikenal: {name}. Ada: {', '.join(list_patterns())}.")
    try:
        return path.read_text(encoding="utf-8").format(**variables)
    except KeyError as exc:
        raise ValueError(f"Pola {name} butuh variabel {exc}.") from exc
