from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.bot.handlers.common import reply_long, require_authorized, resolve_active_subject
from app.knowledge.fabric_patterns import render as render_pattern
from app.manager.manager import format_telegram_answer
from app.services.webfetch import summarize_web

logger = logging.getLogger(__name__)


async def jelaskan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ELI5 explanation grounded in PDFs (Fabric-inspired pattern)."""
    if not await require_authorized(update, context):
        return
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return
    topic = " ".join(context.args).strip() if context.args else ""
    if not topic:
        await message.reply_text("Cara pakai: /jelaskan <topik>\nContoh: /jelaskan inflasi")
        return
    database = context.application.bot_data["database"]
    settings = context.application.bot_data["settings"]
    subject = await resolve_active_subject(message, settings, database, user.id)
    if subject is None:
        return
    conversation_id = await database.get_active_conversation_id(user.id)
    if conversation_id is None:
        conversation_id = await database.set_active_subject(user.id, subject.code)
    question_message_id = await database.add_message(conversation_id, "user", f"/jelaskan {topic}")
    try:
        await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
        manager = context.application.bot_data["academic_manager"]
        prompt = render_pattern("explain_simple", topic=topic)
        result = await manager.answer(
            subject.code,
            prompt,
            [],
            question_message_id=question_message_id,
            user_id=user.id,
        )
        formatted = format_telegram_answer(result)
        await database.add_message(conversation_id, "assistant", formatted)
        await reply_long(message, formatted)
    except Exception as exc:
        logger.error("[ERROR] jelaskan task failed (%s)", type(exc).__name__)
        error_text = (
            f"Penjelasan belum berhasil dibuat. {exc}"
            if isinstance(exc, ValueError)
            else "Penjelasan belum berhasil dibuat. Detail teknis ada di CMD."
        )
        await database.add_message(conversation_id, "assistant", error_text)
        await message.reply_text(error_text)


async def web_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Summarize the top web result (explicit user intent; labeled as web source)."""
    if not await require_authorized(update, context):
        return
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await message.reply_text("Cara pakai: /web <kata kunci>\nContoh: /web fotosintesis")
        return
    database = context.application.bot_data["database"]
    settings = context.application.bot_data["settings"]
    subject = await resolve_active_subject(message, settings, database, user.id)
    if subject is None:
        return
    conversation_id = await database.get_active_conversation_id(user.id)
    if conversation_id is None:
        conversation_id = await database.set_active_subject(user.id, subject.code)
    await database.add_message(conversation_id, "user", f"/web {query}")
    try:
        await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)
        manager = context.application.bot_data["academic_manager"]
        result = await summarize_web(manager, query)
        formatted = format_telegram_answer(result)
        await database.add_message(conversation_id, "assistant", formatted)
        await reply_long(message, formatted)
    except Exception as exc:
        logger.error("[ERROR] web task failed (%s)", type(exc).__name__)
        error_text = (
            f"Ringkasan web belum berhasil dibuat. {exc}"
            if isinstance(exc, ValueError)
            else "Ringkasan web belum berhasil dibuat. Detail teknis ada di CMD."
        )
        await database.add_message(conversation_id, "assistant", error_text)
        await message.reply_text(error_text)
