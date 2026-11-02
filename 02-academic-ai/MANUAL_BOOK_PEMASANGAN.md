# Manual Book — Pemasangan Academic AI di Laptop (Windows)

Panduan pasang + jalan untuk `academic_ai_v3.zip`. Estimasi: 15–30 menit
(belum termasuk download model AI).

## 1. Yang perlu disiapkan

| Kebutuhan | Keterangan |
|---|---|
| Laptop Windows 10/11 | RAM 4 GB+ disarankan |
| Python 3.11+ | Centang **Add python.exe to PATH** saat install |
| 9Router lokal | Jalan di `http://localhost:20128` (dashboard + API key) |
| Token bot Telegram | Dari `@BotFather` (hanya bila pakai bot) |
| ffmpeg | Hanya untuk fitur Video (langkah 8) |
| Internet | Untuk install paket + panggil model AI |

## 2. Ekstrak file

1. Download `academic_ai_v3.zip` dari Google Drive.
2. Klik kanan → **Extract All** ke `C:\academic_ai`.
3. Buka **Command Prompt (CMD)** di folder itu
   (ketik `cmd` di address bar Explorer → Enter).

## 3. Install aplikasi

```cmd
cd /d C:\academic_ai
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```

Tunggu sampai selesai (bisa 5–15 menit, tergantung internet).

## 4. Siapkan file `.env`

Untuk model chat di 9Router (default):

```cmd
copy .env.gratis-9router.example .env
```

Untuk Agent A/B/C di 9Router tetapi hanya Manager memakai Hermes lokal, gunakan:

```cmd
copy .env.hybrid-manager-hermes.example .env
```

Lalu isi `NINE_ROUTER_API_KEY` dan nilai rahasia lokal yang diperlukan. Untuk profil hybrid, pasang Hermes melalui Ollama (`ollama pull hermes3`) dan pastikan nama ID `MODEL_MANAGER` sesuai dengan `ollama list`.

Lalu buat token internal dan buka file `.env`:

```cmd
python -c "import secrets; print(secrets.token_urlsafe(32))"
notepad .env
```

Isi wajib di `.env`:

| Baris | Isi dengan |
|---|---|
| `NINE_ROUTER_API_KEY` | API key dari dashboard 9Router lokal |
| `MODEL_EMBEDDING` | ID persis dari `GET /v1/models/embedding` (bukan ID chat!) |
| `MODEL_PP_A` … `MODEL_DJ_C` | ID model chat dari katalog 9Router (3 specialist per matkul) |
| `MODEL_MANAGER` | ID model dari endpoint Manager: Ollama bila memakai `MANAGER_CHAT_BASE_URL`, selain itu endpoint chat biasa |
| `MANAGER_CHAT_BASE_URL` + `MANAGER_CHAT_API_KEY` | Opsional; set ke `http://localhost:11434/v1` + `ollama` untuk Manager Hermes lokal saja |
| `LOCAL_API_TOKEN` | Hasil perintah `secrets` di atas |
| `LOCAL_WEB_USERNAME` + `LOCAL_WEB_PASSWORD` | Username & password pilihanmu untuk login website |
| `TELEGRAM_BOT_TOKEN` + `ALLOWED_USER_IDS` | Hanya bila pakai bot Telegram |

Simpan, tutup Notepad.

## 5. Cek konfigurasi

```cmd
python run.py --check
python run.py --check --live
```

- `--check`: cek lokal, tanpa internet ke model.
- `--check --live`: cek ID model ke katalog chat spesialis, katalog chat Manager,
  dan katalog embedding sesuai endpoint masing-masing.
- Bila ada `TIDAK ADA`: salin ID exact dari katalog endpoint peran tersebut
  (9Router atau Ollama), ganti ID di `.env`, lalu ulangi pemeriksaan.

### 5b. Uji semua model satu per satu (wajib sekali setelah pasang)

`--check --live` hanya membaca katalog; untuk menguji completion sungguhan
(konteks, timeout, output kosong) jalankan:

```cmd
python tools/probe_models.py --patch-env
```

