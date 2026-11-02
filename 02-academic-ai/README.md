# AI ACADEMIC — Bot Telegram dan Website Lokal

Project bantuan belajar berbasis PDF untuk Windows 10/11. Bot Telegram dan website lokal memakai subject knowledge base yang sama, SQLite, persistent vector index, dan provider AI OpenAI-compatible **9Router**. Tidak memerlukan VPS atau Docker untuk berjalan di komputer sendiri. Provider default adalah 9Router, tetapi tiap peran model (chat, embedding, STT) dapat diarahkan ke endpoint OpenAI-compatible lain seperti **Ollama/Hermes** lokal — lihat `PANDUAN_OLLAMA_HERMES.md`. PDF yang di-upload juga bisa dibackup otomatis ke Google Drive per mata kuliah (`PANDUAN_GDRIVE_BACKUP.md`), dan API lokal dapat diorkestrasi n8n (`PANDUAN_N8N.md`, folder `n8n/`).

> **Belum ada uji live Telegram atau 9Router dari workspace ini.** Tes otomatis menggunakan mock/fake provider untuk memeriksa perilaku aplikasi tanpa mengirim pertanyaan atau dokumen ke layanan luar.

## Fitur saat ini

- 7 knowledge base terpisah: **PP, PA, BING, PR, ILKOM, KAP, DJ**.
- Tiga AI specialist per mata kuliah (Agent A, B, dan C). Specialist tidak menerima draft specialist lain; per request hanya specialist untuk subject aktif yang dipanggil, bukan semua 21 agent.
- Researcher mengambil chunk dari vector index subject aktif; Librarian memvalidasi subject, dokumen, halaman, dan chunk terhadap SQLite.
- Manager memeriksa jawaban berdasarkan sumber yang ditemukan, dapat meminta paling banyak dua revisi, serta menggunakan `UNVERIFIED` jika bukti tidak cukup.
- PDF banyak per mata kuliah, ekstraksi per halaman, chunk ID, metadata subject/dokumen/halaman, embedding melalui 9Router, SQLite dan index vektor persisten.
- Telegram: tanya jawab, rangkuman, kuis, daftar/hapus materi, batas akses per Telegram user ID, dan respons aman ketika provider tidak tersedia.
- Website/API FastAPI lokal dengan akses login nama pengguna/kata sandi: pilih subject, chat, rangkum, kuis, upload/daftar/hapus PDF. AI Study Desk juga dapat merangkum video YouTube memakai caption publik (tanpa download audio/video) dan menerima voice note lewat rekaman browser atau unggahan audio yang ditranskripsi dengan model STT 9Router.
- Batas konteks lokal untuk rangkuman dinaikkan menjadi **60.000 karakter** secara default; file `.env` yang sudah ada tetap menang dan perlu diperbarui manual jika masih menyetel nilai 30.000.
- Visual **Agent Office** bergaya pixel/block yang lebih sederhana: 18 pekerja (21 specialist A/B/C untuk tujuh mata kuliah, Researcher, Librarian, Archivist visual, dan AI Manager), Owner Arya, Developer Byte, Pantry, Mushola, lounge, dan kolam refleksi. Layout ruang/pod, nama mata kuliah dari `config/subjects.yaml`, bukaan pintu, collision dinding/furnitur/kolam, serta navigasi tetap mengikuti layout baru. Canvas memiliki tombol zoom +/−/reset, roda mouse, pinch, dan drag saat diperbesar. Setiap hari menurut jam `Asia/Jakarta`, seluruh karakter menuju workstation pukul 08.00; mereka bekerja dalam blok 08.00–12.00 dan 12.30–16.30, dengan istirahat 30 menit pukul 12.00–12.30 dan 16.30–17.00. Setelah 17.00, layanan tetap berjalan dan tugas yang dikirim tetap diproses. Saat pengguna mengirim pertanyaan, meminta rangkuman, atau kuis, karakter tim yang relevan tampak sibuk dan ikon runner pembawa dokumen tampil di AI Study Desk selama proses berjalan. Pada perkiraan waktu sholat Jakarta, karakter idle mengambil jeda terpisah sekitar 12–14 menit; maksimal empat bergerak ke Mushola sekaligus karena kapasitas visualnya, sementara karakter dengan tugas aktif tidak dialihkan. Jadwal sholat dihitung offline untuk koordinat Jakarta (Fajr -20°, Isha -18°, Asr standard), sehingga merupakan perkiraan dan dapat berbeda dari jadwal resmi Kemenag/masjid setempat. Artwork retro berada di `app/web/office_background_retro.webp` dan di-embed sebagai data URI; ini aproksimasi dari artwork saat ini karena file pre-HD asli tidak tersedia, sementara artwork sebelumnya tetap ada di `app/web/office_background.webp`. Archivist tetap persona visual, bukan panggilan AI backend. Status shift/animasi adalah representasi visual, bukan telemetry progres backend per-agent.
- Fallback model dapat dikonfigurasi per tipe agent. Model ID harus benar-benar tersedia dan diizinkan oleh provider yang tersambung.
- **Multi-provider per endpoint dan peran**: `CHAT_*`, `EMBEDDING_*`, `STT_*` mengatur endpoint chat spesialis, embedding, dan STT; `MANAGER_CHAT_*` dapat mengalihkan hanya AI Manager/verifier ke endpoint lain seperti Ollama/Hermes. Jika override Manager kosong, Manager mengikuti endpoint chat biasa. Tanpa override, perilaku default tetap memakai 9Router.
- **Backup Google Drive otomatis**: setiap PDF yang berhasil di-upload disalin ke folder `Academic_AI/<KODE_MATKUL>/` di Drive; file lokal tetap dipakai untuk RAG. Deduplikasi konten identik, best-effort (gagal backup tidak menggagalkan upload), dan hapus materi ikut menghapus salinan Drive.
- **Endpoint `/api/stats` + workflow n8n siap-import**: kuis harian terjadwal, auto-ingest folder inbox, dan digest statistik harian ke Telegram.
- **Antrean job + progress bar**: rangkuman dan kuis di website berjalan sebagai job FIFO dengan indikator tahap (mencari → memeriksa → menyusun → memverifikasi); endpoint `/api/jobs` juga bisa dipanggil skrip/n8n.
- **Halaman Pengaturan + API**: ubah RAG/model/kredensial dari browser (`GET/PATCH /api/settings`); kunci runtime berlaku langsung, kunci jaringan/model tersimpan ke `.env` dan aktif setelah restart. Ganti password: halaman Pengaturan atau `python run.py --set-password`.
- **Ekspor riwayat**: tombol Ekspor di AI Study Desk mengunduh percakapan mata kuliah aktif sebagai Markdown.
- **OCR PDF scan otomatis**: bila PDF nyaris tanpa teks dan Tesseract terinstal, halaman di-OCR (Indonesia+Inggris) saat upload; maks 80 halaman per file.
- **Perintah Telegram `/mode`**: preset gaya jawaban Singkat/Seimbang/Mendalam (berlaku langsung, tersimpan di `.env`).

