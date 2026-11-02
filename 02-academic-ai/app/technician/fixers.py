"""Perbaikan otomatis tingkat konfigurasi (aman): tulis .env + jurnal perbaikan."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import update_env_file
from app.technician.checks import Issue

logger = logging.getLogger(__name__)


@dataclass
class FixRecord:
    ts: str
    code: str
    action: str
    before: str
    after: str
    restart_needed: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def append_journal(data_dir: Path, record: dict[str, Any]) -> None:
    try:
        journal = data_dir / "fix_journal.jsonl"
        data_dir.mkdir(parents=True, exist_ok=True)
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[TECH] Gagal menulis jurnal (%s)", type(exc).__name__)


def read_journal(data_dir: Path, limit: int = 20) -> list[dict[str, Any]]:
    journal = data_dir / "fix_journal.jsonl"
    if not journal.is_file():
        return []
    try:
        lines = journal.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(records))


def apply_safe_fixes(settings: Any, issues: list[Issue]) -> list[FixRecord]:
    """Terapkan perbaikan config yang dikenal aman. Return daftar yang diterapkan."""
    updates: dict[str, str] = {}
    records: list[FixRecord] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for issue in issues:
        if not issue.fixable:
            continue
        if issue.code in {"MODEL_MANAGER_TIDAK_DITEMUKAN", "MODEL_MANAGER_KOSONG"}:
            current = str(issue.data.get("current", ""))
            replacement = str(issue.data.get("replacement", "")).strip()
            if replacement and replacement != current:
                updates["MODEL_MANAGER"] = replacement
                records.append(
                    FixRecord(
                        ts=now,
                        code=issue.code,
                        action="Ganti MODEL_MANAGER",
                        before=current or "(kosong)",
                        after=replacement,
                        restart_needed=True,
                    )
                )
        elif issue.code == "MODEL_SPECIALIST_TIDAK_DITEMUKAN":
            for item in issue.data.get("models", []):
                key = str(item.get("key", ""))
                replacement = str(item.get("replacement", "")).strip()
                current = str(item.get("current", ""))
                if key and replacement and replacement != current:
                    updates[key] = replacement
                    records.append(
                        FixRecord(
                            ts=now,
                            code=issue.code,
                            action=f"Ganti {key}",
                            before=current or "(kosong)",
                            after=replacement,
                            restart_needed=True,
                        )
                    )
        elif issue.code == "MODEL_EMBEDDING_TIDAK_DITEMUKAN":
            current = str(issue.data.get("current", ""))
            replacement = str(issue.data.get("replacement", "")).strip()
            if replacement and replacement != current:
                updates["MODEL_EMBEDDING"] = replacement
                records.append(
                    FixRecord(
                        ts=now,
                        code=issue.code,
                        action="Ganti MODEL_EMBEDDING",
                        before=current,
                        after=replacement,
                        restart_needed=True,
                    )
                )
        elif issue.code == "MODEL_EMBEDDING_KOSONG":
            replacement = ""
            catalog = issue.data.get("catalog") or []
            if catalog:
                replacement = str(catalog[0])
            if replacement:
                updates["MODEL_EMBEDDING"] = replacement
                records.append(
                    FixRecord(
                        ts=now,
                        code=issue.code,
                        action="Isi MODEL_EMBEDDING",
                        before="(kosong)",
                        after=replacement,
                        restart_needed=True,
                    )
                )
        elif issue.code == "TIMEOUT_TERLALU_PENDEK":
            updates["NINE_ROUTER_TIMEOUT"] = "300"
            records.append(
                FixRecord(
                    ts=now,
                    code=issue.code,
                    action="Naikkan NINE_ROUTER_TIMEOUT",
                    before=str(issue.data.get("current", "")),
                    after="300",
                    restart_needed=True,
                )
            )

    if updates:
        try:
            update_env_file(Path(getattr(settings, "env_file", ".env")), updates)
        except Exception as exc:  # noqa: BLE001
            logger.error("[TECH] Gagal menulis .env (%s)", type(exc).__name__)
            return []
        for record in records:
            append_journal(Path(getattr(settings, "data_dir", Path("data"))), {"type": "config_fix", **record.as_dict()})
    return records
