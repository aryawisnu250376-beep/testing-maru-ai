from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.bot.handlers.common import require_authorized, resolve_active_subject
from app.services.video_service import VideoService

logger = logging.getLogger(__name__)


async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return
    topic = " ".join(context.args).strip() if context.args else ""
    if not topic:
        await message.reply_text("Cara pakai: /video <topik>\nContoh: /video fotosintesis")
        return
    database = context.application.bot_data["database"]
    settings = context.application.bot_data["settings"]
    subject = await resolve_active_subject(message, settings, database, user.id)
    if subject is None:
        return
    conversation_id = await database.get_active_conversation_id(user.id)
    if conversation_id is None:
        conversation_id = await database.set_active_subject(user.id, subject.code)
    question_message_id = await database.add_message(conversation_id, "user", f"/video {topic}")
    await message.reply_text(f"Menyusun video {subject.code}: {topic} ... (biasanya 1-3 menit)")
    try:
        await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_VIDEO)
        manager = context.application.bot_data["academic_manager"]
        service = VideoService(settings, manager, database)
        meta = await service.build_video(
            subject_code=subject.code,
            topic=topic,
            question_message_id=question_message_id,
        )
        await database.add_message(
            conversation_id,
            "assistant",
            f"Video: {meta['title']} ({meta['scene_count']} adegan, {meta['duration_sec']} dtk)",
        )
        with open(meta["file_path"], "rb") as handle:
            await message.reply_video(
                video=handle,
                caption=f"{meta['title']} ({meta['scene_count']} adegan)",
                supports_streaming=True,
            )
    except Exception as exc:
        logger.error("[ERROR] video task failed (%s)", type(exc).__name__)
        if isinstance(exc, ValueError):
            error_text = f"Video belum berhasil dibuat. {exc}"
        else:
            error_text = (
                "Video belum berhasil dibuat. Pastikan ffmpeg + TTS terinstal "
                "(lihat PANDUAN_STACK_AI.md). Detail teknis ada di CMD."
            )
        await database.add_message(conversation_id, "assistant", error_text)
        await message.reply_text(error_text)
