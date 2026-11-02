from __future__ import annotations

import logging
from contextlib import suppress

from app.logging_setup import resolve_log_dir, setup_logging


def test_setup_logging_writes_rotating_file_and_is_idempotent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    root.handlers.clear()
    try:
        logger = setup_logging("testproc", log_dir=tmp_path)
        logger.info("hello-log-file")
        for handler in root.handlers:
            handler.flush()
        content = (tmp_path / "testproc.log").read_text(encoding="utf-8")
        assert "hello-log-file" in content
        setup_logging("testproc", log_dir=tmp_path)
        assert len(root.handlers) == 2
    finally:
        for handler in root.handlers:
            with suppress(Exception):
                handler.close()
        root.handlers[:] = old_handlers


def test_resolve_log_dir_defaults_under_project_data() -> None:
    assert resolve_log_dir().name == "logs"
    assert resolve_log_dir().parent.name == "data"
