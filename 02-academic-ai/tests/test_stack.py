from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from app.knowledge import pdf_processor
from app.knowledge.compress import compress_chunks, estimate_saved, rolling_history
from app.knowledge.fabric_patterns import list_patterns, render
from app.knowledge.tree_index import build_tree, pick_sections, retrieve_with_tree
from app.knowledge.vector_store import RetrievedChunk
from app.manager.manager import AcademicManager, AcademicResult
from app.manager.skills import record_answer_shape, skill_hint_for, skill_name
from app.services import webfetch
from app.services.user_memory import recall_for_query, record_from_text
from app.services.webfetch import duckduckgo_links, fetch_text, html_to_text, summarize_web


def _db(tmp_path: Path, name: str = "s.db"):
    from app.database.database import Database

    async def _init():
        database = Database(tmp_path / name)
        await database.initialize({})
        return database

    return asyncio.run(_init())


def _chunk(**overrides):
    base = {
        "chunk_id": "c1",
        "subject_code": "PP",
        "document_name": "d.pdf",
        "page_number": 1,
        "content": "isi",
        "score": 0.9,
    }
    base.update(overrides)
    return RetrievedChunk(**base)


def test_html_to_text_and_duckduckgo_parse(monkeypatch) -> None:
    html = "<html><head><style>x{}</style></head><body><script>bad()</script><p>Bagus &amp; bersih</p></body></html>"
    assert html_to_text(html) == "Bagus & bersih"
    ddg = (
        '<a class="result__a" href="https://contoh.id/a">Judul <b>A</b></a>'
        '<a class="result__a" href="/relative">Relatif</a>'
    )
    monkeypatch.setattr(webfetch, "download_html", lambda url, timeout=20: ddg)
    assert duckduckgo_links("apa", limit=5) == [("Judul A", "https://contoh.id/a")]


def test_fetch_text_httpx_fallback(monkeypatch) -> None:
    monkeypatch.setattr(webfetch, "_scrapling_get", lambda url, timeout: None)

    class FakeResponse:
        text = "<p>Halo</p>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(webfetch.httpx, "get", lambda *a, **k: FakeResponse())
    assert fetch_text("http://x") == "Halo"


