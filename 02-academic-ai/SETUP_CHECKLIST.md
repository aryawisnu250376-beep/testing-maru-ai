# Catatan Pengisian Academic AI

Checklist ini merangkum nilai yang perlu kamu isi/ganti di `.env` setelah project disalin ke Windows. Jangan kirim `.env`, token Telegram, atau API key ke chat/Git/screenshot.

## 1. Buat `.env` lokal

Di Windows CMD, dari folder project:

```cmd
copy .env.gratis-9router.example .env
notepad .env
```

File `.env.gratis-9router.example` berisi contoh pembagian model Kiro per specialist dan Manager 9Router. Jika ingin konfigurasi khusus yang diminta—A/B melalui 9Router dan hanya Manager memakai Hermes lokal—gunakan `copy .env.hybrid-manager-hermes.example .env`. Template kosong tersedia melalui `copy .env.example .env`. Template `.env.ollama-hermes.example` tetap tersedia untuk mode semua chat lokal. Detailnya di `PANDUAN_OLLAMA_HERMES.md`.

## 2. Nilai yang wajib diisi

| Nama di `.env` | Apa yang harus diisi | Cara mendapatkan/memeriksa |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Token bot Telegram | Buat bot melalui `@BotFather`; hanya diperlukan jika memakai Telegram. Rahasia. |
| `ALLOWED_USER_IDS` | ID numerik akun Telegram yang diizinkan | Cari numeric Telegram user ID; untuk beberapa akun pisahkan dengan koma. Jangan memakai username. |
| `NINE_ROUTER_API_KEY` | API key lokal 9Router | Salin dari dashboard 9Router lokal. Rahasia. |
| `MODEL_EMBEDDING` | ID embedding exact | Sambungkan provider embedding di 9Router, lalu salin dari `GET http://localhost:20128/v1/models/embedding`. Model chat bukan otomatis model embedding. |
| `MODEL_<KODE>_A`, `MODEL_<KODE>_B` | ID dua AI specialist untuk tiap subject | Isi PP, PA, BING, PR, ILKOM, KAP, DJ. Template gratis memberi contoh, tetapi wajib dicek di katalog live 9Router. |
| `MODEL_MANAGER` | ID chat model Manager | Cek di endpoint Manager yang dipilih: Ollama `/v1/models` jika `MANAGER_CHAT_BASE_URL` diisi, selain itu katalog chat biasa. Dipakai untuk verifikasi dan rangkuman caption YouTube. |
| `MODEL_STT` | Isi hanya jika memakai voice notes | Pilih ID exact dari `GET http://localhost:20128/v1/models/stt`; model chat tidak otomatis mendukung transkripsi audio. |
| `LOCAL_API_TOKEN` | Rahasia internal website/API lokal | Buat dengan perintah CMD di bawah; tetap disimpan di `.env`, tetapi tidak perlu ditempel ke browser. Jangan bagikan. |
| `LOCAL_WEB_USERNAME`, `LOCAL_WEB_PASSWORD` | Akun login website | Tentukan nama pengguna dan kata sandi sendiri, isi hanya di `.env` lokal. Jangan bagikan password atau file `.env`. |

Untuk membuat token lokal website, jalankan dari folder project:

```cmd
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Salin hasilnya ke `.env` sebagai `LOCAL_API_TOKEN=...`. Buat token berbeda untuk tiap instalasi bila perlu. Lalu isi `LOCAL_WEB_USERNAME` dan `LOCAL_WEB_PASSWORD` dengan akun lokal pilihanmu. Token API hanya dipakai aplikasi di background; halaman login meminta nama pengguna/kata sandi dan membuat sesi browser acak yang berlaku 12 jam.

## 3. Cek semua ID model yang dipakai

Jalankan 9Router terlebih dahulu, sambungkan provider/model yang diinginkan di dashboard, lalu di CMD folder project:

```cmd
python run.py --check
python run.py --check --live
```

`--check --live` mengambil katalog chat spesialis, katalog chat Manager, dan katalog embedding sesuai endpoint yang dikonfigurasi. Jika ada baris `TIDAK ADA`, salin ID dari katalog endpoint untuk peran tersebut dan ganti variabel terkait di `.env`. Pemeriksaan katalog tidak mengirim prompt ke model. Untuk voice note, periksa daftar STT terpisah melalui `http://localhost:20128/v1/models/stt`, lalu isi `MODEL_STT` dengan ID yang muncul di sana.

Alamat 9Router biasanya dapat dibiarkan:

```env
NINE_ROUTER_BASE_URL=http://localhost:20128/v1
NINE_ROUTER_TIMEOUT=90
NINE_ROUTER_MAX_RETRIES=3
WEB_ACCESS_MODE=localhost
WEB_HOST=127.0.0.1
WEB_PORT=8765
```

## 4. Tim Researcher/Librarian dan AI specialist

