from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import require_authorized, resolve_active_subject

logger = logging.getLogger(__name__)


def _short_label(value: str, limit: int = 42) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


async def delete_material_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    documents = await database.list_documents(subject_code)
    if not documents:
        await message.reply_text("Tidak ada PDF pada mata kuliah aktif untuk dihapus.")
        return

    buttons = [
        [
            InlineKeyboardButton(
                f"{_short_label(str(document['original_name']))} · {str(document['id'])[:8]}",
                callback_data=f"delete-select:{subject_code}:{document['id']}",
            )
        ]
        for document in documents
    ]
    await message.reply_text(
        f"Pilih PDF yang ingin dihapus dari {subject.code} — {subject.name}. "
        "Tindakan ini menghapus file lokal, metadata, dan vektor indeks.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def delete_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    if not await require_authorized(update, context):
        await query.answer("Unauthorized user.", show_alert=True)
        return
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) != 3:
        await query.edit_message_text("Pilihan hapus tidak valid.")
        return
    subject_code, document_id = parts[1].upper(), parts[2]
    settings = context.application.bot_data["settings"]
    subject = settings.subjects.get(subject_code)
    database = context.application.bot_data["database"]
    document = await database.get_document(subject_code, document_id)
    if subject is None or document is None:
        await query.edit_message_text("PDF tidak ditemukan. Daftar materi mungkin sudah berubah.")
        return
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Ya, hapus PDF",
                    callback_data=f"delete-confirm:{subject_code}:{document_id}",
                ),
                InlineKeyboardButton("Batal", callback_data="delete-cancel"),
            ]
        ]
    )
    await query.edit_message_text(
        f"Konfirmasi hapus:\n{document['original_name']}\n"
        f"Mata kuliah: {subject.code} — {subject.name}\n\n"
        "PDF dan embedding-nya akan dihapus dari komputer ini. Tindakan tidak bisa dibatalkan.",
        reply_markup=keyboard,
    )


async def delete_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    if not await require_authorized(update, context):
        await query.answer("Unauthorized user.", show_alert=True)
        return
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) != 3:
        await query.edit_message_text("Pilihan hapus tidak valid.")
        return
    subject_code, document_id = parts[1].upper(), parts[2]
    service = context.application.bot_data["material_service"]
    try:
        record = await service.delete_pdf(subject_code=subject_code, document_id=document_id)
    except Exception as exc:
        logger.error("[ERROR] Material deletion failed (%s)", type(exc).__name__)
        await query.edit_message_text(
            "PDF belum berhasil dihapus sepenuhnya. Periksa log di CMD; jangan unggah ulang "
            "sebelum memastikan daftar melalui /materi."
        )
        return
    if record is None:
        await query.edit_message_text("PDF sudah tidak ada atau telah dihapus.")
    else:
        await query.edit_message_text(
            f"✅ PDF {record['original_name']} dan index-nya telah dihapus."
        )


async def delete_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    if not await require_authorized(update, context):
        await query.answer("Unauthorized user.", show_alert=True)
        return
    await query.answer("Dibatalkan.")
    await query.edit_message_text("Penghapusan dibatalkan; PDF tetap tersimpan.")
