from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.knowledge.vector_store import RetrievedChunk
from app.research.researcher import Researcher, build_query_variants


def test_build_query_variants_simple_and_dedup() -> None:
    assert build_query_variants("demokrasi", 3) == ["demokrasi"]
    assert build_query_variants("   ", 3) == ["   "]
    variants = build_query_variants("Apa itu demokrasi?", 3)
    assert variants[0] == "Apa itu demokrasi?"
    assert variants[1] == "demokrasi"
    assert len(variants) == 2


def test_build_query_variants_long_text_adds_sentences_and_caps() -> None:
    question = (
        "Jelaskan konsep demokrasi terpimpin di Indonesia secara lengkap dan terperinci. "
        "Bagaimana pelaksanaannya pada masa Orde Lama dan apa dampaknya bagi sistem politik?"
    )
    variants = build_query_variants(question, 3)
    assert len(variants) == 3
    assert variants[0] == " ".join(question.split())
    assert len({variant.lower() for variant in variants}) == 3
    assert build_query_variants(question, 1) == [" ".join(question.split())]


def test_find_evidence_merges_dedups_batches_and_scopes() -> None:
    async def scenario() -> None:
        calls: dict[str, list[str]] = {}

        class FakeEmbeddings:
            async def embed_texts(self, texts):
                calls["texts"] = list(texts)
                return [[float(len(text)), 0.0] for text in texts]

        class FakeStore:
            async def search(self, subject_code, vector, *, top_k, min_score, embedding_model):
                tag = "long" if vector[0] > 20 else "short"
                high = 0.9 if tag == "long" else 0.5
                shared = 0.9 if tag == "long" else 0.95
                return [
                    RetrievedChunk(f"{tag}-a", subject_code, "D.pdf", 1, "c", high),
                    RetrievedChunk("shared", subject_code, "D.pdf", 2, "c", shared),
                    RetrievedChunk("other", "XX", "X.pdf", 1, "c", 1.0),
                ]

        class FakeDB:
            async def get_embedding_models_for_subject(self, code):
                return {"m"}

        settings = SimpleNamespace(
            embedding_model="m",
            rag_top_k=2,
            rag_min_score=0.0,
            rag_query_variants=3,
        )
        researcher = Researcher(settings, FakeDB(), FakeEmbeddings(), FakeStore())
        chunks = await researcher.find_evidence("PP", "Apa itu demokrasi terpimpin?")
        assert len(calls["texts"]) == 2  # original + keywords in one batched call
        assert researcher.last_query_variants == calls["texts"]
        by_id = {chunk.chunk_id: chunk for chunk in chunks}
        assert set(by_id) == {"long-a", "short-a", "shared"}
        assert by_id["shared"].score == 0.95  # best score wins the merge
        assert len(chunks) <= 2 + 2  # rag_top_k + 2 per extra variant

    asyncio.run(scenario())
