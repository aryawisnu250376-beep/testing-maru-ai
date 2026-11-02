"""Demo learning loop dengan data SINTETIS di DB terpisah.

Tujuan: menunjukkan bagaimana metrik diterjemahkan jadi "pola pemenang" yang
disuntik ke prompt. Data di sini karangan — DB asli (data/pipeline.db) tidak
disentuh.

    python scripts/demo_learning.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import db, learning  # noqa: E402


def make_script(i: int, question_hook: bool) -> dict:
    hook = "Kenapa AI bisa jalan di HP?" if question_hook else "AI sekarang jalan di HP."
    return {
        "title": f"demo {i}",
        "hook": hook,
        "theme": "on_device",
        "format": "satu_konsep",
        "beats": [
            {"kind": "hook", "narration": hook, "body": "x", "source_refs": [],
             "visual": {"type": "card", "props": {}}},
            {"kind": "point", "narration": "a", "body": "y", "source_refs": [0],
             "visual": ({"type": "diagram", "props": {"nodes": [{"title": "a"}, {"title": "b"}]}}
                        if question_hook else {"type": "card", "props": {}})},
            {"kind": "limit", "narration": "b", "body": "z", "source_refs": [0],
             "visual": {"type": "steps", "props": {"items": [{"title": "a"}, {"title": "b"}]}}},
            {"kind": "cta", "narration": "c", "body": "w", "source_refs": [],
             "visual": {"type": "quote", "props": {"text": "t"}}},
        ],
        "caption": "c", "hashtags": ["#AI"],
        "sources": [{"title": "s", "url": "https://example.com/a"}],
    }


def main() -> None:
    tmp = Path(tempfile.mkdtemp()) / "demo.db"
    db.set_db_path(tmp)
    db.init()

    # 9 video: separuh pakai hook pertanyaan + diagram, separuh tidak.
    # Retensi sengaja dibuat berbeda supaya polanya kelihatan.
    for i in range(9):
        q = i % 2 == 0
        ep = f"ex-{i:02d}"
        db.save_episode(ep, "published", {"theme": "on_device"}, make_script(i, q),
                        {"duration_sec": 40})
        retention = 0.55 if q else 0.32
        db.save_metrics(ep, {"views": 1000 + i * 300, "avg_watch": retention * 40,
                             "likes": 40 + i, "comments": 4, "shares": 2})

    r = learning.report()
    print(f"video dengan metrik: {r['n']}  |  cukup untuk menyimpulkan: {r['ready']}")
    print(f"retensi rata-rata: {r['overall']['avg_retention']:.0%}")

    print("\nper tipe hook:")
    for g in r["dimensions"]["hook_type"]:
        mark = "✓" if g["confident"] else "·"
        print(f"  {mark} {g['value']:12} n={g['n']:2}  retensi {g['avg_retention']:.0%}  "
              f"views {g['avg_views']}")

    print("\nper visual utama:")
    for g in r["dimensions"]["primary_visual"]:
        mark = "✓" if g["confident"] else "·"
        print(f"  {mark} {g['value']:12} n={g['n']:2}  retensi {g['avg_retention']:.0%}")

    print("\ninsight:")
    for i in r["insights"]:
        print(f"  - {i}")

    print("\nblok yang akan disuntik ke prompt LLM:")
    print("-" * 66)
    print(learning.prompt_block() or "(kosong — data belum cukup)")
    print("-" * 66)
    print("\nCatatan: ini data sintetis. Angka asli muncul setelah kamu mencatat")
    print("metrik video sendiri lewat: python -m src.cli metrics <ep> --views ...")


if __name__ == "__main__":
    main()
