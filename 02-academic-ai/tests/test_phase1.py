from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

from app.auth import is_authorized
from app.config import Subject
from app.database.database import Database
from app.knowledge.chunker import chunk_pages
from app.knowledge.embeddings import EmbeddingService
from app.knowledge.vector_store import LocalVectorStore, RetrievedChunk, cosine_similarity
from app.manager.manager import AcademicManager, validate_quiz_answer
from app.manager.verifier import parse_verification_result
from app.research.librarian import Librarian
from app.services.material_service import MaterialService

SUBJECTS = {
    "PP": Subject("PP", "Pendidikan Pancasila", "pp", "Pancasila"),
    "KAP": Subject("KAP", "Komunikasi Antarpribadi", "kap", "komunikasi interpersonal"),
}


class FakeSettings:
    project_root = Path(".")
    embedding_model = "test-embedding-model"
    manager_model = "test-manager-model"
    rag_top_k = 5
    rag_min_score = 0.1
    rag_query_variants = 3
    max_output_tokens = 500
    max_revision_rounds = 2
    max_context_chars = 60000
    subjects = SUBJECTS
    models: ClassVar[dict[str, Any]] = {
        "subjects": {
            "KAP": {
                "agent_a": "test-agent-a",
                "agent_b": "test-agent-b",
                "agent_c": "test-agent-c",
            },
            "PP": {
                "agent_a": "test-agent-a",
                "agent_b": "test-agent-b",
                "agent_c": "test-agent-c",
            },
        }
    }

    @staticmethod
    def model_for(subject_code: str, agent: str = "agent_a") -> str:
        return FakeSettings.models["subjects"][subject_code][agent]

    @staticmethod
    def fallback_models_for(role: str) -> list[str]:
        return []


class FakeProvider:
    def __init__(self, manager_decisions: list[str] | None = None) -> None:
        self.manager_decisions = manager_decisions or ["APPROVED"]
        self.manager_calls = 0
        self.agent_prompts: dict[str, list[dict[str, object]]] = {"A": [], "B": [], "C": []}
        self.manager_payloads: list[dict[str, object]] = []

    async def embed(self, model, texts):
        assert model == "test-embedding-model"
        return [[1.0, 0.0] for _ in texts]

    async def chat(self, model, messages, **kwargs):
        if model == "test-manager-model":
            payload = json.loads(messages[-1]["content"])
            self.manager_payloads.append(payload)
            decision_index = min(self.manager_calls, len(self.manager_decisions) - 1)
            decision = self.manager_decisions[decision_index]
            self.manager_calls += 1
            if decision == "REVISION_REQUIRED":
                return json.dumps(
                    {
                        "decision": decision,
                        "confidence": 0.5,
                        "reason": "Sumber perlu dicocokkan ulang.",
                        "revision_instruction": "Periksa kembali definisi pada cuplikan halaman.",
                        "answer": "",
                        "sources": [],
                    }
                )
            if decision == "APPROVED":
                return json.dumps(
                    {
                        "decision": decision,
                        "confidence": 0.97,
                        "reason": "Dua draft konsisten dengan cuplikan materi.",
                        "revision_instruction": None,
                        "answer": "Self-disclosure adalah keterbukaan diri yang dijelaskan dalam materi.",
                        "sources": [{"document": "KAP_Bab_2.pdf", "page": 14}],
                    }
                )
            return json.dumps(
                {
                    "decision": "UNVERIFIED",
                    "confidence": 0.2,
                    "reason": "Bukti belum cukup.",
                    "revision_instruction": None,
                    "answer": "",
                    "sources": [],
                }
            )

        slot = {"test-agent-a": "A", "test-agent-b": "B", "test-agent-c": "C"}[model]
        payload = json.loads(messages[-1]["content"])
        self.agent_prompts[slot].append(payload)
        return json.dumps(
            {
                "answer": f"Draft independen agent {slot}.",
                "sources": [{"document": "KAP_Bab_2.pdf", "page": 14}],
                "confidence": 0.8,
            }
        )

    async def list_models(self):
        return ["test-agent-a", "test-agent-b", "test-agent-c", "test-manager-model"]

    async def list_embedding_models(self):
        return ["test-embedding-model"]

    async def close(self):
        return None


