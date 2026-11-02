"""mem0-inspired user memory on SQLite (heuristic extract, keyword recall). Free."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_PATTERNS = [
    (re.compile(r"nama saya ([a-zA-Z][a-zA-Z .']{1,39})"), "Nama user: {}"),
    (re.compile(r"panggil saya ([a-zA-Z][a-zA-Z .']{1,29})"), "Panggil user: {}"),
    (
        re.compile(
            r"saya (suka|tidak suka|kelas \S+|dari \S+|kuliah di [^.,;]+|"
            r"sekolah di [^.,;]+|belajar [^.,;]+)",
            re.IGNORECASE,
        ),
        "User: saya {}",
    ),
]
_WORD = re.compile(r"[a-zA-Z0-9]{4,}")
_MAX_FACTS = 50


async def record_from_text(database, user_id: int, text: str) -> list[str]:
    """Extract durable facts from a user message. Returns newly stored facts."""
    found: list[str] = []
    for pattern, template in _PATTERNS:
        match = pattern.search(text or "")
        if match:
            found.append(template.format(match.group(1).strip().rstrip(".")[:80]))
    if not found:
        return []
    try:
        existing = {row["fact"] for row in await database.list_facts(user_id)}
        fresh = [fact for fact in found if fact not in existing][:5]
        for fact in fresh:
            await database.add_fact(user_id, fact)
        await database.trim_facts(user_id, _MAX_FACTS)
        if fresh:
            await _best_effort_sync_user_memory(database)
        return fresh
    except Exception as exc:
        logger.warning("[WARN] Gagal menyimpan memori (%s).", type(exc).__name__)
        return []


async def _best_effort_sync_user_memory(database) -> None:
    """Ekspor & sinkronkan user_facts ke repo GitHub MARU secara non-blocking."""
    try:
        import asyncio
        import sys as _sys
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
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
                    "memory/academic/user_facts.json",
                    commit_label="academic-memory",
                )

        await asyncio.to_thread(_sync_worker)
    except Exception:
        return


async def recall_for_query(database, user_id: int, query: str, limit: int = 3) -> list[str]:
    """Keyword recall over stored facts. Never raises."""
    try:
        facts = [row["fact"] for row in await database.list_facts(user_id)]
    except Exception:
        return []
    wanted = set(match.group(0).lower() for match in _WORD.finditer(query or ""))
    if not wanted:
        return facts[:limit]
    scored = sorted(
        facts,
        key=lambda fact: len(
            set(match.group(0).lower() for match in _WORD.finditer(fact)) & wanted
        ),
        reverse=True,
    )
    return [fact for fact in scored[:limit] if fact]
