"""Orkestrator AI Teknisi: scan -> perbaiki config -> (mode penuh) patch kode AI + auto-loop."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.technician.checks import Issue, run_health_checks
from app.technician.coder import CodeFixReport, diagnose_and_fix, rollback_last
from app.technician.collector import ErrorCollector
from app.technician.fixers import apply_safe_fixes, read_journal

logger = logging.getLogger(__name__)


class TechnicianService:
    def __init__(self, settings: Any, academic_manager: Any) -> None:
        self.settings = settings
        self.manager = academic_manager
        self.collector = ErrorCollector(limit=60)
        self.collector.attach()
        self._auto_task: asyncio.Task | None = None
        self._last_scan: dict[str, Any] = {}

    # ------------------------------------------------------------------ status
    async def status(self) -> dict[str, Any]:
        data_dir = Path(getattr(self.settings, "data_dir", Path("data")))
        return {
            "enabled": bool(getattr(self.settings, "technician_enabled", True)),
            "auto": bool(getattr(self.settings, "technician_auto", True)),
            "mode": getattr(self.settings, "technician_mode", "safe"),
            "code_fix": bool(getattr(self.settings, "technician_code_fix", True)),
            "interval_min": int(getattr(self.settings, "technician_interval_min", 30)),
            "recent_errors": [
                {"ts": e.ts, "level": e.level, "message": e.message[:220], "codes": e.codes}
                for e in self.collector.unique_recent(data_dir / "logs", limit=8)
            ],
            "journal": read_journal(data_dir, limit=12),
            "last_scan": self._last_scan,
        }

    # -------------------------------------------------------------------- scan
    async def scan(self, mode: str | None = None) -> dict[str, Any]:
        if not getattr(self.settings, "technician_enabled", True):
            return {"ok": False, "detail": "TECHNICIAN_ENABLED=false di .env."}
        mode = (mode or getattr(self.settings, "technician_mode", "safe")).lower()
        if mode not in {"safe", "full"}:
            mode = "safe"
        started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        provider = self.manager.provider
        manager_provider = getattr(self.manager, "manager_provider", provider)

        issues: list[Issue] = await run_health_checks(
            settings=self.settings,
            provider=provider,
            manager_provider=manager_provider,
            collector=self.collector,
        )
        fixes = apply_safe_fixes(self.settings, issues)

        code_report: CodeFixReport | None = None
        if (
            mode == "full"
            and getattr(self.settings, "technician_code_fix", True)
        ):
            errors = [
                {"ts": e.ts, "message": e.message}
                for e in self.collector.unique_recent(
                    Path(getattr(self.settings, "data_dir", Path("data"))) / "logs", limit=10
                )
            ]
            if errors:
                code_report = await diagnose_and_fix(
                    settings=self.settings,
                    provider=manager_provider,
                    errors=errors,
                    test_command=[
                        sys_executable(),
                        "-m",
                        "pytest",
                        "tests/",
                        "-q",
                        "--ignore=tests/test_video.py",
                        "--ignore=tests/test_agent_office.py",
                    ],
                )

        result = {
            "ok": True,
            "ts": started,
            "mode": mode,
            "issues": [issue.as_dict() for issue in issues],
            "fixes": [fix.as_dict() for fix in fixes],
            "code_fix": code_report.as_dict() if code_report else None,
            "restart_needed": any(fix.restart_needed for fix in fixes)
            or bool(code_report and code_report.kept and code_report.patches),
            "summary": "",
        }
        result["summary"] = _summarize(issues, fixes, code_report)
        self._last_scan = result
        logger.info("[TECH] Scan %s: %s", mode, result["summary"])
        return result

    # ----------------------------------------------------------------- rollback
    async def rollback(self) -> dict[str, Any]:
        outcome = rollback_last(self.settings)
        if outcome.get("ok"):
            logger.info("[TECH] Rollback batch %s (%s file)", outcome.get("batch_id"), len(outcome.get("restored", [])))
        return outcome

    # --------------------------------------------------------------- auto loop
    async def auto_loop(self) -> None:
        interval = max(5, int(getattr(self.settings, "technician_interval_min", 30))) * 60
        await asyncio.sleep(90)  # beri waktu startup penuh sebelum scan pertama
        while True:
            try:
                await self.scan(getattr(self.settings, "technician_mode", "safe"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("[TECH] Auto-scan gagal (%s)", type(exc).__name__)
            await asyncio.sleep(interval)

    def start_auto(self) -> None:
        if not getattr(self.settings, "technician_enabled", True):
            return
        if not getattr(self.settings, "technician_auto", True):
            return
        if self._auto_task is None or self._auto_task.done():
            self._auto_task = asyncio.get_running_loop().create_task(self.auto_loop())
            logger.info(
                "[TECH] AI Teknisi auto aktif (mode %s, tiap %s menit)",
                getattr(self.settings, "technician_mode", "safe"),
                getattr(self.settings, "technician_interval_min", 30),
            )

    async def stop_auto(self) -> None:
        if self._auto_task is not None and not self._auto_task.done():
            self._auto_task.cancel()
            try:
                await self._auto_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._auto_task = None


def sys_executable() -> str:
    import sys

    return sys.executable


def _summarize(issues: list[Issue], fixes: list[Any], code_report: CodeFixReport | None) -> str:
    parts = [f"{len(issues)} masalah terdeteksi", f"{len(fixes)} perbaikan config diterapkan"]
    if code_report is not None:
        applied = sum(1 for patch in code_report.patches if patch.applied)
        if code_report.kept:
            parts.append(f"patch AI diterapkan ({applied} file, uji lulus)")
        elif applied:
            parts.append("patch AI di-rollback (uji gagal)")
        elif code_report.error:
            parts.append(f"patch AI: {code_report.error[:80]}")
        else:
            parts.append("tidak ada patch AI yang cocok")
    return "; ".join(parts)