**Batas penting:** PDF hasil scan tanpa text layer otomatis di-OCR bila Tesseract terinstal (maks 80 halaman per file); tanpa Tesseract, pakai PDF yang teksnya bisa dipilih. Tidak ada jawaban yang diberi status VERIFIED hanya karena model menyatakannya; jawaban tanpa bukti yang tervalidasi menjadi `UNVERIFIED`. Project tidak mengirim reasoning internal model ke pengguna.

## Struktur folder ringkas

```text
academic_ai/
├── app/
│   ├── agents/          # Subject specialists A/B/C dan struktur hasil
│   ├── bot/             # Telegram commands dan handlers
│   ├── database/        # SQLite: user, percakapan, dokumen, chunks, audit
│   ├── knowledge/       # PDF, embeddings, citations, vector index
│   ├── manager/         # Researcher/Librarian orchestration, Manager/revisions
│   ├── providers/       # Abstraksi provider, 9Router, OpenAI-compat generik, router per-peran
│   ├── services/        # Ingest materi, caption YouTube, backup Google Drive
│   └── web/             # FastAPI routes dan UI HTML lokal
├── config/              # subjects.yaml, models.yaml
├── tests/               # tes otomatis offline
├── data/                # dibuat lokal: SQLite, PDF, index vektor
├── run.py               # Telegram bot
├── web_run.py           # website/API lokal
├── start_bot.bat        # Windows CMD launcher bot
├── start_web.bat        # Windows CMD launcher website
├── .env.example         # template konfigurasi kosong
├── .env.gratis-9router.example # profil model 9Router contoh
├── .env.ollama-hermes.example  # profil semua chat lokal via Ollama
├── .env.hybrid-manager-hermes.example # spesialis 9Router + Manager Hermes lokal
├── n8n/                # workflow siap-import (kuis, ingest folder, digest)
├── PANDUAN_*.md        # panduan Hermes, backup Drive, dan n8n
├── SETUP_CHECKLIST.md   # daftar nilai yang wajib diisi
└── requirements*.txt
```

