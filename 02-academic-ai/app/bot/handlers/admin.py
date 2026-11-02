from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import require_authorized


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return
    database = context.application.bot_data["database"]
    conversation_id = await database.reset_conversation(user.id)
    if conversation_id is None:
        await message.reply_text("Pilih mata kuliah dulu dengan /matkul.")
        return
    await message.reply_text(
        "Percakapan baru dimulai. Arsip percakapan lama dan materi PDF tetap tersimpan di SQLite."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return

    settings = context.application.bot_data["settings"]
    database = context.application.bot_data["database"]
    subject_code = await database.get_active_subject_code(user.id)
    if not subject_code:
        subject_line = "Mata kuliah aktif: belum dipilih"
        document_count = chunk_count = 0
        agent_a_line = agent_b_line = "AI specialist: pilih mata kuliah untuk melihat model"
    else:
        subject = settings.subjects.get(subject_code)
        if subject is None:
            subject_line = (
                f"Mata kuliah aktif: {subject_code} (tidak ada di config — pilih ulang /matkul)"
            )
            document_count = chunk_count = 0
            agent_a_line = agent_b_line = "AI specialist: pilih mata kuliah untuk melihat model"
        else:
            document_count, chunk_count = await database.get_subject_counts(subject_code)
            subject_line = f"Mata kuliah aktif: {subject.code} — {subject.name}"
            lines = []
            for slot, label, suffix in (("agent_a", "Agent A", "A"), ("agent_b", "Agent B", "B")):
                try:
                    lines.append(f"{label}: {settings.model_for(subject_code, slot)}")
                except ValueError:
                    lines.append(f"{label}: belum diisi (MODEL_{subject_code}_{suffix})")
            agent_a_line, agent_b_line = lines

    embedding_line = (
        f"Embedding model: {settings.embedding_model}"
        if settings.embedding_model
        else "Embedding model: belum diisi (pilih ID dari /v1/models/embedding)"
    )
    manager_endpoint = getattr(settings, "manager_chat_base_url", "") or settings.chat_base_url
    manager_line = f"AI Manager: {settings.manager_model or 'belum diisi'} ({manager_endpoint})"
    await message.reply_text(
        "Academic AI — status lokal\n"
        f"{subject_line}\n"
        f"PDF pada subject aktif: {document_count}\n"
        f"Chunk terindeks: {chunk_count}\n"
        f"{agent_a_line}\n"
        f"{agent_b_line}\n"
        f"{manager_line}\n"
        f"{embedding_line}\n"
        "Tim Researcher + Librarian: pencarian subject-scoped dan cek sumber lokal\n"
        "Verifier: dua draft independen; maksimal dua ronde revisi"
    )
