"""Hermes mandiri: membaca bahan, menjalankan skill, menulis draf ke antrean.

Tidak pernah mengubah status persetujuan dan tidak pernah memanggil Ootto.
Jika Hermes Agent eksternal tersedia, skill yang sama bisa dipasang di sana.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from . import queue4, skills4
from .config import ROOT


def run_file(path: str | Path, topic: str = "") -> dict:
    path = Path(path)
    if not path.is_file():
        raise ValueError("Bahan tidak ditemukan: " + str(path))
    result = skills4.run_pipeline(path, topic)
    content_id = "k-" + uuid.uuid4().hex[:10]
    out = ROOT / "keluar" / content_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "ringkasan.json").write_text(
        json.dumps(result["summary"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "naskah.json").write_text(
        json.dumps(result["script"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "qc.json").write_text(
        json.dumps(result["qc"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sumber = out / "sumber.md"
    sumber.write_text(
        f"# Sumber\n\n- Bahan: {path.name}\n- Diakses: {queue4.now()}\n- Setiap klaim harus diperiksa terhadap bahan asli.\n",
        encoding="utf-8",
    )
    script = result["script"]
    naskah_txt = (
        script.get("hook", "")
        + "\n\n"
        + "\n".join(b.get("narration", "") for b in script.get("beats", []))
    )
    queue4.create(
        content_id,
        topic or path.stem,
        naskah=naskah_txt,
        caption=script.get("caption", ""),
        usulan_jam=result["schedule"]["waktu"],
        alasan_jam=result["schedule"]["alasan"],
        sumber=[{"title": path.name, "url": str(path)}],
        episode_id="",
        actor="hermes",
    )
    queue4.transition(
        content_id,
        "MENUNGGU",
        "hermes",
        "Draf siap ditinjau pemilik",
        qc_passed=not result["needs_human"],
    )
    return {
        "id": content_id,
        "item": queue4.get(content_id),
        "needs_human": result["needs_human"],
        "revision_rounds": result["revision_rounds"],
        "keluar": str(out),
    }
