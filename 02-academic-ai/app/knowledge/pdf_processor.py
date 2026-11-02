from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)

OCR_MIN_CHARS = 100  # below this total, a PDF is treated as image-only
OCR_MAX_PAGES = 80  # CPU guard: larger scans must be split by the user
OCR_RENDER_SCALE = 2.0

_tesseract_path: str | None = None
_tesseract_probed = False
_ocr_lang: str | None = None


class PdfHasNoTextError(ValueError):
    """Raised when a PDF is image-only or has no extractable text."""


def tesseract_available() -> bool:
    """True when the `tesseract` binary is installed (result cached)."""
    global _tesseract_path, _tesseract_probed
    if not _tesseract_probed:
        _tesseract_path = shutil.which("tesseract")
        _tesseract_probed = True
    return _tesseract_path is not None


def _choose_ocr_lang() -> str:
    global _ocr_lang
    if _ocr_lang is not None:
        return _ocr_lang
    binary = _tesseract_path if tesseract_available() else None
    if binary is None:
        _ocr_lang = "eng"
        return _ocr_lang
    try:
        completed = subprocess.run(  # noqa: S603 - binary is the resolved tesseract path, args fixed
            [binary, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        langs = completed.stdout + completed.stderr
        _ocr_lang = "ind+eng" if "ind" in langs.split() else "eng"
    except Exception:
        _ocr_lang = "eng"
    return _ocr_lang


def _ocr_pages(pdf_path: Path) -> list[tuple[int, str]]:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise PdfHasNoTextError(
            "OCR butuh paket pypdfium2. Instal: pip install pypdfium2 pytesseract."
        ) from exc
    try:
        import pytesseract
    except ImportError as exc:
        raise PdfHasNoTextError(
            "OCR butuh paket pytesseract. Instal: pip install pytesseract."
        ) from exc

    document = pdfium.PdfDocument(pdf_path)
    page_count = len(document)
    if page_count > OCR_MAX_PAGES:
        raise PdfHasNoTextError(
            f"PDF hasil scan {page_count} halaman melebihi batas OCR {OCR_MAX_PAGES} halaman. "
            "Perkecil/split PDF lalu unggah ulang."
        )
    lang = _choose_ocr_lang()
    logger.info("[INFO] OCR %d halaman (%s)...", page_count, lang)
    pages: list[tuple[int, str]] = []
    for page_number, page in enumerate(document, start=1):
        bitmap = page.render(scale=OCR_RENDER_SCALE).to_pil()
        try:
            text = pytesseract.image_to_string(bitmap, lang=lang) or ""
        except Exception as exc:
            raise PdfHasNoTextError(f"OCR gagal di halaman {page_number}: {exc}") from exc
        pages.append((page_number, " ".join(text.split())))
    return pages


def _try_docling(pdf_path: Path) -> list[tuple[int, str]] | None:
    """Docling parse (layout+tables). None = unavailable/failed, caller falls back."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        return None
    try:
        document = DocumentConverter().convert(str(pdf_path)).document
    except Exception as exc:
        logger.warning("[WARN] Docling gagal (%s); fallback pypdf.", type(exc).__name__)
        return None
    by_page: dict[int, list[str]] = {}
    try:
        items = list(document.iterate_items())
    except Exception:
        return None
    for item, _level in items:
        text = getattr(item, "text", "") or ""
        if not text.strip():
            continue
        page_no = 1
        prov = getattr(item, "prov", None) or []
        if prov and getattr(prov[0], "page_no", None):
            page_no = int(prov[0].page_no)
        by_page.setdefault(page_no, []).append(" ".join(text.split()))
    if not by_page:
        return None
    logger.info("[INFO] PDF diparsing dengan Docling (%d halaman).", len(by_page))
    return [(page, " ".join(parts)) for page, parts in sorted(by_page.items())]


def extract_pdf_pages(pdf_path: Path, *, ocr: str = "auto") -> list[tuple[int, str]]:
    """Extract selectable text from a PDF, preserving 1-based page numbers.

    When the PDF looks image-only (selectable text below OCR_MIN_CHARS) and the
    `tesseract` binary is installed, pages are OCR-ed automatically. Pass
    ocr="never" to skip the OCR fallback.
    """
    docling_pages = _try_docling(pdf_path)
    if docling_pages is not None:
        return docling_pages
    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        try:
            decrypted = reader.decrypt("")
        except Exception as exc:
            raise ValueError("PDF terenkripsi dan tidak bisa dibuka.") from exc
        if not decrypted:
            raise ValueError("PDF terenkripsi dan tidak bisa dibuka tanpa password.")

    pages: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append((page_number, " ".join(text.split())))

    total_chars = sum(len(text) for _, text in pages)
    if total_chars >= OCR_MIN_CHARS:
        return pages
    if ocr == "never" or not tesseract_available():
        raise PdfHasNoTextError(
            "Tidak ditemukan teks yang bisa diekstrak (kemungkinan PDF hasil scan). "
            "Instal Tesseract OCR gratis lalu unggah ulang: winget install --id UB-Mannheim.TesseractOCR."
        )
    ocr_pages = _ocr_pages(pdf_path)
    if sum(len(text) for _, text in ocr_pages) < OCR_MIN_CHARS:
        raise PdfHasNoTextError(
            "Hasil OCR kosong. Pastikan hasil scan terbaca jelas lalu unggah ulang."
        )
    logger.info("[INFO] OCR selesai: %d halaman teks.", len(ocr_pages))
    return ocr_pages
