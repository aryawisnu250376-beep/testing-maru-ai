"""Pengumpul error: handler logging in-process + ekor file log data/logs/*.log."""

from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[,.]?\d*\s+(?P<level>ERROR|WARNING)\s+"
    r"(?P<logger>[\w.]+):\s*(?P<msg>.*)$"
)

# Pola error yang sudah dikenali beserta kode masalahnya.
KNOWN_SIGNATURES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Manager verification failed", re.I), "VERIFIER_GAGAL"),
    (re.compile(r"model gagal \((?P<exc>\w+)\)", re.I), "PANGGILAN_MODEL_GAGAL"),
    (re.compile(r"404 Not Found|NotFoundError|model.*not found", re.I), "MODEL_TIDAK_DITEMUKAN"),
    (re.compile(r"APITimeoutError|timed? ?out|Timeout", re.I), "TIMEOUT_MODEL"),
    (re.compile(r"invalid structured output", re.I), "OUTPUT_AGENT_TIDAK_VALID"),
    (re.compile(r"transcription failed|STT", re.I), "STT_GAGAL"),
    (re.compile(r"Katalog model live tidak dapat dibaca", re.I), "ENDPOINT_TIDAK_TERJANGKAU"),
]


@dataclass(frozen=True)
class ErrorEvent:
    ts: str
    level: str
    logger: str
    message: str
    source: str  # "runtime" | nama file log

    @property
    def codes(self) -> list[str]:
        found = [code for pattern, code in KNOWN_SIGNATURES if pattern.search(self.message)]
        return found or ["ERROR_LAIN"]


class _RingHandler(logging.Handler):
    def __init__(self, sink: deque[ErrorEvent], limit: int) -> None:
        super().__init__(level=logging.WARNING)
        self._sink = sink
        self._limit = limit

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = ErrorEvent(
                ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                level=record.levelname,
                logger=record.name,
                message=self.format(record)[:500],
                source="runtime",
            )
            self._sink.append(event)
            while len(self._sink) > self._limit:
                self._sink.popleft()
        except Exception:  # noqa: BLE001
            pass


@dataclass
class ErrorCollector:
    limit: int = 50
    events: deque[ErrorEvent] = field(default_factory=lambda: deque(maxlen=50))
    _handler: _RingHandler | None = field(default=None, repr=False)

    def attach(self) -> None:
        """Pasang handler logging sekali (idempoten)."""
        if self._handler is not None:
            return
        self._handler = _RingHandler(self.events, self.limit)
        logging.getLogger().addHandler(self._handler)

    def runtime_events(self) -> list[ErrorEvent]:
        return list(self.events)

    def log_file_events(self, log_dir: Path, tail_lines: int = 400) -> list[ErrorEvent]:
        events: list[ErrorEvent] = []
        if not log_dir.is_dir():
            return events
        for log_file in sorted(log_dir.glob("*.log")):
            try:
                lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines[-tail_lines:]:
                match = LOG_LINE.match(line.strip())
                if not match:
                    continue
                events.append(
                    ErrorEvent(
                        ts=match.group("ts"),
                        level=match.group("level"),
                        logger=match.group("logger"),
                        message=match.group("msg")[:500],
                        source=log_file.name,
                    )
                )
        return events[-tail_lines:]

    def unique_recent(self, log_dir: Path, limit: int = 12) -> list[ErrorEvent]:
        """Gabung runtime + file log, dedupe per pesan, terbaru dulu."""
        combined = self.log_file_events(log_dir) + self.runtime_events()
        seen: set[str] = set()
        unique: list[ErrorEvent] = []
        for event in reversed(combined):
            key = event.message.strip()[:160]
            if key in seen:
                continue
            seen.add(key)
            unique.append(event)
            if len(unique) >= limit:
                break
        return unique
