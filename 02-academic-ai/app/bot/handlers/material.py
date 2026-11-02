from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import require_authorized, resolve_active_subject
from app.bot.handlers.subject import subject_keyboard

logger = logging.getLogger(__name__)


async def add_material_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    message = update.effective_message
    if message:
        await message.reply_text(
            "Pilih mata kuliah untuk PDF ini. Setelah itu kirim file PDF sebagai dokumen.",
            reply_markup=subject_keyboard(context, "upload"),
        )


async def upload_subject_callback(
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
    subject_code = (query.data or "").partition(":")[2].upper()
    settings = context.application.bot_data["settings"]
    subject = settings.subjects.get(subject_code)
    if subject is None:
        await query.edit_message_text(
            "Mata kuliah tidak dikenal. Kirim /tambahmateri untuk mencoba lagi."
        )
        return

    context.user_data["pending_upload_subject"] = subject_code
    await query.edit_message_text(
        f"Kirim satu file PDF untuk {subject.code} — {subject.name}.\n"
        "File lama dengan nama yang sama tidak akan ditimpa."
    )


async def materials_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return

    settings = context.application.bot_data["settings"]
    database = context.application.bot_data["database"]
    subject = await resolve_active_subject(message, settings, database, user.id)
    if subject is None:
        return
    subject_code = subject.code
    documents = await database.list_documents(subject_code)
    if not documents:
        await message.reply_text(
            f"Belum ada PDF untuk {subject.code} — {subject.name}.\n"
            "Gunakan /tambahmateri untuk mengunggah materi."
        )
        return

    lines = [f"Mata kuliah aktif: {subject.code} — {subject.name}", "Daftar PDF:"]
    for index, document in enumerate(documents, start=1):
        lines.append(
            f"{index}. {document['original_name']} ({document['page_count']} halaman) "
            f"[ID {str(document['id'])[:8]}]"
        )
    await message.reply_text("\n".join(lines))


async def receive_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    message = update.effective_message
    if message is None or message.document is None:
        return

    subject_code = context.user_data.get("pending_upload_subject")
    if not subject_code:
        await message.reply_text("Untuk menambahkan PDF, jalankan /tambahmateri terlebih dahulu.")
        return

    document = message.document
    original_name = document.file_name or "materi.pdf"
    if not original_name.lower().endswith(".pdf"):
        await message.reply_text(
            "File harus berekstensi .pdf. Kirim PDF atau gunakan /tambahmateri ulang."
        )
        return

    settings = context.application.bot_data["settings"]
    if document.file_size and document.file_size > settings.max_pdf_bytes:
        max_mb = settings.max_pdf_bytes // (1024 * 1024)
        await message.reply_text(f"Ukuran PDF terlalu besar. Batas awal adalah {max_mb} MB.")
        return

    context.user_data.pop("pending_upload_subject", None)
    subject = settings.subjects.get(subject_code)
    if subject is None:
        await message.reply_text(
            "Mata kuliah upload tidak dikenal di config. Jalankan /tambahmateri ulang."
        )
        return
    await message.reply_text(
        f"PDF diterima untuk {subject.code}. Sedang menyimpan, mengekstrak halaman, "
        "dan membuat embedding melalui 9Router."
    )

    try:
        telegram_file = await context.bot.get_file(document.file_id)

        async def download_to_path(path: Path) -> None:
            await telegram_file.download_to_drive(custom_path=path)

        service = context.application.bot_data["material_service"]
        result = await service.ingest_pdf(
            subject_code=subject_code,
            original_name=original_name,
            uploaded_by=update.effective_user.id,
            download_to_path=download_to_path,
        )
    except Exception as exc:
        logger.error(
            "[ERROR] PDF upload/index failed for subject %s (%s)",
            subject_code,
            type(exc).__name__,
        )
        user_hint = str(exc) if isinstance(exc, ValueError) else "Detail teknis ada di CMD."
        await message.reply_text(
            "PDF belum berhasil diproses. Periksa model embedding, koneksi 9Router, "
            f"atau format PDF. {user_hint}"
        )
        return

    await message.reply_text(
        "✅ Materi tersimpan dan terindeks.\n"
        f"Mata kuliah: {subject.code} — {subject.name}\n"
        f"PDF: {result['original_name']}\n"
        f"Halaman teks: {result['page_count']}\n"
        f"Potongan materi: {result['chunk_count']}\n\n"
        "Gunakan /materi untuk melihat daftar atau langsung tanyakan isi PDF."
    )
