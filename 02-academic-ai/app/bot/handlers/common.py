from __future__ import annotations

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.auth import is_authorized

logger = logging.getLogger(__name__)
MAX_TELEGRAM_MESSAGE = 3800


async def require_authorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    settings = context.application.bot_data["settings"]
    user = update.effective_user
    message = update.effective_message
    user_id = user.id if user else None
    if not is_authorized(user_id, settings.allowed_user_ids):
        logger.warning("[WARN] Unauthorized user")
        if message:
            await message.reply_text("Unauthorized user.")
        return False

    database = context.application.bot_data["database"]
    await database.upsert_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
    )
    logged_users: set[int] = context.application.bot_data.setdefault(
        "logged_authorized_users", set()
    )
    if user.id not in logged_users:
        logger.info("[INFO] User authorized")
        logged_users.add(user.id)
    return True


async def resolve_active_subject(
    message: Any, settings: Any, database: Any, user_id: int
) -> Any | None:
    """Return the user's active Subject, replying with guidance when unavailable.

    Handles both "no subject chosen yet" and "chosen subject missing from config"
    (for example after subjects.yaml was edited), which previously raised KeyError.
    """
    subject_code = await database.get_active_subject_code(user_id)
    if not subject_code:
        await message.reply_text("Pilih mata kuliah dulu dengan /matkul.")
        return None
    subject = settings.subjects.get(subject_code)
    if subject is None:
        await message.reply_text(
            f"Mata kuliah aktif ({subject_code}) tidak ada di config. Pilih ulang dengan /matkul."
        )
        return None
    return subject


def split_telegram_text(text: str, limit: int = MAX_TELEGRAM_MESSAGE) -> list[str]:
    remaining = text.strip()
    chunks: list[str] = []
    while len(remaining) > limit:
        cut_at = max(remaining.rfind("\n", 0, limit), remaining.rfind(" ", 0, limit))
        if cut_at < limit // 2:
            cut_at = limit
        piece = remaining[:cut_at].strip()
        if piece:
            chunks.append(piece)
        remaining = remaining[cut_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def reply_long(message: Any, text: str) -> None:
    for part in split_telegram_text(text):
        await message.reply_text(part, disable_web_page_preview=True)