def _document_record(
    document_id: str, subject_code: str, name: str, stored_path: str, uploaded_by: int
):
    return {
        "id": document_id,
        "subject_code": subject_code,
        "original_name": name,
        "stored_path": stored_path,
        "sha256": f"hash-{document_id}",
        "embedding_model": "test-embedding-model",
        "file_size_bytes": 100,
        "page_count": 20,
        "uploaded_by": uploaded_by,
    }


def _chunk_record(chunk_id: str, page: int, content: str, vector: list[float]):
    return {
        "chunk_id": chunk_id,
        "page_number": page,
        "chunk_index": 0,
        "content": content,
        "embedding": vector,
    }


def test_allowlist_denies_unknown_user() -> None:
    assert is_authorized(123, frozenset({123}))
    assert not is_authorized(456, frozenset({123}))
    assert not is_authorized(None, frozenset({123}))
    assert not is_authorized(123, frozenset())


def test_chunk_ids_keep_pdf_page_metadata() -> None:
    chunks = chunk_pages(
        document_id="doc-1",
        document_name="KAP_Bab_2.pdf",
        pages=[(14, "Self-disclosure adalah proses membuka informasi pribadi kepada orang lain.")],
        max_chars=100,
        overlap_chars=10,
    )
    assert chunks
    assert all(chunk.page_number == 14 for chunk in chunks)
    assert all(chunk.chunk_id.startswith("doc-1:p14:c") for chunk in chunks)


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0


def test_legacy_phase1_parser_never_marks_unverified_response_as_approved() -> None:
    from app.manager.manager import parse_model_result

    result = parse_model_result(
        '{"status":"ANSWERED_FROM_MATERIAL","answer":"Contoh jawaban.",'
        '"sources":[{"document":"KAP_Bab_2.pdf","page":99}],"confidence":0.9}',
        allowed_sources={("KAP_Bab_2.pdf", 14)},
        model_id="test-model",
    )
    assert result.status == "UNVERIFIED"
    assert result.sources == []

    legacy_answer = parse_model_result(
        json.dumps(
            {
                "status": "ANSWERED_FROM_MATERIAL",
                "answer": "Konsep dijelaskan pada halaman 14.",
                "sources": [{"document": "KAP_Bab_2.pdf", "page": 14}],
                "confidence": 0.9,
            }
        ),
        allowed_sources={("KAP_Bab_2.pdf", 14)},
        model_id="test-model",
    )
    assert legacy_answer.status == "UNVERIFIED"


def test_verifier_rejects_fabricated_page_and_requires_sources() -> None:
    fabricated = parse_verification_result(
        json.dumps(
            {
                "decision": "APPROVED",
                "confidence": 0.9,
                "reason": "Approved",
                "revision_instruction": None,
                "answer": "Jawaban",
                "sources": [{"document": "KAP_Bab_2.pdf", "page": 99}],
            }
        ),
        allowed_sources={("KAP_Bab_2.pdf", 14)},
        model_id="manager",
    )
    assert fabricated.decision == "UNVERIFIED"
    missing_sources = parse_verification_result(
        json.dumps(
            {
                "decision": "APPROVED",
                "confidence": 0.9,
                "reason": "Approved",
                "revision_instruction": None,
                "answer": "Jawaban",
                "sources": [],
            }
        ),
        allowed_sources={("KAP_Bab_2.pdf", 14)},
        model_id="manager",
    )
    assert missing_sources.decision == "UNVERIFIED"
    body_claim = parse_verification_result(
        json.dumps(
            {
                "decision": "APPROVED",
                "confidence": 0.9,
                "reason": "Approved",
                "revision_instruction": None,
                "answer": "Konsep ini dijelaskan pada halaman 99.",
                "sources": [{"document": "KAP_Bab_2.pdf", "page": 14}],
            }
        ),
        allowed_sources={("KAP_Bab_2.pdf", 14)},
        model_id="manager",
    )
    assert body_claim.decision == "UNVERIFIED"


