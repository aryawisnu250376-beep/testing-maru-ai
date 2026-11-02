from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import require_authorized


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    message = update.effective_message
    if message:
        await message.reply_text(
            "Selamat datang di Academic AI.\n\n"
            "Pilih mata kuliah dengan /matkul dan unggah PDF memakai /tambahmateri. "
            "Researcher mencari potongan materi pada subject aktif, Librarian memeriksa dokumen/halaman, "
            "lalu dua AI specialist menjawab secara independen dan AI Manager memverifikasi bukti.\n\n"
            "Jika bukti tidak cukup, bot menandai jawaban UNVERIFIED; halaman tidak akan ditebak.\n"
            "Ketik /help untuk perintah yang tersedia."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_authorized(update, context):
        return
    message = update.effective_message
    if message:
        await message.reply_text(
            "Perintah Academic AI:\n"
            "/start — mulai\n"
            "/help — bantuan\n"
            "/matkul — pilih mata kuliah aktif\n"
            "/tambahmateri — unggah PDF ke mata kuliah pilihan\n"
            "/materi — daftar PDF mata kuliah aktif\n"
            "/ringkas — rangkum materi terindeks pada mata kuliah aktif\n"
            "/kuis [topik] — buat 10 soal dari materi aktif\n"
            "/hapusmateri — pilih lalu konfirmasi penghapusan PDF\n"
            "/status — status materi/model aktif\n"
            "/reset — mulai percakapan baru tanpa menghapus materi\n\n"
            "Setelah memilih mata kuliah, kirim pertanyaan lewat chat biasa. Hasil yang belum didukung "
            "oleh bukti PDF ditandai UNVERIFIED. Model dan kuota gratis bergantung pada provider yang "
            "kamu hubungkan di 9Router."
        )
