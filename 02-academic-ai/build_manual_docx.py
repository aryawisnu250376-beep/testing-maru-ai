"""Bangun MANUAL_BOOK_PEMASANGAN.docx (satu manual utuh, label WAJIB/OPSIONAL)."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.shared import Pt

CODE_FONT = "Consolas"
WAJIB = "[WAJIB]"
OPSIONAL = "[OPSIONAL]"


def h1(doc: Document, text: str) -> None:
    doc.add_heading(text, level=1)


def h2(doc: Document, text: str) -> None:
    doc.add_heading(text, level=2)


def p(doc: Document, text: str) -> None:
    doc.add_paragraph(text)


def bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def numbers(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Number")


def code(doc: Document, text: str) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = CODE_FONT
    run.font.size = Pt(9)


def table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    grid = doc.add_table(rows=1 + len(rows), cols=len(headers))
    grid.style = "Table Grid"
    for i, head in enumerate(headers):
        grid.rows[0].cells[i].text = head
    for r, row in enumerate(rows, start=1):
        for i, val in enumerate(row):
            grid.rows[r].cells[i].text = val
    doc.add_paragraph("")


def build() -> None:
    doc = Document()
    doc.add_heading("Manual Book — Pemasangan Academic AI di Laptop (Windows)", level=0)
    p(doc, "Paket: academic_ai_v3.zip  |  8 Oktober 2026  |  Satu dokumen utuh — tidak perlu buka file lain.")

    h1(doc, "0. Jalur Cepat — Yang Penting Saja")
    p(doc, "Cukup kerjakan ini aplikasi sudah jalan. Sisanya boleh skip.")
    numbers(doc, [
        "Bab 1: siapkan Python + 9Router.",
        "Bab 2: ekstrak zip ke C:\\academic_ai.",
        "Bab 3: install (venv + requirements).",
        "Bab 4: isi .env (API key, MODEL_*, token, username/password).",
        "Bab 5: cek config sampai bersih.",
        "Bab 7: jalankan web, buka http://127.0.0.1:8765.",
    ])
    table(doc, ["Bab", "Status", "Boleh skip?"], [
        ["1–5, 7", "WAJIB", "Tidak — inti pemasangan"],
        ["6 Bot Telegram", "OPSIONAL", "Ya, bila cukup pakai web"],
        ["7.1 HP, 8 Video, 12 Drive, 13 Opsi lain", "OPSIONAL", "Ya"],
        ["9–11", "Panduan pakai", "Dibaca saat perlu"],
    ])

    h1(doc, f"1. Yang Perlu Disiapkan {WAJIB}")
    table(doc, ["Kebutuhan", "Status", "Keterangan"], [
        ["Laptop Windows 10/11", "WAJIB", "RAM 4 GB+ disarankan"],
        ["Python 3.11+", "WAJIB", "Centang Add python.exe to PATH saat install"],
        ["9Router lokal", "WAJIB", "Jalan di http://localhost:20128 (dashboard + API key)"],
        ["Internet", "WAJIB", "Untuk install paket + panggil model AI"],
        ["Token bot Telegram", "OPSIONAL", "Dari @BotFather, hanya bila pakai bot (Bab 6)"],
        ["ffmpeg", "OPSIONAL", "Hanya untuk fitur Video (Bab 8)"],
    ])

    h1(doc, f"2. Ekstrak File {WAJIB}")
    numbers(doc, [
        "Download academic_ai_v3.zip dari Google Drive.",
        "Klik kanan → Extract All ke C:\\academic_ai.",
        "Buka Command Prompt (CMD) di folder itu (ketik cmd di address bar Explorer → Enter).",
    ])

    h1(doc, f"3. Install Aplikasi {WAJIB}")
    code(doc, "cd /d C:\\academic_ai\npython -m venv venv\nvenv\\Scripts\\activate\npython -m pip install -r requirements.txt")
    p(doc, "Tunggu sampai selesai (5–15 menit, tergantung internet).")

    h1(doc, f"4. Siapkan File .env {WAJIB}")
    p(doc, "Pilih salah satu profil konfigurasi:")
    code(doc, "9Router saja: copy .env.gratis-9router.example .env\nHybrid (A/B 9Router + Manager Hermes): copy .env.hybrid-manager-hermes.example .env")
    p(doc, "Jika memilih hybrid, instal Ollama dan pastikan ID MODEL_MANAGER cocok dengan ollama list. Lalu buat token internal dan buka file .env:")
    code(doc, 'python -c "import secrets; print(secrets.token_urlsafe(32))"\nnotepad .env')
    table(doc, ["Baris", "Status", "Isi dengan"], [
        ["NINE_ROUTER_API_KEY", "WAJIB", "API key dari dashboard 9Router lokal"],
        ["MODEL_EMBEDDING", "WAJIB", "ID persis dari GET /v1/models/embedding (bukan ID chat!)"],
        ["MODEL_PP_A … MODEL_DJ_B", "WAJIB", "ID model chat dari katalog spesialis 9Router"],
        ["MODEL_MANAGER", "WAJIB", "ID dari katalog Manager (Ollama bila MANAGER_CHAT_* diaktifkan)"],
        ["MANAGER_CHAT_BASE_URL + MANAGER_CHAT_API_KEY", "OPSIONAL", "http://localhost:11434/v1 + ollama untuk Hermes lokal saja"],
        ["LOCAL_API_TOKEN", "WAJIB", "Hasil perintah secrets di atas"],
        ["LOCAL_WEB_USERNAME + LOCAL_WEB_PASSWORD", "WAJIB", "Username & password pilihanmu untuk login website"],
        ["TELEGRAM_BOT_TOKEN + ALLOWED_USER_IDS", "OPSIONAL", "Hanya bila pakai bot (Bab 6)"],
    ])

    h1(doc, f"5. Cek Konfigurasi {WAJIB}")
    code(doc, "python run.py --check\npython run.py --check --live")
    bullets(doc, [
        "--check: cek lokal, tanpa internet ke model.",
        "--check --live: cek ID spesialis, Manager, dan embedding ke katalog endpoint masing-masing.",
        "Bila ada TIDAK ADA: ganti ID di .env dengan ID exact dari katalog endpoint sesuai perannya.",
    ])

    h1(doc, f"6. Jalankan Bot Telegram {OPSIONAL}")
    p(doc, "Skip bab ini bila cukup pakai website.")
    code(doc, "python run.py")
    p(doc, "Biarkan CMD ini tetap terbuka. Test dari Telegram: /start, /matkul, lalu kirim pertanyaan. Perintah baru: /video, /jelaskan, /web.")

    h1(doc, f"7. Jalankan Website {WAJIB}")
    p(doc, "Buka CMD baru (jangan tutup yang bot bila dipakai), lalu:")
    code(doc, "cd /d C:\\academic_ai\nvenv\\Scripts\\activate\npython web_run.py")
    p(doc, "Atau double-click start_web.bat. Buka browser ke http://127.0.0.1:8765 dan login dengan username + password dari Bab 4. Fitur web: chat, rangkuman, kuis, upload PDF, tombol Video, YouTube & voice note, Pengaturan.")
    h2(doc, f"7.1 Buka dari HP {OPSIONAL}")
    numbers(doc, [
        "Di .env: WEB_ACCESS_MODE=lan, restart web_run.py.",
        "Bila Windows Firewall bertanya → pilih Private networks saja.",
        "Cari IPv4 laptop: ipconfig → mis. 192.168.1.23.",
        "Di HP (Wi-Fi yang sama): http://192.168.1.23:8765.",
    ])

    h1(doc, f"8. Aktifkan Fitur Video {OPSIONAL}")
    p(doc, "Syarat: ffmpeg + salah satu mesin suara.")
    code(doc, "winget install --id Gyan.FFmpeg")
    p(doc, "Tutup-buka CMD agar PATH terbaca, lalu cek: ffmpeg -version")
    table(doc, ["Mesin", "Syarat", ".env"], [
        ["edge-tts", "Internet", "TTS_PROVIDER=edge + TTS_VOICE=id-ID-ArdiNeural"],
        ["Piper", "File suara lokal", "TTS_PROVIDER=piper + TTS_VOICE=id_ID-fajri-medium"],
        ["Otomatis", "—", "TTS_PROVIDER=auto (coba Piper, fallback edge)"],
    ])
    p(doc, "Test: di web isi kolom Fokus/topik → tombol Video → tunggu → putar MP4 (suara + subtitle otomatis).")

    h1(doc, "9. Pakai Harian")
    numbers(doc, [
        "Upload PDF materi per mata kuliah (web atau bot /tambah).",
        "Tanya jawab, minta rangkuman, buat kuis.",
        "Ganti setting model/RAG dari halaman Pengaturan di web (kunci jaringan/model aktif setelah restart server).",
    ])

    h1(doc, "10. Troubleshooting")
    table(doc, ["Gejala", "Solusi"], [
        ["Python was not found", "Install ulang Python, centang Add to PATH"],
        ["TIDAK ADA saat --check --live", "Cek katalog endpoint peran itu (9Router untuk Agent A/B; Ollama untuk Manager bila override aktif)"],
        ["MODEL_EMBEDDING error", "Harus dari katalog embedding, bukan chat"],
        ["Web tidak bisa dibuka", "Pastikan web_run.py jalan; cek WEB_PORT"],
        ["Video gagal: ffmpeg tidak ditemukan", "Install ffmpeg (Bab 8), tutup-buka CMD"],
        ["Video gagal: TTS", "pip install piper-tts edge-tts, atau TTS_PROVIDER=edge + internet"],
        ["Bot tidak balas", "Cek token + ID Telegram di ALLOWED_USER_IDS; CMD bot harus terbuka"],
        ["Lupa password web", "Halaman Pengaturan, atau python run.py --set-password"],
    ])

    h1(doc, "11. Cheat Sheet Perintah")
    code(doc, "venv\\Scripts\\activate        :: aktifkan environment (tiap buka CMD baru)\npython run.py --check --live :: cek config + model\npython run.py                 :: jalankan bot Telegram\npython web_run.py             :: jalankan website (atau start_web.bat)")

    h1(doc, f"12. Workflow Kirim ke Drive (Backup Otomatis) + Cara Setup {OPSIONAL}")
    p(doc, "Setiap PDF yang berhasil di-upload (lewat web ATAU bot Telegram) otomatis dibackup ke Google Drive dengan struktur folder per mata kuliah. File lokal tetap dipakai untuk RAG; Drive hanya cadangan.")
    h2(doc, "12.1 Alur Workflow")
    code(doc, "Upload PDF (web / bot)\n  → Simpan lokal + masuk RAG (wajib sukses)\n  → Backup otomatis ke Drive: Academic_AI/<KODE_MATKUL>/<nama file>\n  → Upload ulang konten identik (sha256 sama) dilewati, tidak dobel\nHapus materi (/hapusmateri / web)\n  → Hapus lokal + hapus salinan Drive-nya")
    p(doc, "Backup bersifat best-effort: kalau gagal (internet putus, token kedaluwarsa), upload lokal tetap sukses dan peringatan dicatat di log. Aplikasi memakai scope drive.file — hanya bisa mengelola file yang ia buat sendiri, tidak bisa melihat/mengubah file Drive lain milikmu.")
    h2(doc, "12.2 Setup — Buat Kredensial OAuth (Sekali Saja)")
    numbers(doc, [
        "Buka https://console.cloud.google.com/ dan login dengan akun Google penampung backup.",
        "Buat project baru (misalnya academic-ai-backup).",
        "Aktifkan Google Drive API: APIs & Services → Library → Google Drive API → Enable.",
        "APIs & Services → OAuth consent screen: User type External, isi nama aplikasi + email. Pada langkah Test users, tambahkan email kamu sendiri (wajib selama status Testing).",
        "APIs & Services → Credentials → Create Credentials → OAuth client ID: Application type Desktop app. Unduh JSON-nya.",
        "Simpan file JSON itu sebagai data/drive_credentials.json di folder project (atau atur path via GDRIVE_CREDENTIALS_FILE di .env).",
    ])
    h2(doc, "12.3 Setup — Otorisasi (Sekali Saja)")
    p(doc, "Di CMD folder project (venv aktif):")
    code(doc, "python run.py --drive-auth")
    p(doc, 'Browser terbuka → login → izinkan akses. Kalau muncul peringatan "Google hasn\'t verified this app", klik Advanced → Go to … (unsafe) — wajar untuk aplikasi Testing milik sendiri. Token tersimpan di data/drive_token.json (jangan bagikan file ini). Token di-refresh otomatis; kalau refresh gagal, jalankan ulang perintah di atas.')
    h2(doc, "12.4 Setup — Nyalakan Backup")
    p(doc, "Di .env:")
    code(doc, "GDRIVE_BACKUP_ENABLED=true\nGDRIVE_CREDENTIALS_FILE=data/drive_credentials.json\nGDRIVE_TOKEN_FILE=data/drive_token.json\nGDRIVE_ROOT_FOLDER=Academic_AI")
    p(doc, "Restart bot/web. Upload satu PDF percobaan, lalu cek folder Academic_AI di Google Drive.")
    h2(doc, "12.5 Troubleshooting Backup Drive")
    table(doc, ["Gejala", "Penyebab Umum", "Solusi"], [
        ["File kredensial Google tidak ditemukan", "JSON belum disimpan", "Simpan sebagai data/drive_credentials.json"],
        ["Token Drive belum ada", "Belum otorisasi", "python run.py --drive-auth"],
        ["access_denied / Error 403 di browser", "Email belum jadi test user", "Tambahkan email di OAuth consent → Test users"],
        ["Backup dilewati + [WARN] di log", "Internet/token bermasalah", "Cek koneksi; otorisasi ulang bila perlu"],
        ["Folder ganda Academic_AI", "Root diganti nama/diubah", "Samakan GDRIVE_ROOT_FOLDER atau hapus folder ganda manual"],
    ])

    h1(doc, f"13. Opsi Lain (Singkat) {OPSIONAL}")
    h2(doc, "13.1 Hermes/Ollama Lokal + 9Router")
    numbers(doc, [
        "Install Ollama, lalu jalankan: ollama pull hermes3.",
        "Untuk Agent A/B di 9Router + Manager Hermes, copy .env.hybrid-manager-hermes.example .env; untuk semua chat lokal gunakan .env.ollama-hermes.example.",
        "Isi key 9Router, samakan MODEL_MANAGER dengan ollama list, lalu verifikasi python run.py --check --live.",
    ])
    h2(doc, "13.2 Otomatisasi n8n")
    p(doc, "API lokal (/api/jobs, /api/web, dsb.) bisa dipanggil dari workflow n8n — contoh siap impor ada di folder n8n/ (termasuk Trend Briefing mingguan ke Telegram).")
    h2(doc, "13.3 Pengaturan Model/RAG")
    p(doc, "RAG_MODE (vector/tree/hybrid), RAG_TOP_K, MODEL_*, dan kunci lain bisa diubah dari halaman Pengaturan di web atau langsung di .env. Perubahan model/jaringan aktif setelah restart server.")

    h1(doc, f"14. AI Teknisi (Perbaikan Bug Otomatis) {OPSIONAL}")
    p(doc, "AI Teknisi adalah montir AI di dalam aplikasi: memantau data/logs/*.log, memeriksa kesehatan model/endpoint/timeout, lalu memperbaiki masalah secara otomatis.")
    h2(doc, "14.1 Mode Kerja")
    bullets(doc, [
        "Mode aman (TECHNICIAN_MODE=safe): perbaikan konfigurasi otomatis (model tidak ditemukan diganti dari katalog aktif, timeout dinaikkan) — tanpa menyentuh kode program.",
        "Mode penuh (TECHNICIAN_MODE=full): AI Manager juga menganalisis error lalu menambal kode sumber; file asli dibackup ke data/patches/, diuji otomatis dengan pytest, dan langsung di-rollback bila tes gagal.",
        "Pemindaian berjalan otomatis tiap TECHNICIAN_INTERVAL_MIN menit (default 30), plus tombol Pindai Sekarang dan Rollback Terakhir di panel 05 AI Teknisi pada web.",
    ])
    h2(doc, "14.2 Konfigurasi .env")
    code(doc, "TECHNICIAN_ENABLED=true\nTECHNICIAN_AUTO=true\nTECHNICIAN_MODE=safe\nTECHNICIAN_INTERVAL_MIN=30\nTECHNICIAN_CODE_FIX=true")
    h2(doc, "14.3 Catatan Penting")
    bullets(doc, [
        "Setiap perbaikan dicatat di data/fix_journal.jsonl (jejak audit siapa memperbaiki apa dan kapan).",
        "Perubahan kode selalu diuji pytest lebih dulu; gagal tes = otomatis kembali seperti semula.",
        "Tetap disarankan menjalankan python tools/probe_models.py bila mengganti endpoint/akun AI.",
    ])

    output_path = Path(__file__).with_name("MANUAL_BOOK_PEMASANGAN.docx")
    doc.save(output_path)
    print("DOCX_DONE")


if __name__ == "__main__":
    build()
