from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import require_authorized


def subject_keyboard(
    context: ContextTypes.DEFAULT_TYPE, callback_prefix: str
) -> InlineKeyboardMarkup:
    settings = context.application.bot_data["settings"]
    buttons = [
        InlineKeyboardButton(
            f"{subject.code} — {subject.name}",
            callback_data=f"{callback_prefix}:{subject.code}",
        )
        for subject in settings.subjects.values()
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


async def matkul_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    message = update.effective_message
    if message:
        await message.reply_text(
            "Pilih mata kuliah aktif. Knowledge base tiap subject dipisahkan:",
            reply_markup=subject_keyboard(context, "subject"),
        )


async def subject_selection_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    if query is None:
        return
    if not await require_authorized(update, context):
        await query.answer("Unauthorized user.", show_alert=True)
        return

    await query.answer()
    value = query.data or ""
    subject_code = value.partition(":")[2].upper()
    settings = context.application.bot_data["settings"]
    subject = settings.subjects.get(subject_code)
    if subject is None:
        await query.edit_message_text(
            "Mata kuliah tidak dikenal. Kirim /matkul untuk mencoba lagi."
        )
        return

    database = context.application.bot_data["database"]
    await database.set_active_subject(update.effective_user.id, subject_code)
    await query.edit_message_text(
        f"Mata kuliah aktif: {subject.code} — {subject.name}.\n"
        "Materi yang dicari hanya berasal dari mata kuliah ini."
    )
