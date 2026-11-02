from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.bot.handlers.common import reply_long, require_authorized, resolve_active_subject
from app.manager.manager import format_quiz_answer, format_telegram_answer

logger = logging.getLogger(__name__)


async def _run_subject_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    task_mode: str,
) -> None:
    if not await require_authorized(update, context):
        return
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
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

    topic = " ".join(context.args).strip() if context.args else ""
    if task_mode == "summary":
        request_text = "/ringkas — buat rangkuman materi mata kuliah" + (
            f": {topic}" if topic else ""
        )
    else:
        request_text = "/kuis" + (f" {topic}" if topic else "")
    question_message_id = await database.add_message(conversation_id, "user", request_text)
    try:
        await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
        manager = context.application.bot_data["academic_manager"]
        if task_mode == "summary":
            result = await manager.summarize(
                subject_code,
                question_message_id=question_message_id,
                topic=topic,
            )
            formatted = format_telegram_answer(result)
        else:
            result = await manager.quiz(
                subject_code,
                question_message_id=question_message_id,
                topic=" ".join(context.args).strip() if context.args else "",
            )
            formatted = format_quiz_answer(result)
        await database.add_message(conversation_id, "assistant", formatted)
        await reply_long(message, formatted)
    except Exception as exc:
        logger.error("[ERROR] %s task failed (%s)", task_mode, type(exc).__name__)
        if isinstance(exc, ValueError):
            error_text = f"Permintaan belum berhasil diproses. {exc}"
        else:
            error_text = (
                "Permintaan belum berhasil diproses. Periksa apakah PDF sudah diunggah, "
                "MODEL_EMBEDDING cocok dengan index, dan model 9Router tersedia. Detail teknis ada di CMD."
            )
        await database.add_message(conversation_id, "assistant", error_text)
        await message.reply_text(error_text)


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_subject_task(update, context, task_mode="summary")


async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_subject_task(update, context, task_mode="quiz")
