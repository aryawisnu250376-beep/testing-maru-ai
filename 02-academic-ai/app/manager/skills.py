"""Hermes-style skill loop: record the shape of wins, inject hints. No extra LLM.

Ditambah skill pack bawaan (prompts/skills/) yang diadaptasi dari pola
Agent Skills open-source (https://github.com/anthropics/skills — SKILL.md,
spesifikasi https://agentskills.io). Skill bawaan dipakai sebagai dasar;
hint yang dipelajari dari jawaban VERIFIED dilampirkan di atasnya.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = PROJECT_ROOT / "prompts" / "skills"

_BUILTIN_SKILL_FILES = {
    "answer": ("answer.md", "citation_discipline.md"),
    "summary": ("summary.md", "citation_discipline.md"),
    "quiz": ("quiz.md", "citation_discipline.md"),
    "youtube_summary": ("summary.md",),
}


def skill_name(task_mode: str, subject_code: str) -> str:
    return f"{task_mode}:{subject_code}".lower()


def _builtin_skill_text(task_mode: str) -> str:
    parts: list[str] = []
    for filename in _BUILTIN_SKILL_FILES.get(task_mode, ("answer.md",)):
        try:
            text = (SKILLS_DIR / filename).read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if text:
            parts.append(text)
    return "\n\n".join(parts)


async def record_answer_shape(
    database,
    settings,
    *,
    task_mode: str,
    subject_code: str,
    status: str,
    revision_rounds: int,
    answer_len: int,
    source_count: int,
) -> None:
    """Learn from a finished answer. Never breaks answering."""
    if not getattr(settings, "skills_learn_enabled", True):
        return
    try:
        won = status in {"VERIFIED", "REVISED"}
        hint = (
            f"jawaban {task_mode} {subject_code} yang VERIFIED: "
            f"~{max(50, answer_len // 5 * 5)} kata, {source_count} sumber."
        )
        await database.upsert_skill(
            skill_name(task_mode, subject_code),
            subject_code=subject_code,
            task_mode=task_mode,
            hint=hint[:200],
            won=won,
        )
        if won:
            logger.info(
                "[INFO] Skill menang: %s (revisi %d).",
                skill_name(task_mode, subject_code),
                revision_rounds,
            )
            await _best_effort_sync_academic_skills(database)
    except Exception as exc:
        logger.warning("[WARN] Gagal merekam skill (%s).", type(exc).__name__)


async def _best_effort_sync_academic_skills(database) -> None:
    """Ekspor & sinkronkan answer_skills ke repo GitHub MARU tanpa pernah memutus proses jawab."""
    try:
        import asyncio
        import sys as _sys

        repo_root = PROJECT_ROOT.parent
        if not (repo_root / "maru_github_sync").is_dir():
            return
        db_path = getattr(database, "path", None)
        if not isinstance(db_path, Path) or not db_path.is_file():
            return

        def _sync_worker() -> None:
            if str(repo_root) not in _sys.path:
                _sys.path.insert(0, str(repo_root))
            from maru_github_sync import GitHubSyncConfig, MaruGitHubSyncService

            gcfg = GitHubSyncConfig.from_env(repo_root=repo_root)
            svc = MaruGitHubSyncService(gcfg)
            svc.export_local_to_central(academic_db_path=db_path)
            if gcfg.is_ready:
                svc.best_effort_push_single(
                    "skills/learned/academic_answer_skills.json",
                    commit_label="academic-skills",
                )

        await asyncio.to_thread(_sync_worker)
    except Exception:
        return


async def skill_hint_for(database, settings, task_mode: str, subject_code: str) -> str:
    """Builtin skill pack + hint from past wins, or ''. Never raises."""
    if not getattr(settings, "skills_learn_enabled", True):
        return ""
    hints: list[str] = []
    builtin = _builtin_skill_text(task_mode)
    if builtin:
        hints.append(f"[skill bawaan {task_mode}]\n{builtin}")
    try:
        row = await database.get_skill(skill_name(task_mode, subject_code))
    except Exception:
        row = None
    if row and int(row.get("wins", 0)) > 0:
        hints.append(f"[skill {row['name']}] {row['hint']}")
    return "\n\n".join(hints)