def test_persistent_vector_index_subject_filter_and_reopen(tmp_path) -> None:
    async def scenario() -> None:
        database = Database(tmp_path / "academic_ai.db")
        await database.initialize(SUBJECTS)
        await database.upsert_user(123, "student", "Student")
        await database.add_document_and_chunks(
            _document_record("doc-kap-1", "KAP", "Materi.pdf", "data/knowledge/kap/kap.pdf", 123),
            [_chunk_record("doc-kap-1:p14:c0", 14, "Materi komunikasi antarpribadi.", [1.0, 0.0])],
        )
        await database.add_document_and_chunks(
            _document_record("doc-pp-1", "PP", "Materi.pdf", "data/knowledge/pp/pp.pdf", 123),
            [_chunk_record("doc-pp-1:p1:c0", 1, "Materi Pendidikan Pancasila.", [0.0, 1.0])],
        )
        index_path = tmp_path / "data" / "vectorstore" / "vectors.sqlite"
        store = LocalVectorStore(database, index_path)
        assert await store.sync_from_database(set(SUBJECTS)) == 2
        kap_results = await store.search(
            "KAP", [1.0, 0.0], top_k=5, min_score=0.5, embedding_model="test-embedding-model"
        )
        pp_results = await store.search(
            "PP", [1.0, 0.0], top_k=5, min_score=0.5, embedding_model="test-embedding-model"
        )
        assert [item.subject_code for item in kap_results] == ["KAP"]
        assert [item.document_name for item in kap_results] == ["Materi.pdf"]
        assert pp_results == []

        reopened = LocalVectorStore(database, index_path)
        reopened_results = await reopened.search(
            "KAP", [1.0, 0.0], top_k=5, min_score=0.5, embedding_model="test-embedding-model"
        )
        assert reopened_results == kap_results

    asyncio.run(scenario())


def test_librarian_uses_database_as_authority_and_filters_subject(tmp_path) -> None:
    async def scenario() -> None:
        database = Database(tmp_path / "academic_ai.db")
        await database.initialize(SUBJECTS)
        await database.upsert_user(123, "student", "Student")
        await database.add_document_and_chunks(
            _document_record("doc-kap", "KAP", "KAP_Bab_2.pdf", "data/knowledge/kap/kap.pdf", 123),
            [_chunk_record("doc-kap:p14:c0", 14, "Teks kanonis halaman 14.", [1.0, 0.0])],
        )
        librarian = Librarian(database)
        wrong_subject = RetrievedChunk("doc-kap:p14:c0", "PP", "KAP_Bab_2.pdf", 14, "spoof", 1.0)
        wrong_page = RetrievedChunk("doc-kap:p14:c0", "KAP", "KAP_Bab_2.pdf", 99, "spoof", 1.0)
        valid = RetrievedChunk("doc-kap:p14:c0", "KAP", "KAP_Bab_2.pdf", 14, "spoof", 0.9)
        assert (
            await librarian.validate_evidence("PP", "test-embedding-model", [wrong_subject]) == []
        )
        assert await librarian.validate_evidence("KAP", "test-embedding-model", [wrong_page]) == []
        checked = await librarian.validate_evidence("KAP", "test-embedding-model", [valid])
        assert len(checked) == 1
        assert checked[0].content == "Teks kanonis halaman 14."

    asyncio.run(scenario())


