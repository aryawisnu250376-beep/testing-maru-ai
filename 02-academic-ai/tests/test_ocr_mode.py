from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.knowledge import pdf_processor
from app.knowledge.pdf_processor import PdfHasNoTextError, extract_pdf_pages
from app.settings_update import apply_answer_preset, detect_answer_preset

LONG_TEXT = (
    "hasil ocr dua kalimat penuh agar total karakter melewati ambang minimum seratus. "
    "Kalimat kedua memastikan ambang OCR_MIN_CHARS terlampaui dengan aman. "
)


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakeReader:
    is_encrypted = False

    def __init__(self, texts: list[str]) -> None:
        self.pages = [_FakePage(text) for text in texts]


def _reader_with(*texts: str):
    return lambda _path: _FakeReader(list(texts))


def test_selectable_text_skips_ocr(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pdf_processor, "PdfReader", _reader_with(LONG_TEXT))
    called = []
    monkeypatch.setattr(pdf_processor, "_ocr_pages", lambda _p: called.append(1))
    pages = extract_pdf_pages(tmp_path / "x.pdf")
    assert pages[0][1].startswith("hasil ocr")
    assert called == []


def test_image_only_pdf_without_tesseract_raises_helpful(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pdf_processor, "PdfReader", _reader_with("", ""))
    monkeypatch.setattr(pdf_processor, "tesseract_available", lambda: False)
    with pytest.raises(PdfHasNoTextError, match="Tesseract"):
        extract_pdf_pages(tmp_path / "scan.pdf")


def test_image_only_pdf_with_tesseract_uses_ocr(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pdf_processor, "PdfReader", _reader_with(""))
    monkeypatch.setattr(pdf_processor, "tesseract_available", lambda: True)
    monkeypatch.setattr(pdf_processor, "_ocr_pages", lambda _p: [(1, LONG_TEXT)])
    assert extract_pdf_pages(tmp_path / "scan.pdf") == [(1, LONG_TEXT)]


def test_empty_ocr_result_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pdf_processor, "PdfReader", _reader_with(""))
    monkeypatch.setattr(pdf_processor, "tesseract_available", lambda: True)
    monkeypatch.setattr(pdf_processor, "_ocr_pages", lambda _p: [(1, "")])
    with pytest.raises(PdfHasNoTextError, match="kosong"):
        extract_pdf_pages(tmp_path / "scan.pdf")


def test_ocr_never_skips_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pdf_processor, "PdfReader", _reader_with(""))
    monkeypatch.setattr(pdf_processor, "tesseract_available", lambda: True)
    called = []
    monkeypatch.setattr(pdf_processor, "_ocr_pages", lambda _p: called.append(1))
    with pytest.raises(PdfHasNoTextError):
        extract_pdf_pages(tmp_path / "scan.pdf", ocr="never")
    assert called == []


def test_tesseract_available_caches_which(monkeypatch) -> None:
    monkeypatch.setattr(pdf_processor, "_tesseract_probed", False)
    monkeypatch.setattr(pdf_processor, "_tesseract_path", None)
    calls = []
    monkeypatch.setattr(pdf_processor.shutil, "which", lambda name: calls.append(name) or None)
    assert pdf_processor.tesseract_available() is False
    assert pdf_processor.tesseract_available() is False
    assert calls == ["tesseract"]
    monkeypatch.setattr(pdf_processor, "_tesseract_probed", False)
    monkeypatch.setattr(pdf_processor, "_tesseract_path", None)


def _preset_settings(env_file: Path) -> SimpleNamespace:
    return SimpleNamespace(
        env_file=env_file,
        subjects={},
        models={},
        rag_top_k=6,
        max_output_tokens=1500,
    )


def test_detect_answer_preset(tmp_path: Path) -> None:
    assert detect_answer_preset(_preset_settings(tmp_path / ".env")) == "seimbang"
    custom = _preset_settings(tmp_path / ".env")
    custom.rag_top_k = 7
    assert detect_answer_preset(custom) == "kustom"


def test_apply_answer_preset_persists(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("RAG_TOP_K=6\n", encoding="utf-8")
    settings = _preset_settings(env_file)
    report = apply_answer_preset(settings, "mendalam")
    assert settings.rag_top_k == 10
    assert settings.max_output_tokens == 2500
    assert report["needs_restart"] == []
    assert "RAG_TOP_K=10" in env_file.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="tidak dikenal"):
        apply_answer_preset(settings, "turbo")


def test_n8n_example_is_importable() -> None:
    path = Path(__file__).resolve().parents[1] / "n8n" / "academic_webhook.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    types = [node["type"] for node in workflow["nodes"]]
    assert "n8n-nodes-base.webhook" in types
    assert "n8n-nodes-base.httpRequest" in types
    assert "n8n-nodes-base.respondToWebhook" in types
    assert set(workflow["connections"]) == {"Webhook", "Tanya Academic AI"}
