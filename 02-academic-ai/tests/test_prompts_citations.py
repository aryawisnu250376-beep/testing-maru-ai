from __future__ import annotations

import asyncio
import json

from app.agents.base import parse_agent_draft
from app.knowledge.citations import inline_citations, inline_citations_have_sources
from app.manager.manager import AcademicManager
from app.manager.verifier import parse_verification_result

SOURCES = [
    {"document": "Modul 1.pdf", "page": 3},
    {"document": "Bab 2, Pengantar.pdf", "page": 7},
]


def test_inline_citations_extract_doc_page_pairs() -> None:
    text = "Konsep A jelas [Modul 1.pdf, h.3]. Detail ada di [Bab 2, Pengantar.pdf, h.7]."
    assert inline_citations(text) == {("Modul 1.pdf", 3), ("Bab 2, Pengantar.pdf", 7)}
    assert inline_citations("Tanpa penanda sama sekali.") == set()
    assert inline_citations("Kurung biasa [bukan sitasi] diabaikan.") == set()


def test_inline_citations_subset_validation() -> None:
    assert inline_citations_have_sources("Lihat [Modul 1.pdf, h.3].", SOURCES)
    assert not inline_citations_have_sources("Lihat [Modul 1.pdf, h.9].", SOURCES)
    assert not inline_citations_have_sources("Lihat [Lain.pdf, h.3].", SOURCES)
    assert inline_citations_have_sources("Tanpa penanda lolos vakum.", SOURCES)


def _draft_raw(answer: str) -> str:
    return json.dumps(
        {
            "answer": answer,
            "sources": [
                {"document": "Modul 1.pdf", "page": 3},
                {"document": "Bab 2, Pengantar.pdf", "page": 7},
            ],
            "confidence": 0.8,
        }
    )


def test_agent_draft_rejects_markers_outside_retrieval() -> None:
    allowed = {("Modul 1.pdf", 3), ("Bab 2, Pengantar.pdf", 7)}
    good = parse_agent_draft(
        _draft_raw("Konsep inti [Modul 1.pdf, h.3]."),
        agent_name="PP_AGENT_A",
        slot="A",
        model_id="m",
        allowed_sources=allowed,
    )
    assert good.available
    bad = parse_agent_draft(
        _draft_raw("Klaim aneh [Modul 9.pdf, h.1]."),
        agent_name="PP_AGENT_A",
        slot="A",
        model_id="m",
        allowed_sources=allowed,
    )
    assert not bad.available
    assert bad.error == "citation_outside_retrieval"


def test_verifier_rejects_manager_markers_outside_retrieval() -> None:
    allowed = {("Modul 1.pdf", 3)}

    def raw(answer: str) -> str:
        return json.dumps(
            {
                "decision": "APPROVED",
                "confidence": 0.9,
                "reason": "ok",
                "revision_instruction": None,
                "answer": answer,
                "sources": [{"document": "Modul 1.pdf", "page": 3}],
            }
        )

    good = parse_verification_result(
        raw("Final [Modul 1.pdf, h.3]."), allowed_sources=allowed, model_id="m"
    )
    assert good.decision == "APPROVED"
    bad = parse_verification_result(
        raw("Final [Modul X.pdf, h.3]."), allowed_sources=allowed, model_id="m"
    )
    assert bad.decision == "UNVERIFIED"
    assert "penanda sitasi" in bad.reason


def test_verifier_ignores_coverage_extra_field() -> None:
    payload = json.dumps(
        {
            "decision": "REVISION_REQUIRED",
            "confidence": 0.4,
            "reason": "kurang",
            "revision_instruction": "tambah sub-poin B",
            "answer": "",
            "sources": [],
            "coverage": [
                {"point": "definisi", "status": "covered"},
                {"point": "contoh", "status": "missing"},
            ],
        }
    )
    result = parse_verification_result(payload, allowed_sources=set(), model_id="m")
    assert result.decision == "REVISION_REQUIRED"
    assert "sub-poin B" in (result.revision_instruction or "")


def test_transcript_summarizer_falls_back_to_next_model() -> None:
    class SettingsStub:
        manager_model = "primary-model"
        max_context_chars = 6000
        max_output_tokens = 1200

        @staticmethod
        def fallback_models_for(role: str) -> list:
            return ["fallback-model"]

    class FlakyProvider:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def chat(self, model, messages, **kwargs):
            self.calls.append(model)
            if model == "primary-model":
                raise RuntimeError("primary down")
            return "Ringkasan via fallback."

    manager = AcademicManager.__new__(AcademicManager)
    manager.settings = SettingsStub()
    manager.provider = FlakyProvider()
    result = asyncio.run(
        manager.summarize_source_text(
            source_text="isi transkrip",
            source_name="Video (x)",
            source_url="https://example.test/x",
        )
    )
    assert result.status == "UNVERIFIED"
    assert result.manager_model == "fallback-model"
    assert manager.provider.calls == ["primary-model", "fallback-model"]