def test_three_subject_specialists_are_independent_and_manager_verifies(tmp_path) -> None:
    async def scenario() -> None:
        database = Database(tmp_path / "academic_ai.db")
        await database.initialize(SUBJECTS)
        await database.upsert_user(123, "student", "Student")
        await database.add_document_and_chunks(
            _document_record("kap-doc", "KAP", "KAP_Bab_2.pdf", "data/knowledge/kap/kap.pdf", 123),
            [
                _chunk_record(
                    "kap-doc:p14:c0", 14, "Self-disclosure adalah keterbukaan diri.", [1.0, 0.0]
                )
            ],
        )
        provider = FakeProvider()
        store = LocalVectorStore(database, tmp_path / "data" / "vectorstore" / "vectors.sqlite")
        await store.sync_from_database(set(SUBJECTS))
        manager = AcademicManager(
            settings=FakeSettings(),
            database=database,
            provider=provider,
            embedding_service=EmbeddingService(provider, "test-embedding-model"),
            vector_store=store,
        )
        result = await manager.answer("KAP", "Apa itu self-disclosure?")
        assert result.status == "VERIFIED"
        assert result.sources == [{"document": "KAP_Bab_2.pdf", "page": 14}]
        assert result.successful_agents == 3
        assert provider.manager_calls == 1
        assert (
            len(provider.agent_prompts["A"])
            == len(provider.agent_prompts["B"])
            == len(provider.agent_prompts["C"])
            == 1
        )
        # No agent prompt contains the other agent's draft text.
        for payload in (
            provider.agent_prompts["A"]
            + provider.agent_prompts["B"]
            + provider.agent_prompts["C"]
        ):
            assert "Draft independen agent A." not in json.dumps(payload)
            assert "Draft independen agent B." not in json.dumps(payload)
            assert "Draft independen agent C." not in json.dumps(payload)
        manager_drafts = provider.manager_payloads[0]["agent_drafts"]
        assert len(manager_drafts) == 3
        material = provider.manager_payloads[0]["material_excerpts"]
        assert material[0]["document"] == "KAP_Bab_2.pdf"
        assert material[0]["page"] == 14

    asyncio.run(scenario())


def test_revision_loop_approves_after_one_round_without_sharing_drafts(tmp_path) -> None:
    async def scenario() -> None:
        database = Database(tmp_path / "academic_ai.db")
        await database.initialize(SUBJECTS)
        await database.upsert_user(123, "student", "Student")
        await database.add_document_and_chunks(
            _document_record("kap-doc", "KAP", "KAP_Bab_2.pdf", "data/knowledge/kap/kap.pdf", 123),
            [
                _chunk_record(
                    "kap-doc:p14:c0", 14, "Self-disclosure adalah keterbukaan diri.", [1.0, 0.0]
                )
            ],
        )
        provider = FakeProvider(["REVISION_REQUIRED", "APPROVED"])
        store = LocalVectorStore(database, tmp_path / "data" / "vectorstore" / "vectors.sqlite")
        await store.sync_from_database(set(SUBJECTS))
        manager = AcademicManager(
            FakeSettings(),
            database,
            provider,
            EmbeddingService(provider, "test-embedding-model"),
            store,
        )
        result = await manager.answer("KAP", "Apa itu self-disclosure?")
        assert result.status == "REVISED"
        assert result.revision_rounds == 1
        assert len(provider.agent_prompts["A"]) == 2
        assert len(provider.agent_prompts["B"]) == 2
        assert len(provider.agent_prompts["C"]) == 2
        revision_a = provider.agent_prompts["A"][1]
        revision_b = provider.agent_prompts["B"][1]
        revision_c = provider.agent_prompts["C"][1]
        assert revision_a["your_previous_draft_only"] == "Draft independen agent A."
        assert revision_b["your_previous_draft_only"] == "Draft independen agent B."
        assert revision_c["your_previous_draft_only"] == "Draft independen agent C."
        assert "Draft independen agent B." not in json.dumps(revision_a)
        assert "Draft independen agent C." not in json.dumps(revision_a)
        assert "Draft independen agent A." not in json.dumps(revision_b)
        assert "Draft independen agent C." not in json.dumps(revision_b)
        assert "Draft independen agent A." not in json.dumps(revision_c)
        assert "Draft independen agent B." not in json.dumps(revision_c)

    asyncio.run(scenario())


