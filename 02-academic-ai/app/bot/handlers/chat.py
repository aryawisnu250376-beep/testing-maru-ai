from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.bot.handlers.common import reply_long, require_authorized, resolve_active_subject
from app.manager.manager import format_telegram_answer

logger = logging.getLogger(__name__)


async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None or not message.text:
        return

    database = context.application.bot_data["database"]
    settings = context.application.bot_data["settings"]
    subject = await resolve_active_subject(message, settings, database, user.id)
    if subject is None:
        return
    subject_code = subject.code
    conversation_id = await database.get_active_conversation_id(user.id)
    if conversation_id is None:
        conversation_id = await database.set_active_subject(user.id, subject_code)

    history = await database.get_recent_messages(conversation_id, limit=8)
    question_message_id = await database.add_message(conversation_id, "user", message.text)
    model_id = ""
    try:
        logger.info("[INFO] Subject: %s", subject_code)
        await context.bot.send_chat_action(
            chat_id=message.chat_id,
            action=ChatAction.TYPING,
        )
        manager = context.application.bot_data["academic_manager"]
        result = await manager.answer(
            subject_code,
            message.text,
            history,
            question_message_id=question_message_id,
            user_id=update.effective_user.id if update.effective_user else None,
        )
        model_id = result.manager_model or model_id
        formatted = format_telegram_answer(result)
        await database.add_message(conversation_id, "assistant", formatted)
        await reply_long(message, formatted)
    except Exception as exc:
        logger.error(
            "[ERROR] Academic RAG request failed for subject %s (%s)",
            subject_code,
            type(exc).__name__,
        )
        if isinstance(exc, ValueError):
            error_text = f"Maaf, pertanyaan belum berhasil diproses. {exc}"
        else:
            error_text = (
                "Maaf, pertanyaan belum berhasil diproses. Cek konfigurasi model untuk mata kuliah aktif, "
                "model embedding, dan apakah 9Router masih berjalan. Detail teknis ada di CMD."
            )
        await database.add_message(conversation_id, "assistant", error_text)
        await database.record_agent_run(
            question_message_id=question_message_id,
            subject_code=subject_code,
            agent_name="UNHANDLED_MANAGER_ERROR",
            model_id=model_id,
            status="ERROR",
            result={"error_type": type(exc).__name__},
        )
        await message.reply_text(error_text)