PDF disimpan di `data/knowledge/<subject>/`; database ada di `data/academic_ai.db`; index vektor terpisah berada di `data/vectorstore/`. Masing-masing upload punya nama file aman yang unik—PDF tidak menimpa file lain hanya karena nama asli sama. Data ini tetap ada setelah bot/website ditutup.

## Prasyarat

- Windows 10/11.
- Python 3.11+.
- Node.js LTS + npm untuk 9Router lokal.
- VS Code (opsional, tetapi disarankan untuk melihat file dan log).
- Token Telegram dari `@BotFather` jika akan memakai bot Telegram.
- 9Router lokal, satu atau lebih provider terhubung, API key lokal 9Router, chat model, dan embedding model.
- Tesseract OCR (opsional, hanya untuk PDF hasil scan): `winget install --id UB-Mannheim.TesseractOCR`, lalu buka CMD baru.

### Jalankan 9Router

Ikuti instruksi resmi 9Router; dokumentasi saat ini menjelaskan instalasi CLI melalui:

```cmd
npm install -g 9router
9router
```

Biarkan proses itu tetap berjalan di CMD terpisah. Dashboard lokal biasanya dibuka pada `http://localhost:20128`; salin API key lokal yang ditampilkan, lalu sambungkan provider/model yang akan digunakan. Project memakai `http://localhost:20128/v1` sebagai OpenAI-compatible base URL secara default.

