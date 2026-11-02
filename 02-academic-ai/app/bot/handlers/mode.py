from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import require_authorized
from app.settings_update import (
    ANSWER_PRESETS,
    PRESET_LABELS,
    apply_answer_preset,
    detect_answer_preset,
)

PRESET_HINTS = {
    "singkat": "cepat, hemat token (top_k 3)",
    "seimbang": "standar harian (top_k 6)",
    "mendalam": "maksimal, lebih lambat (top_k 10)",
}


def mode_keyboard(current: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            ("✓ " if name == current else "") + PRESET_LABELS[name],
            callback_data=f"mode:{name}",
        )
        for name in ANSWER_PRESETS
    ]
    return InlineKeyboardMarkup([buttons])


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    message = update.effective_message
    if message is None:
        return
    settings = context.application.bot_data["settings"]
    current = detect_answer_preset(settings)
    lines = ["Pilih gaya jawaban (berlaku langsung untuk chat, ringkas, dan kuis):"]
    for name in ANSWER_PRESETS:
        mark = "✓" if name == current else "·"
        lines.append(f"{mark} {PRESET_LABELS[name]} — {PRESET_HINTS[name]}")
    await message.reply_text("\n".join(lines), reply_markup=mode_keyboard(current))


async def mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    if not await require_authorized(update, context):
        await query.answer("Unauthorized user.", show_alert=True)
        return
    await query.answer()
    name = (query.data or "").partition(":")[2]
    settings = context.application.bot_data["settings"]
    try:
        apply_answer_preset(settings, name)
    except ValueError as exc:
        await query.edit_message_text(f"Gagal mengganti mode: {exc}")
        return
    await query.edit_message_text(
        f"Mode jawaban: {PRESET_LABELS.get(name, name)}.\nBerlaku langsung dan tersimpan di .env."
    )
