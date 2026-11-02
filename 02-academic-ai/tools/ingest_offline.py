"""Ingest PDF ke database tanpa provider embedding (offline).

Chunk + teks disimpan penuh; embedding diisi placeholder nol dengan model
"pending-backfill" (skor cosine selalu 0.0, aman diabaikan). Mode RAG tree
langsung jalan; mode vector aktif setelah tools/backfill_embeddings.py
dijalankan di mesin yang punya provider (9Router/Ollama).

Contoh:
    python tools/ingest_offline.py --source uploads --data /tmp/databuild/data
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import shutil
import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Subject  # noqa: E402
from app.database.database import Database  # noqa: E402
from app.knowledge.chunker import chunk_pages  # noqa: E402
from app.knowledge.pdf_processor import extract_pdf_pages  # noqa: E402
from app.knowledge.vector_store import LocalVectorStore  # noqa: E402
from app.config import _load_yaml  # noqa: E402

PENDING_MODEL = "pending-backfill"
PLACEHOLDER_VECTOR = [0.0] * 8

# Awalan nama file -> kode matkul (sesuaikan bila pola berubah).
PREFIX_MAP = {
    "0308027905": "ILKOM",
    "0314129101": "KAP",
    "0320170449": "PR",
    "0322068401": "DJ",
    "0327026502": "BING",
    "03414081101": "PA",
}


def subject_for(filename: str) -> str | None:
    upper = filename.upper()
    if "PANCASILA" in upper:
        return "PP"
    for prefix, code in PREFIX_MAP.items():
        if upper.startswith(prefix):
            return code
    return None


def safe_filename(original_name: str) -> str:
    basename = original_name.replace("\\", "/").split("/")[-1].strip()
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", basename).strip(" .")
    if not safe:
        safe = "materi.pdf"
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    return safe


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


async def ingest(source: Path, data_dir: Path) -> dict[str, int]:
    config = _load_yaml(PROJECT_ROOT / "config" / "subjects.yaml")
    subjects = {
        code: Subject(code, info["name"], info["directory"])
        for code, info in config["subjects"].items()
    }
    database_path = data_dir / "academic_ai.db"
    if database_path.exists():
        database_path.unlink()
    vector_file = data_dir / "vectorstore" / "vectors.sqlite"
    if vector_file.exists():
        vector_file.unlink()
    database = Database(database_path)
    await database.initialize(subjects)
    await database.upsert_user(0, "local-web", "Local Web")

    counts: dict[str, int] = {}
    seen_hashes: set[str] = set()
    files = sorted(source.glob("*.pdf"))
    if not files:
        raise SystemExit(f"Tidak ada PDF di {source}")
    for pdf in files:
        code = subject_for(pdf.name)
        if code is None:
            print(f"SKIP (matkul tak dikenal): {pdf.name}")
            continue
        digest = sha256_file(pdf)
        if digest in seen_hashes:
            print(f"SKIP (duplikat isi): {pdf.name}")
            continue
        seen_hashes.add(digest)
        subject = subjects[code]
        document_id = uuid4().hex
        subject_dir = data_dir / "knowledge" / subject.directory
        subject_dir.mkdir(parents=True, exist_ok=True)
        stored_file = subject_dir / f"{document_id}_{safe_filename(pdf.name)}"
        shutil.copyfile(pdf, stored_file)
        pages = await asyncio.to_thread(extract_pdf_pages, stored_file)
        text_chunks = chunk_pages(
            document_id=document_id, document_name=pdf.name, pages=pages
        )
        if not text_chunks:
            stored_file.unlink(missing_ok=True)
            print(f"SKIP (teks kosong): {pdf.name}")
            continue
        chunk_rows = [
            {
                "chunk_id": chunk.chunk_id,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "embedding": PLACEHOLDER_VECTOR,
            }
            for chunk in text_chunks
        ]
        await database.add_document_and_chunks(
            {
                "id": document_id,
                "subject_code": code,
                "original_name": pdf.name,
                "stored_path": f"data/knowledge/{subject.directory}/{stored_file.name}",
                "sha256": digest,
                "embedding_model": PENDING_MODEL,
                "file_size_bytes": stored_file.stat().st_size,
                "page_count": len(pages),
                "uploaded_by": 0,
            },
            chunk_rows,
        )
        counts[code] = counts.get(code, 0) + 1
        print(f"OK {code}: {pdf.name} ({len(pages)} hlm, {len(chunk_rows)} chunk)")

    store = LocalVectorStore(database, vector_file)
    total = await store.sync_from_database()
    print(f"CHUNKS_TOTAL={total}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDF offline (tanpa embedding).")
    parser.add_argument("--source", required=True, help="Folder berisi PDF.")
    parser.add_argument("--data", required=True, help="Folder data tujuan (akan dibuat).")
    args = parser.parse_args()
    source = Path(args.source).expanduser()
    data_dir = Path(args.data).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    counts = asyncio.run(ingest(source, data_dir))
    print("DONE", counts)


if __name__ == "__main__":
    main()