**Jangan isi `oc/auto` secara otomatis.** Pada September 2026, laporan 9Router mencatat OpenCode Free menghasilkan 403 dan pihak OpenCode menyatakan tier gratisnya hanya untuk klien OpenCode, bukan router pihak ketiga. Lihat [laporan akses 403](https://github.com/decolua/9router/issues/4124) dan [permintaan pembatasan OpenCode](https://github.com/decolua/9router/issues/4182). Untuk fallback pilih provider lain yang izinnya jelas, lalu salin ID model persis dari katalog lokal.

## Instalasi pertama — Windows CMD

1. Buat/ekstrak folder project, misalnya `C:\academic_ai`, lalu buka **Command Prompt** (CMD) di folder tersebut. Di VS Code pilih **Terminal → New Terminal** dan ubah profil terminal menjadi Command Prompt jika perlu.
2. Siapkan virtual environment dan dependencies:

```cmd
cd /d C:\academic_ai
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

3. (Opsional, untuk PDF hasil scan) instal Tesseract OCR bila langkah prasyarat belum dilakukan, lalu tutup-buka CMD agar PATH terbaca.

4. Pilih salah satu template:

```cmd
copy .env.gratis-9router.example .env
```

Template gratis memuat contoh ID Kiro untuk Agent A/B per subject dan Manager; ketersediaannya harus dicek pada 9Router milikmu. Template kosong juga tersedia:

```cmd
copy .env.example .env
```

5. Buat local API token internal untuk website. Jalankan perintah berikut di CMD; salin hasilnya ke `LOCAL_API_TOKEN` di `.env`. Token ini tetap rahasia di sisi server—tidak perlu kamu masukkan ke browser:

```cmd
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

6. Buka `.env`, lalu isi nama pengguna dan kata sandi pilihanmu pada `LOCAL_WEB_USERNAME` serta `LOCAL_WEB_PASSWORD`:

```cmd
notepad .env
```

## Nilai yang harus diisi atau diperiksa di `.env`

| Nama | Harus diisi/diperiksa | Catatan |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Isi jika memakai Telegram | Buat melalui `@BotFather`. Rahasia. |
| `ALLOWED_USER_IDS` | Isi ID Telegram numerik | Satu atau beberapa ID, pisahkan dengan koma. Hanya ID ini yang diizinkan. |
| `NINE_ROUTER_API_KEY` | Wajib | Salin dari dashboard 9Router lokal. Rahasia; jangan mengirimnya ke chat. |
| `MODEL_EMBEDDING` | Wajib untuk PDF/RAG | Pilih **exact ID** dari `GET http://localhost:20128/v1/models/embedding`; jangan menebak ID. Hubungkan provider embedding dulu. |
| `MODEL_<KODE>_A`, `MODEL_<KODE>_B` | Wajib untuk 7 subject | `.env.gratis-9router.example` sudah memberi contoh. Jalankan live check dan ganti ID yang tidak tersedia. |
| `MODEL_MANAGER` | Wajib | Dicek terhadap katalog endpoint Manager; dipakai untuk verifikasi dan merangkum caption YouTube. |
| `MODEL_STT` | Wajib hanya jika memakai voice note | Pilih ID dari `GET http://localhost:20128/v1/models/stt`. Model chat tidak otomatis mendukung STT. |
| `MODEL_FALLBACK_*`, `FALLBACK_MODEL` | Opsional | Boleh kosong. Hanya isi model yang muncul di katalog dan boleh digunakan lewat provider itu. |
| `CHAT_*`, `EMBEDDING_*`, `STT_*` | Opsional | Mengatur endpoint chat spesialis, embedding, dan STT. Kosong = memakai 9Router. |
| `MANAGER_CHAT_BASE_URL`, `MANAGER_CHAT_API_KEY` | Opsional | Override endpoint khusus Manager/verifier, misalnya `http://localhost:11434/v1` + `ollama`. Kosong = mengikuti chat spesialis. Lihat `PANDUAN_OLLAMA_HERMES.md`. |
| `GDRIVE_BACKUP_ENABLED`, `GDRIVE_*` | Opsional | Backup PDF otomatis ke Google Drive per matkul. Default mati. Lihat `PANDUAN_GDRIVE_BACKUP.md`. |
| `LOCAL_API_TOKEN` | Wajib untuk website | Rahasia internal server; gunakan nilai acak panjang. Browser tidak lagi meminta token ini. |
| `LOCAL_WEB_USERNAME`, `LOCAL_WEB_PASSWORD` | Wajib untuk login website | Buat akun lokal sendiri. Kata sandi disimpan hanya di `.env` lokal; jangan bagikan file tersebut. |
| `NINE_ROUTER_BASE_URL` | Biasanya biarkan | Default `http://localhost:20128/v1`. |
| `WEB_ACCESS_MODE` | Biarkan `localhost`, ubah ke `lan` hanya bila ingin akses HP di jaringan lokal | Default aman localhost; mode LAN bind ke semua interface tetapi API menolak alamat client non-private dan tetap mewajibkan token. |
| `WEB_HOST`, `WEB_PORT` | Biasanya biarkan | Localhost default `127.0.0.1:8765`. Dalam mode `lan`, host otomatis menjadi `0.0.0.0`; dari HP gunakan IPv4 laptop, bukan alamat `0.0.0.0`. |
| `MAX_PDF_MB`, `MAX_AUDIO_MB`, `RAG_TOP_K`, `MAX_REVISION_ROUNDS`, dll. | Opsional | Ukuran maksimum audio default 25 MB; jumlah revisi maksimum dibatasi 2. `MAX_CONTEXT_CHARS` default 60.000. |

`MAX_CONTEXT_CHARS` memakai default 60.000 karakter untuk ringkasan lokal. Jika `.env` lama berisi `MAX_CONTEXT_CHARS=30000`, ubah manual menjadi `60000` lalu restart website/bot; nilai di `.env` selalu mengalahkan default kode/template. `Researcher` dan `Librarian` adalah modul lokal, bukan chat model tambahan: Researcher melakukan retrieval subject-specific, sedangkan Librarian mengecek metadata/sumber. Ini menghemat panggilan model. Model untuk 14 specialist harus tersedia pada endpoint spesialis (9Router secara default); `MODEL_MANAGER` harus tersedia pada endpoint Manager yang dikonfigurasi, bisa juga Ollama lokal.

### Cek model sebelum memakai aplikasi

Dengan 9Router berjalan dan provider sudah tersambung, dari CMD project jalankan:

```cmd
python run.py --check
python run.py --check --live
```

`--check` memeriksa konfigurasi lokal tanpa mengirim permintaan ke model. `--check --live` membaca katalog chat spesialis, katalog chat Manager, dan katalog embedding yang dikonfigurasi; ia **tidak** mengirim pertanyaan ke model. Jika ada `TIDAK ADA`, salin ID persis dari endpoint yang ditampilkan untuk peran tersebut lalu ubah `.env`. Ulangi hingga model-model yang digunakan tidak lagi ditandai tidak tersedia. `MODEL_EMBEDDING` harus ada di katalog embedding, bukan hanya di katalog chat.

## Jalankan Telegram bot

Pastikan 9Router berjalan. Buka CMD terpisah, lalu:

```cmd
cd /d C:\academic_ai
venv\Scripts\activate
python run.py
```

Atau jalankan `start_bot.bat` dengan double-click. Proses Python dan 9Router harus tetap terbuka selama bot digunakan. Menutup CMD, mematikan komputer, atau menghentikan proses membuat bot offline; project tidak berjalan di background/VPS.

### Cara mencoba Telegram

1. Chat bot dan kirim `/start`.
2. Gunakan `/matkul`, lalu pilih mata kuliah aktif.
3. Gunakan `/tambahmateri`, pilih mata kuliah, kemudian upload PDF teks.
4. Tunggu pesan bahwa file sudah diproses.
5. Coba `/materi`, lalu ajukan pertanyaan yang jawabannya tercantum di PDF.
6. Uji `/ringkas <topik>`, `/kuis <topik>`, `/hapusmateri`, dan `/mode`.

Perintah tersedia: `/start`, `/help`, `/matkul`, `/tambahmateri`, `/materi`, `/status`, `/reset`, `/ringkas`, `/kuis`, `/hapusmateri`, `/mode`. Akses bot ditolak bila Telegram user ID tidak ada di `ALLOWED_USER_IDS`.

## Jalankan website/API lokal

Pastikan `.env` berisi `LOCAL_API_TOKEN`, `LOCAL_WEB_USERNAME`, dan `LOCAL_WEB_PASSWORD`, lalu 9Router berjalan. Di CMD project:

```cmd
cd /d C:\academic_ai
venv\Scripts\activate
python web_run.py
```

Atau double-click `start_web.bat`. Pada mode `localhost`, buka `http://127.0.0.1:8765`; pada mode LAN, ikuti langkah akses HP di bawah. Masuk dengan `LOCAL_WEB_USERNAME` dan `LOCAL_WEB_PASSWORD`, lalu pilih mata kuliah. UI membuat sesi Bearer acak secara otomatis di background selama 12 jam; pengguna tidak perlu mengetik atau menyalin `LOCAL_API_TOKEN`. Sesi tersimpan hanya di memori server dan browser tab, sehingga restart server atau masa berlaku habis mengharuskan login ulang. Endpoint tetap menerima `LOCAL_API_TOKEN` untuk kompatibilitas skrip lama. Website menyediakan chat, rangkuman, kuis, upload PDF, daftar dokumen, hapus PDF, halaman Pengaturan (.env), dan tombol ekspor riwayat percakapan. Di AI Study Desk, buka panel **YouTube & voice notes** untuk memasukkan URL video atau merekam/mengunggah audio. Ringkasan YouTube menggunakan caption publik yang otomatis diambil server; bila caption tidak tersedia, aplikasi menampilkan pesan fallback dan **tidak** mengunduh audio/video. Ringkasan caption berstatus belum diverifikasi terhadap PDF kuliah. Voice note dikirim ke model yang ditetapkan pada `MODEL_STT` (bahasa bisa dideteksi otomatis atau dipilih Indonesia/English); hasil transkripsi dimasukkan ke kotak pertanyaan untuk ditinjau, tidak langsung dikirim, dan file audio tidak disimpan aplikasi. Browser perlu izin mikrofon dan akses media yang aman (localhost/HTTPS).

API dilindungi header Bearer. Login nama pengguna/kata sandi membuat token sesi acak 12 jam yang disimpan otomatis di `sessionStorage`; `LOCAL_API_TOKEN` tetap sebagai rahasia internal server dan kompatibilitas skrip lama. Default `WEB_ACCESS_MODE=localhost` hanya dapat dibuka dari laptop. Proses website dan 9Router harus tetap berjalan.

### Akses website dari HP melalui Wi-Fi/LAN

HP dan laptop perlu berada di **jaringan lokal yang sama**—biasanya terhubung ke Wi-Fi/router yang sama. Ini opsional; mode localhost tetap lebih aman jika hanya memakai web di laptop.

1. Hentikan website (di CMD tekan `Ctrl+C`), lalu buka `.env`.
2. Ubah/tambahkan baris berikut; biarkan `WEB_HOST` apa adanya:

   ```env
   WEB_ACCESS_MODE=lan
   ```

   Mode ini otomatis bind ke interface jaringan. API menolak client yang bukan alamat jaringan private dan meminta sesi login (atau token legacy untuk skrip).
3. Jalankan kembali `python web_run.py`. Jika Windows Firewall menampilkan permintaan izin, pilih **Private networks saja**—jangan pilih Public networks.
4. Di laptop, buka CMD lain dan jalankan `ipconfig`. Cari **IPv4 Address** pada adapter aktif yang terhubung ke LAN/router (Wi-Fi atau Ethernet), misalnya `192.168.1.23`.
5. Pastikan HP berada pada jaringan lokal yang sama (umumnya Wi-Fi/router yang sama), lalu buka `http://192.168.1.23:8765` (ganti contoh IP dengan IPv4 laptop). Login memakai `LOCAL_WEB_USERNAME` dan `LOCAL_WEB_PASSWORD`.

Gunakan hanya jaringan private yang dipercaya: situs berjalan melalui HTTP, jadi nama pengguna, kata sandi, dan token sesi tidak terenkripsi saat dikirim di jaringan lokal. Jangan gunakan `http://0.0.0.0:8765` sebagai URL browser, jangan aktifkan port forwarding, dan jangan buka mode LAN ke internet. Jika HP tetap tidak tersambung, pastikan firewall mengizinkan Python/port 8765 pada profil Private dan router tidak mengaktifkan client/AP isolation.

## File dan data lokal

Saat dijalankan, aplikasi membuat struktur seperti:

```text
data/
├── academic_ai.db
├── drive_credentials.json   (opsional, rahasia — OAuth client backup Drive)
├── drive_token.json         (opsional, rahasia — token backup Drive)
├── knowledge/
│   ├── pp/  pa/  bing/  pr/  ilkom/  kap/  dj/
└── vectorstore/
    └── vectors.sqlite
```

SQLite menyimpan user, percakapan/pesan, metadata dokumen, chunk, dan log agent/verifikasi. File PDF disimpan terpisah per subject, sedangkan index vector persisten menyimpan embedding dan metadata pencarian. Penambahan/hapus PDF mempertahankan subject filter; satu subject tidak mengambil chunk dari subject lain.

## Test otomatis

Test tidak memerlukan token Telegram/API provider dan tidak melakukan request network:

```cmd
venv\Scripts\activate
python -m pytest -q
node tests/test_agent_office.js
node tests/test_web_ui.js
python -m compileall -q app run.py web_run.py
```

Verifikasi Agent Office pada workspace: `node tests/test_agent_office.js` memeriksa **225 rute**, jadwal, zoom, loader chat/rangkuman/kuis/media, UI login, kontrol YouTube dan voice note, tujuh label mata kuliah, serta avatar. Suite Python juga mencakup sapaan sederhana, login nama/kata sandi dan pencabutan sesi, pengambilan caption (mock), parsing URL, ukuran/audio STT (mock), perlindungan API, dan batas konteks. Suite ini juga mencakup perbaikan Fase 1 (resolusi subject aktif, error 422, hapus vector scoped, fallback sumber), routing multi-provider (mock), backup Drive (mock), dan endpoint `/api/stats`, antrean job (`/api/jobs`), pengaturan runtime (`/api/settings`), ekspor riwayat, preset `/mode`, dan OCR (mock). Tes tidak mengirim audio, transcript, atau pertanyaan ke layanan live. Tidak ada live smoke test Telegram/9Router/YouTube karena kredensial dan koneksi pengguna tidak tersedia.

## Model tambahan dan kuota gratis

Model/prefix dapat berubah; cek katalog lokal (`/v1/models`) dan sambungkan providernya di dashboard 9Router sebelum mengubah `.env`.

- **Kiro**: contoh pada template berasal dari daftar 9Router (`kr/claude-sonnet-4.5`, `kr/claude-haiku-4.5`, `kr/glm-5`, `kr/MiniMax-M2.5`, `kr/deepseek-3.2`, `kr/qwen3-coder-next`). Repo 9Router menyebut sekitar 50 credits/bulan; ini bukan kuota unlimited.
- **Vertex AI**: model seperti `vertex/gemini-3.1-pro-preview` atau `vertex/gemini-2.5-flash` dapat dicoba melalui koneksi Vertex di 9Router. Trial credit Google Cloud terbatas waktu/pemakaian; bukan gratis permanen, dan konfigurasi butuh project serta kredensial Google Cloud di dashboard 9Router.
- **Cloudflare Workers AI**: pilihan lain melalui provider Cloudflare AI di 9Router. Cloudflare menyebut kuota free 10.000 Neurons per hari; perlu Cloudflare Account ID dan API token di dashboard. Contoh model upstream meliputi `@cf/zai-org/glm-4.7-flash`, `@cf/meta/llama-3.2-3b-instruct`, atau `@cf/openai/gpt-oss-20b`, tetapi gunakan **ID persis yang ditampilkan katalog 9Router** (bisa memakai prefix provider).
- **Embedding**: `gemini-embedding-2` adalah kandidat dengan free tier menurut Google, tetapi hanya dapat dipakai bila provider Google sudah tersambung dan ID tepat muncul dari katalog **embedding** 9Router. Model chat tidak otomatis cocok untuk embedding.

Ketentuan, harga/kuota, daftar ID, dan hak penggunaan provider dapat berubah. Jangan mengandalkan model gratis untuk akses tanpa batas atau memakai layanan melewati persyaratan provider.

## Hermes (Ollama), backup Drive, dan n8n

- **Hermes/Ollama**: instal Ollama lalu `ollama pull hermes3`. Untuk setup hybrid (A/B spesialis 9Router + Manager Hermes lokal), salin `.env.hybrid-manager-hermes.example` ke `.env`; untuk semua chat lokal, gunakan `.env.ollama-hermes.example`. Periksa dengan `python run.py --check --live`. Detail: `PANDUAN_OLLAMA_HERMES.md`.
- **Backup Drive**: buat OAuth client Desktop di Google Cloud Console, simpan JSON ke `data/drive_credentials.json`, jalankan `python run.py --drive-auth`, lalu set `GDRIVE_BACKUP_ENABLED=true`. Detail: `PANDUAN_GDRIVE_BACKUP.md`.
- **n8n**: `npm install -g n8n` lalu `n8n start`, import file di folder `n8n/`, isi token API/Telegram/chat ID, dan aktifkan workflow. Detail: `PANDUAN_N8N.md`.

## Pemecahan masalah dasar

- **`TELEGRAM_BOT_TOKEN` kosong/tidak valid** — cek `.env`, pastikan token dari `@BotFather` benar, lalu restart bot.
- **`Unauthorized user`** — cek ID numerik Telegram di `ALLOWED_USER_IDS`; pisahkan beberapa ID dengan koma.
- **Login website 503 / kredensial belum diatur** — isi `LOCAL_WEB_USERNAME` dan `LOCAL_WEB_PASSWORD` di `.env`, pastikan `LOCAL_API_TOKEN` internal juga ada, lalu restart `web_run.py`.
- **Sesi website kedaluwarsa** — login lagi; sesi berumur 12 jam dan dihapus jika server restart.
- **Connection refused ke `localhost:20128`** — nyalakan 9Router terlebih dahulu dan cek `NINE_ROUTER_BASE_URL`.
- **Voice note memberi 503 / model tidak ditemukan** — isi `MODEL_STT` memakai ID dari `/v1/models/stt`, bukan otomatis memakai `MODEL_MANAGER` atau model chat lainnya; pastikan provider STT tersambung di 9Router.
- **Ringkasan YouTube tidak tersedia** — video harus memiliki caption/transkrip publik yang dapat diambil. Fitur ini tidak mengambil audio video sebagai fallback.
- **Model not found** — jalankan `python run.py --check --live`, sambungkan provider di dashboard, lalu ubah ID pada `.env` mengikuti katalog.
- **Embedding model tidak ada** — periksa `/v1/models/embedding`; model chat biasa belum tentu provider embedding.
- **Error 401/403/429** — token/provider mungkin salah, batas kuota tercapai, atau akses model ditolak. Cek log 9Router/dashboard dan pilih model lain yang tersedia/diizinkan. Jangan menaruh token dalam issue/chat/log publik.
- **PDF tidak terbaca / tidak ada chunks** — bila file hasil scan, instal Tesseract (lihat Prasyarat) lalu unggah ulang; bila tetap gagal, pakai PDF yang teksnya bisa dipilih, pastikan file tidak rusak, atau split scan di atas 80 halaman.
- **Website tidak terbuka** — pastikan `web_run.py` masih berjalan, URL `http://127.0.0.1:8765` benar, dan port tidak dipakai program lain.
- **Bot/website gagal karena SQLite sibuk** — tutup proses aplikasi yang tidak dipakai, tunggu proses upload selesai, lalu coba kembali. Folder `data/` berisi data lokal; jangan menghapusnya kecuali memang ingin menghapus semua materi/percakapan.

## Privasi dan keamanan

PDF, database, serta vector index disimpan di komputer lokal. Pertanyaan dan potongan teks PDF yang dipakai untuk embedding/jawaban, caption YouTube yang diringkas, serta audio voice note yang ditranskripsi dikirim ke provider/model yang kamu aktifkan lewat 9Router. Audio hanya diproses sementara dan tidak disimpan aplikasi; caption video juga dikirim sebagai input ke model ringkasan. Jangan unggah materi rahasia atau data pribadi bila kebijakan kampus/pemilik materi tidak mengizinkan. Simpan `.env` secara lokal, jangan kirim ke chat, repository, atau screenshot. Nama pengguna/kata sandi dikirim melalui HTTP tanpa enkripsi hanya jika kamu mengaktifkan akses LAN; gunakan jaringan yang dipercaya dan utamakan mode localhost.
