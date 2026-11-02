from __future__ import annotations

MAX_REVISION_ROUNDS = 2


def should_revise(decision: str, completed_revision_rounds: int, configured_max: int = 2) -> bool:
    """There is one initial verification plus at most two revision rounds."""
    limit = min(MAX_REVISION_ROUNDS, max(0, configured_max))
    return decision == "REVISION_REQUIRED" and completed_revision_rounds < limit