Researcher dan Librarian adalah modul lokal. Researcher melakukan retrieval di vectorstore yang disaring berdasarkan mata kuliah; Librarian memvalidasi subject, nama dokumen, nomor halaman, dan chunk ID terhadap SQLite. Keduanya tidak butuh API key/model chat tambahan.

Dua AI specialist per mata kuliah **menggunakan model chat**, dan Manager memeriksa hasilnya. Contoh mapping pada profil hybrid `.env.hybrid-manager-hermes.example` (A/B murah di 9Router; Manager lokal):

- PP: Haiku 4.5 + GLM-5
- PA: Haiku 4.5 + GLM-5
- BING: Haiku 4.5 + GLM-5
- PR: Haiku 4.5 + DeepSeek 3.2
- ILKOM: Haiku 4.5 + GLM-5
- KAP: Haiku 4.5 + GLM-5
- DJ: Haiku 4.5 + Qwen3 Coder Next
- Manager: Hermes 3 lokal melalui Ollama

Template memakai variabel `MODEL_PP_A`/`MODEL_PP_B`, dan seterusnya. Pada setiap request hanya dipanggil 2 specialist untuk mata kuliah aktif beserta Manager; bukan semua 14 specialist sekaligus. Template gratis memakai `MAX_REVISION_ROUNDS=1`, sehingga kasus terburuk 6 panggilan model per pertanyaan (2 specialist + Manager, dikali 2 ronde). Jika Manager meminta revisi, pemanggilan model bertambah. Pastikan semua ID tersedia dan kuota cukup sebelum mulai; naikkan ke 2 ronde hanya bila kuota longgar.

## 5. Model/provider alternatif dan batasnya

- **Kiro**: 9Router mencantumkan beberapa model (`kr/claude-sonnet-4.5`, `kr/claude-haiku-4.5`, `kr/glm-5`, `kr/MiniMax-M2.5`, `kr/deepseek-3.2`, `kr/qwen3-coder-next`). Repo 9Router menyebut sekitar 50 credits/bulan untuk free tier; kuota dan daftar dapat berubah.
- **Vertex AI**: 9Router mencantumkan model seperti `vertex/gemini-3.1-pro-preview` dan `vertex/gemini-2.5-flash`. Untuk memakainya, sambungkan Vertex di dashboard 9Router; ini memerlukan project dan kredensial Google Cloud. Kredit trial terbatas waktu/pemakaian, bukan gratis permanen.
- **Cloudflare Workers AI**: 9Router juga mendukung provider Cloudflare AI. Cloudflare menyebut free allocation 10.000 Neurons per hari; perlu Cloudflare Account ID dan API token di dashboard. Contoh upstream termasuk `@cf/zai-org/glm-4.7-flash`, `@cf/meta/llama-3.2-3b-instruct`, dan `@cf/openai/gpt-oss-20b`; pakai ID **persis seperti katalog `/v1/models` 9Router**, termasuk prefix provider jika ada.
- **Embedding**: `gemini-embedding-2` bisa menjadi kandidat karena Google mencantumkan free tier, tetapi pilih hanya jika model tersebut tersedia pada katalog embedding 9Router yang tersambung dan syarat/kuotanya sesuai.