def test_summarize_web_skips_short_and_fails_cleanly(monkeypatch) -> None:
    seen: dict = {}

    async def fake_summarize(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(as_dict=lambda: {"status": "OK"})

    manager = SimpleNamespace(summarize_source_text=fake_summarize)
    monkeypatch.setattr(
        webfetch,
        "duckduckgo_links",
        lambda query, limit=3: [("Pendek", "http://pendek"), ("Panjang", "http://panjang")],
    )
    monkeypatch.setattr(
        webfetch,
        "fetch_text",
        lambda url, timeout=20: "pendek" if "pendek" in url else "isi penting " * 100,
    )
    result = asyncio.run(summarize_web(manager, "kunci"))
    assert result.as_dict()["status"] == "OK"
    assert seen["source_name"] == "[web] Panjang"
    monkeypatch.setattr(webfetch, "duckduckgo_links", lambda query, limit=3: [])
    try:
        asyncio.run(summarize_web(manager, "kunci"))
    except ValueError as exc:
        assert "hasil web" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_docling_absent_falls_back(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "docling", None)
    monkeypatch.setitem(sys.modules, "docling.document_converter", None)
    assert pdf_processor._try_docling(Path("x.pdf")) is None


def test_extract_prefers_docling(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pdf_processor, "_try_docling", lambda path: [(1, "docling" * 40)])

    def _boom(*args, **kwargs):
        raise AssertionError("pypdf must not run")

    monkeypatch.setattr(pdf_processor, "PdfReader", _boom)
    assert extract_pages(tmp_path) == [(1, "docling" * 40)]


def extract_pages(tmp_path: Path):
    return pdf_processor.extract_pdf_pages(tmp_path / "x.pdf")


def test_tree_build_pick_retrieve() -> None:
    rows = [
        {
            "chunk_id": "a1",
            "document_name": "d.pdf",
            "page_number": 1,
            "content": "BAB 1 FOTOSINTESIS",
        },
        {
            "chunk_id": "a2",
            "document_name": "d.pdf",
            "page_number": 2,
            "content": "klorofil menangkap cahaya matahari",
        },
        {
            "chunk_id": "b1",
            "document_name": "d.pdf",
            "page_number": 5,
            "content": "BAB 2 RESPIRASI",
        },
        {
            "chunk_id": "b2",
            "document_name": "d.pdf",
            "page_number": 6,
            "content": "mitokondria dan oksigen",
        },
    ]
    sections = build_tree(rows)
    assert [section.title for section in sections] == ["BAB 1 FOTOSINTESIS", "BAB 2 RESPIRASI"]
    assert pick_sections(sections, "cahaya klorofil")[0].title == "BAB 1 FOTOSINTESIS"

    async def scenario():
        database = SimpleNamespace(
            get_embedding_models_for_subject=lambda code: _coro({"e1"}),
            list_chunks_for_subject=lambda code, model: _coro(rows),
        )
        settings = SimpleNamespace(embedding_model="e1", rag_top_k=2)
        chunks = await retrieve_with_tree(database, settings, "PP", "klorofil cahaya")
        assert [chunk.chunk_id for chunk in chunks] == ["a1", "a2"]
        try:
            await retrieve_with_tree(
                database, SimpleNamespace(embedding_model="", rag_top_k=2), "PP", "x"
            )
        except ValueError as exc:
            assert "MODEL_EMBEDDING" in str(exc)
        else:
            raise AssertionError("expected ValueError")

    asyncio.run(scenario())


def _coro(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner()


def test_memory_record_recall_trim(tmp_path: Path) -> None:
    database = _db(tmp_path)

    async def scenario():
        fresh = await record_from_text(database, 7, "Halo, nama saya Budi Santoso.")
        assert fresh == ["Nama user: Budi Santoso"]
        assert await record_from_text(database, 7, "Nama saya Budi Santoso.") == []
        assert await record_from_text(database, 7, "apa kabar?") == []
        assert await recall_for_query(database, 7, "siapa budi?") == ["Nama user: Budi Santoso"]
        for index in range(60):
            await database.add_fact(7, f"fakta {index}")
        await database.trim_facts(7, 50)
        assert len(await database.list_facts(7)) == 50

    asyncio.run(scenario())


def test_compress_chunks_history_saved() -> None:
    chunks = [
        _chunk(chunk_id="a", content="satu  dua"),
        _chunk(chunk_id="a"),
        _chunk(chunk_id="b", content="x" * 100),
    ]
    kept, stats = compress_chunks(chunks, 50)
    assert [chunk.chunk_id for chunk in kept] == ["a"]
    assert stats["dropped"] == 2 and kept[0].content == "satu dua"
    history = [{"role": "user", "content": f"m{index}"} for index in range(15)]
    rolled = rolling_history(history, 5)
    assert [item["content"] for item in rolled] == ["m0", "m11", "m12", "m13", "m14"]
    assert estimate_saved(100, 40)["saved_pct"] == 60.0


def test_skills_learn_and_hint(tmp_path: Path) -> None:
    database = _db(tmp_path, "k.db")

    async def scenario():
        settings = SimpleNamespace(skills_learn_enabled=True)
        assert skill_name("Quiz", "PP") == "quiz:pp"
        await record_answer_shape(
            database,
            settings,
            task_mode="quiz",
            subject_code="PP",
            status="VERIFIED",
            revision_rounds=0,
            answer_len=123,
            source_count=3,
        )
        hint = await skill_hint_for(database, settings, "quiz", "PP")
        assert "quiz:pp" in hint and "3 sumber" in hint
        assert "skill bawaan" in hint
        await record_answer_shape(
            database,
            settings,
            task_mode="answer",
            subject_code="PP",
            status="UNVERIFIED",
            revision_rounds=1,
            answer_len=50,
            source_count=0,
        )
        answer_hint = await skill_hint_for(database, settings, "answer", "PP")
        assert "skill bawaan" in answer_hint and "quiz:pp" not in answer_hint
        off = SimpleNamespace(skills_learn_enabled=False)
        await record_answer_shape(
            database,
            off,
            task_mode="quiz",
            subject_code="PA",
            status="VERIFIED",
            revision_rounds=0,
            answer_len=99,
            source_count=2,
        )
        assert await database.get_skill("quiz:pa") is None

    asyncio.run(scenario())


def test_fabric_patterns_render() -> None:
    assert "explain_simple" in list_patterns()
    text = render("explain_simple", topic="inflasi")
    assert "inflasi" in text and "{topic}" not in text
    try:
        render("tidak-ada")
    except ValueError as exc:
        assert "tidak dikenal" in str(exc)
    else:
        raise AssertionError("expected ValueError")
    try:
        render("quiz_maker", count="2")
    except ValueError as exc:
        assert "variabel" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_manager_tree_and_hybrid_modes() -> None:
    rows = [
        {
            "chunk_id": "a1",
            "document_name": "d.pdf",
            "page_number": 1,
            "content": "BAB 1 FOTOSINTESIS",
        },
        {
            "chunk_id": "a2",
            "document_name": "d.pdf",
            "page_number": 2,
            "content": "klorofil cahaya",
        },
    ]

    async def scenario():
        manager = AcademicManager.__new__(AcademicManager)
        manager.settings = SimpleNamespace(
            rag_mode="tree", embedding_model="e1", rag_top_k=5, max_context_chars=60000
        )
        manager.database = SimpleNamespace(
            get_embedding_models_for_subject=lambda code: _coro({"e1"}),
            list_chunks_for_subject=lambda code, model: _coro(rows),
        )
        chunks = await manager._retrieve("PP", "klorofil")
        assert [chunk.chunk_id for chunk in chunks] == ["a1", "a2"]
        manager.settings.rag_mode = "hybrid"
        manager.research_team = SimpleNamespace(
            collect_evidence=lambda code, q: _coro(SimpleNamespace(chunks=[_chunk(chunk_id="v9")])),
        )
        merged = await manager._retrieve("PP", "klorofil")
        assert [chunk.chunk_id for chunk in merged] == ["v9", "a1", "a2"]

    asyncio.run(scenario())


def test_answer_records_and_recalls_memory(tmp_path: Path) -> None:
    captured: dict = {}

    async def fake_workflow(**kwargs):
        captured.update(kwargs)
        return AcademicResult(
            status="VERIFIED",
            answer="jawab",
            sources=[],
            confidence=1.0,
            reason="",
            revision_rounds=0,
            successful_agents=2,
            task_mode="answer",
            manager_model="m",
        )

    database = _db(tmp_path, "mem.db")
    database.get_subject_counts = lambda code: _coro((1, 1))

    async def scenario():
        manager = AcademicManager.__new__(AcademicManager)
        manager.settings = SimpleNamespace(
            subjects={"PP": SimpleNamespace(code="PP")}, memory_enabled=True
        )
        manager.database = database
        manager._retrieve = lambda code, q: _coro([_chunk()])
        manager._run_workflow = fake_workflow
        manager._subject = lambda code: SimpleNamespace(code="PP")
        await manager.answer("PP", "nama saya Budi, apa itu fotosintesis?", [], user_id=7)
        assert (await database.list_facts(7))[0]["fact"] == "Nama user: Budi"
        await manager.answer("PP", "lanjut budi", [], user_id=7)
        assert "[profil]" in captured["history"][0]["content"]

    asyncio.run(scenario())