Skrip ini menguji SEMUA model chat + embedding + Manager (termasuk payload besar
dan output panjang), lalu menulis `hasil_uji_model.md` berisi daftar **OK/GAGAL**
per model beserta rekomendasi `MODEL_*` — dengan `--patch-env`, baris `MODEL_*`
di `.env` diperbarui otomatis hanya memakai model yang lolos uji.

## 6. Jalankan bot Telegram (opsional)

```cmd
python run.py
```

Biarkan CMD ini tetap terbuka. Test dari Telegram: `/start`, `/matkul`,
lalu kirim pertanyaan. Perintah baru: `/video`, `/jelaskan`, `/web`.

## 7. Jalankan website (CMD kedua)

Buka CMD **baru** (jangan tutup yang bot), lalu:

```cmd
cd /d C:\academic_ai
venv\Scripts\activate
python web_run.py
```

Atau double-click `start_web.bat`. Buka browser:

```
http://127.0.0.1:8765
```

Login dengan username + password dari langkah 4. Fitur web: chat, rangkuman,
kuis, upload PDF, **tombol 🎬 Video**, YouTube & voice note, Pengaturan.

### Buka dari HP (opsional)

1. Di `.env`: `WEB_ACCESS_MODE=lan`, restart `web_run.py`.
2. Bila Windows Firewall bertanya → pilih **Private networks saja**.
3. Cari IPv4 laptop: `ipconfig` → mis. `192.168.1.23`.
4. Di HP (Wi-Fi yang sama): `http://192.168.1.23:8765`.

## 8. Aktifkan fitur Video (opsional)

Syarat: `ffmpeg` + salah satu mesin suara.

```cmd
winget install --id Gyan.FFmpeg
```

Tutup-buka CMD agar PATH terbaca, lalu cek:

```cmd
ffmpeg -version
```

Mesin suara (sudah ikut `requirements.txt`, tinggal pakai):

| Mesin | Syarat | `.env` |
|---|---|---|
| edge-tts | Internet | `TTS_PROVIDER=edge` + `TTS_VOICE=id-ID-ArdiNeural` |
| Piper | File suara lokal | `TTS_PROVIDER=piper` + `TTS_VOICE=id_ID-fajri-medium` |
| Otomatis | — | `TTS_PROVIDER=auto` (coba Piper, fallback edge) |

Test: di web isi kolom Fokus/topik → tombol 🎬 Video → tunggu → putar MP4
(suara + subtitle otomatis).

## 9. Pakai harian

1. Upload PDF materi per mata kuliah (web atau bot `/tambah`).
2. Tanya jawab, minta rangkuman, buat kuis.
3. Ganti setting model/RAG dari halaman **Pengaturan** di web
   (kunci jaringan/model aktif setelah restart server).

## 10. Troubleshooting

| Gejala | Solusi |
|---|---|
| `Python was not found` | Install ulang Python, centang Add to PATH |
| `TIDAK ADA` saat `--check --live` | Ganti ID model di `.env` sesuai katalog 9Router |
| `MODEL_EMBEDDING` error | Harus dari katalog **embedding**, bukan chat |
| Web tidak bisa dibuka | Pastikan `web_run.py` jalan; cek `WEB_PORT` |
| Video gagal: `ffmpeg tidak ditemukan` | Install ffmpeg (langkah 8), tutup-buka CMD |
| Video gagal: TTS | Pasang `pip install piper-tts edge-tts`, atau set `TTS_PROVIDER=edge` + internet |
| Bot tidak balas | Cek token + ID Telegram di `ALLOWED_USER_IDS`; CMD bot harus terbuka |
| Lupa password web | Halaman Pengaturan, atau `python run.py --set-password` |

## 11. Cheat sheet perintah

```cmd
venv\Scripts\activate        :: aktifkan environment (tiap buka CMD baru)
python run.py --check --live :: cek config + model
python run.py                 :: jalankan bot Telegram
python web_run.py             :: jalankan website (atau start_web.bat)
```

Dokumen lanjutan: `README.md`, `PANDUAN_STACK_AI.md`, `PANDUAN_OLLAMA_HERMES.md`,
`PANDUAN_GDRIVE_BACKUP.md`, `PANDUAN_N8N.md`.
