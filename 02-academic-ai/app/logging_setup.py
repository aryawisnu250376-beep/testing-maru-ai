from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE_MAX_BYTES = 2 * 1024 * 1024
LOG_FILE_BACKUPS = 5


def resolve_log_dir() -> Path:
    """Mirror Settings' DATA_DIR resolution so logs land in data/logs/."""
    data_setting = Path(os.getenv("DATA_DIR", "data")).expanduser()
    data_dir = data_setting if data_setting.is_absolute() else PROJECT_ROOT / data_setting
    return data_dir / "logs"


def setup_logging(process_name: str, *, log_dir: Path | None = None) -> logging.Logger:
    """Console output (historical plain style) plus a rotating file log.

    Idempotent: calling twice for the same process/log file adds no handlers.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    level = getattr(logging, level_name, logging.INFO)
    target = log_dir or resolve_log_dir()
    target.mkdir(parents=True, exist_ok=True)
    log_file = target / f"{process_name}.log"

    root = logging.getLogger()
    root.setLevel(level)
    has_console = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler)
        for handler in root.handlers
    )
    if not has_console:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("%(message)s"))
        console.setLevel(level)
        root.addHandler(console)
    has_file = any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", "") == str(log_file)
        for handler in root.handlers
    )
    if not has_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUPS,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        file_handler.setLevel(level)
        root.addHandler(file_handler)
    return logging.getLogger(f"academic_ai.{process_name}")
