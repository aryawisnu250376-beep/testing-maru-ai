import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import db  # noqa: E402


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """DB bersih per test — jangan pernah menyentuh data/pipeline.db asli."""
    path = tmp_path / "test.db"
    db.set_db_path(path)
    db.init()
    # state orkestrator juga harus diisolasi: kalau tidak, test bisa
    # menghapus `last_episode_at` milik proses yang sedang berjalan.
    from src import orchestrator

    orchestrator.set_state_path(tmp_path / "orch_state.json")
    yield path
    db.set_db_path(ROOT / "data" / "pipeline.db")
    orchestrator.set_state_path(ROOT / "data" / "orchestrator_state.json")


@pytest.fixture()
def cfg():
    from src.config import load_config

    return load_config()


@pytest.fixture()
def cluster():
    return {
        "theme": "on_device",
        "label": "AI yang bisa jalan di HP sendiri",
        "angle_hint": "Kenapa AI sekarang muat di kantong, dan apa batasnya",
        "headline_signal": "Model AI baru: LFM3-1.7B",
        "score": 0.85,
        "sources": ["github", "huggingface"],
        "evidence": [
            {"source": "github", "title": "repo A on-device agent", "url": "https://github.com/a/b",
             "raw_score": 900, "score": 0.8},
            {"source": "huggingface", "title": "LiquidAI/LFM3-1.7B", "url": "https://huggingface.co/L/lfm3",
             "raw_score": 400, "score": 0.75},
            {"source": "hackernews", "title": "LLM on your phone", "url": "https://news.ycombinator.com/item?id=1",
             "raw_score": 300, "score": 0.7},
        ],
    }
