def is_authorized(user_id: int | None, allowed_user_ids: frozenset[int] | set[int]) -> bool:
    """Return True only for IDs explicitly present in the allowlist."""
    return user_id is not None and user_id in allowed_user_ids