def test_revision_loop_never_exceeds_two_rounds(tmp_path) -> None:
    async def scenario() -> None:
        database = Database(tmp_path / "academic_ai.db")
        await database.initialize(SUBJECTS)
        await database.upsert_user(123, "student", "Student")
        await database.add_document_and_chunks(
            _document_record("kap-doc", "KAP", "KAP_Bab_2.pdf", "data/knowledge/kap/kap.pdf", 123),
            [
                _chunk_record(
                    "kap-doc:p14:c0", 14, "Self-disclosure adalah keterbukaan diri.", [1.0, 0.0]
                )
            ],
        )
        provider = FakeProvider(["REVISION_REQUIRED"])
        store = LocalVectorStore(database, tmp_path / "data" / "vectorstore" / "vectors.sqlite")
        await store.sync_from_database(set(SUBJECTS))
        manager = AcademicManager(
            FakeSettings(),
            database,
            provider,
            EmbeddingService(provider, "test-embedding-model"),
            store,
        )
        result = await manager.answer("KAP", "Apa itu self-disclosure?")
        assert result.status == "UNVERIFIED"
        assert result.revision_rounds == 2
        assert provider.manager_calls == 3  # Initial verification plus two revisions.
        assert len(provider.agent_prompts["A"]) == len(provider.agent_prompts["B"]) == 3

    asyncio.run(scenario())


def test_quiz_validator_rejects_missing_or_fabricated_sources() -> None:
    chunks = [RetrievedChunk("id", "KAP", "KAP_Bab_2.pdf", 14, "Teks", 1.0)]
    questions = [
        {
            "question": f"Soal {index}",
            "options": {"A": "satu", "B": "dua", "C": "tiga", "D": "empat"},
            "correct_answer": "A",
            "explanation": "Didukung cuplikan.",
            "source": "KAP_Bab_2.pdf",
            "page": 14,
        }
        for index in range(10)
    ]
    assert validate_quiz_answer(json.dumps({"questions": questions}), chunks) is None
    questions[0]["page"] = 99
    assert "Sumber/halaman" in (
        validate_quiz_answer(json.dumps({"questions": questions}), chunks) or ""
    )
    assert validate_quiz_answer("not json", chunks) is not None


def test_delete_material_removes_pdf_database_and_vector_index(tmp_path) -> None:
    async def scenario() -> None:
        settings = SimpleNamespace(
            project_root=tmp_path,
            knowledge_dir=tmp_path / "data" / "knowledge",
            vectorstore_dir=tmp_path / "data" / "vectorstore",
            subjects=SUBJECTS,
        )
        pdf_path = settings.knowledge_dir / "kap" / "kap.pdf"
        pdf_path.parent.mkdir(parents=True)
        pdf_path.write_bytes(b"test pdf placeholder")
        database = Database(tmp_path / "data" / "academic_ai.db")
        await database.initialize(SUBJECTS)
        await database.upsert_user(123, "student", "Student")
        await database.add_document_and_chunks(
            _document_record("kap-doc", "KAP", "KAP_Bab_2.pdf", "data/knowledge/kap/kap.pdf", 123),
            [_chunk_record("kap-doc:p14:c0", 14, "Isi", [1.0, 0.0])],
        )
        store = LocalVectorStore(database, settings.vectorstore_dir / "vectors.sqlite")
        await store.sync_from_database(set(SUBJECTS))
        service = MaterialService(
            settings, database, EmbeddingService(FakeProvider(), "test-embedding-model"), store
        )
        deleted = await service.delete_pdf(subject_code="KAP", document_id="kap-doc")
        assert deleted is not None
        assert not pdf_path.exists()
        assert await database.get_document("KAP", "kap-doc") is None
        assert await store.search("KAP", [1.0, 0.0], embedding_model="test-embedding-model") == []

    asyncio.run(scenario())