**Jangan mengandalkan OpenCode Free (`oc/auto`) untuk fallback.** Pada September 2026 terdapat laporan 403 saat mengakses dari router pihak ketiga, dan tim OpenCode menyatakan free tier hanya boleh dipakai dari klien OpenCode. Lihat [laporan 9Router 403](https://github.com/decolua/9router/issues/4124) dan [permintaan OpenCode](https://github.com/decolua/9router/issues/4182). Template sengaja membiarkan fallback kosong agar tidak memakai ID yang tidak stabil atau berpotensi melanggar ketentuan.

Model gratis bukan jaminan unlimited. Kuota, kebijakan, dan ID model dapat berubah; jangan menggunakan provider di luar ketentuan layanannya.

## 5b. Profil Ollama/Hermes (opsional)

Untuk memakai Hermes **hanya sebagai Manager**, sementara specialist A/B tetap di 9Router:

1. Instal Ollama, lalu `ollama pull hermes3` dan cek nama dengan `ollama list`.
2. Salin `copy .env.hybrid-manager-hermes.example .env`; isi `NINE_ROUTER_API_KEY` dan rahasia lokal lain. Biarkan `CHAT_BASE_URL` kosong; `MANAGER_CHAT_BASE_URL` menunjuk `http://localhost:11434/v1`.
3. Jalankan `python run.py --check --live`. Katalog chat spesialis harus menunjuk 9Router; katalog Manager harus menunjuk Ollama.

Untuk mode semua chat lokal, gunakan `.env.ollama-hermes.example`. Jika semua `*_BASE_URL` kosong, semua peran kembali memakai 9Router. Panduan lengkap: `PANDUAN_OLLAMA_HERMES.md`.

## 5c. Backup Google Drive (opsional)

1. Buat OAuth client (Desktop) di Google Cloud Console, aktifkan Drive API,
   simpan JSON sebagai `data/drive_credentials.json`.
2. `python run.py --drive-auth` (sekali saja) untuk menyimpan token.
3. Set `GDRIVE_BACKUP_ENABLED=true` di `.env`, restart bot/web.

Setiap PDF yang di-upload lalu dibackup ke `Academic_AI/<KODE>/` di Drive.
Panduan lengkap: `PANDUAN_GDRIVE_BACKUP.md`.

## 5d. n8n (opsional)

1. `npm install -g n8n`, lalu `n8n start` (biarkan berjalan).
2. Pastikan `python web_run.py` juga berjalan.
3. Import workflow dari folder `n8n/`, isi token API/Telegram/chat ID,
   test, lalu aktifkan.

Panduan lengkap: `PANDUAN_N8N.md`.

## 6. Nilai opsional yang dapat dibiarkan

- `MODEL_FALLBACK_AGENT_A`, `MODEL_FALLBACK_AGENT_B`, `MODEL_FALLBACK_MANAGER`, `FALLBACK_MODEL`: boleh kosong. Isi hanya jika fallback legal/diizinkan dan muncul di live catalog 9Router.
- `MAX_PDF_MB`, `MAX_AUDIO_MB`, `RAG_TOP_K`, `RAG_MIN_SCORE`, `RAG_QUERY_VARIANTS`, `MAX_OUTPUT_TOKENS`, `MAX_REVISION_ROUNDS`, `MAX_CONTEXT_CHARS`, `LOG_LEVEL`: nilai template umumnya dapat dibiarkan. `MAX_CONTEXT_CHARS` default 60.000; ubah `.env` lama yang masih berisi 30.000 lalu restart aplikasi. Batas upload audio default 25 MB. Jumlah revisi maksimum adalah 2.
- `WEB_ACCESS_MODE=localhost` adalah default aman. Untuk akses HP, ubah hanya menjadi `WEB_ACCESS_MODE=lan`; aplikasi otomatis memilih host LAN dan membatasi API ke IP private + bearer token.

## 7. Jalankan

Pastikan 9Router tetap berjalan di CMD tersendiri. Di CMD kedua, jalankan bot:

```cmd
venv\Scripts\activate
python run.py
```

Website/API dijalankan terpisah di CMD lain:

```cmd
venv\Scripts\activate
python web_run.py
```

Buka `http://127.0.0.1:8765`, lalu login dengan `LOCAL_WEB_USERNAME` dan `LOCAL_WEB_PASSWORD`; token sesi dibuat otomatis di background. Panel YouTube hanya memakai caption publik dan tidak mengunduh audio/video. Panel voice notes dapat merekam atau mengunggah audio; hasil transkripsi dari `MODEL_STT` akan masuk ke kotak pertanyaan. `start_bot.bat` dan `start_web.bat` juga tersedia. Bot dan website hanya hidup selama prosesnya berjalan dan komputer tetap menyala. Keduanya menggunakan data lokal di folder `data/`.

### Akses dari HP melalui jaringan lokal

1. Hentikan web dengan `Ctrl+C` di CMD.
2. Di `.env`, ubah/tambahkan `WEB_ACCESS_MODE=lan`. Biarkan `WEB_HOST=127.0.0.1`; mode LAN akan memilih binding yang diperlukan secara otomatis.
3. Jalankan `python web_run.py` kembali. Jika Windows Firewall bertanya, izinkan **Private networks saja**.
4. Di CMD laptop jalankan `ipconfig`; cari **IPv4 Address** pada adapter aktif yang tersambung ke LAN/router (Wi-Fi atau Ethernet), misalnya `192.168.1.23`.
5. Pastikan HP dan laptop ada di jaringan lokal yang sama (umumnya Wi-Fi/router yang sama), lalu buka `http://192.168.1.23:8765` dengan mengganti contoh IP sesuai alamat laptop. Login memakai `LOCAL_WEB_USERNAME` dan `LOCAL_WEB_PASSWORD`.

Gunakan hanya pada jaringan private yang kamu percaya. Situs memakai HTTP, jadi nama pengguna dan kata sandi tidak terenkripsi saat dikirim di jaringan lokal. API menolak alamat publik dan tetap minta token. Jangan gunakan `0.0.0.0` sebagai alamat browser, jangan buat port forwarding, dan jangan ekspos ke internet. Jika tidak tersambung, cek firewall Private dan pengaturan client/AP isolation router.

Test offline:

```cmd
python -m pytest -q
python -m compileall -q app run.py web_run.py
```

Jangan hapus folder `data/` kecuali kamu sengaja ingin membuang PDF, percakapan, dan vector index.
