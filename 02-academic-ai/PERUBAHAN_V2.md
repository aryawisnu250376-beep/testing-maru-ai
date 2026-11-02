# Perubahan v2 — Perbaikan + Hermes (Ollama) + n8n + Backup Drive

Dokumen ini merangkum semua perubahan dari versi awal (9Router-only) ke versi
ini. File `.env` yang sudah ada **tetap kompatibel**: tanpa variabel baru,
aplikasi berperilaku persis seperti sebelumnya.

## Fase 1 — Perbaikan bug/audit (B1–B5)

- **B1 — Subject aktif persisten**: perintah chat/rangkuman/kuis/tambah-materi/
  hapus-materi kini memakai `resolve_active_subject()` — subject terakhir yang
  dipilih via `/matkul` (atau web) otomatis dipakai; error "pilih matkul dulu"
  hanya muncul bila benar-benar belum ada. Guard `.get()` ditambahkan pada
  penerimaan dokumen dan status admin agar pesan error tak pernah crash.
- **B2 — Error API 422 yang bisa ditindaklanjuti**: endpoint chat, rangkuman
  YouTube, summary, dan quiz kini mengembalikan HTTP 422 berisi pesan perbaikan
  (model hilang, topik kosong, dst) alih-alih 500 generik. Bot Telegram
  menampilkan pesan yang sama.
- **B3 — Hapus vector scoped per dokumen**: sinkronisasi ulang index vektor
  setelah hapus materi hanya menghapus chunk dokumen terkait (bukan rebuild
  seluruh subject), dan tidak menghapus apa pun bila daftar penghapusan kosong.
- **B4 — Sumber jawaban tahan format**: baris sumber mendukung chunk dengan
  `page`, `url`, atau `label`, sehingga sitasi tak pernah kosong/rusak.
- **B5 — Kode mati dihapus**: dua definisi tak terpakai di manager
  (`_sources_from_chunks`, `manager_model_ids`) dibuang.
- Bonus verifikasi: alur caption YouTube terbukti hidup (live test caption
  publik OK dengan timestamp `[mm:ss]`).

## Fase 2 — Multi-provider: Hermes (Ollama) + 9Router

- Provider generik OpenAI-compatible baru (`app/providers/openai_compat.py`)
  dan router per-peran (`app/providers/router.py`): tiap peran — **chat**,
  **embedding**, **STT** — dapat menunjuk endpoint berbeda.
- Variabel `.env` baru (semua opsional): `CHAT_*`, `EMBEDDING_*`, `STT_*`
  (base URL, API key, timeout, retry). `NineRouterProvider` tetap ada sebagai
  subclass agar kompatibel penuh.
- `python run.py --check --live` kini memeriksa katalog **per peran per
  endpoint** (chat/embedding/STT di 9Router dan/atau Ollama).
- Template baru `.env.ollama-hermes.example` (profil hybrid siap pakai) dan
  panduan `PANDUAN_OLLAMA_HERMES.md`.
- Test baru `tests/test_multiprovider.py` (12 test, mock transport).

## Fase 3 — Backup PDF otomatis ke Google Drive

- Setiap PDF yang berhasil di-upload (web maupun bot) dibackup ke
  `Academic_AI/<KODE_MATKUL>/` di Google Drive; file lokal tetap dipakai RAG.
- Best-effort: gagal backup tidak menggagalkan upload (peringatan di log).
  Konten identik tidak di-upload ulang (dedup via sha256). Hapus materi ikut
  menghapus salinan Drive (ID tersimpan di kolom baru `documents.drive_file_id`,
  migrasi otomatis untuk DB lama).
- Dependensi baru: `google-api-python-client`, `google-auth-oauthlib`,
  `google-auth-httplib2` (lihat `requirements.txt`).
- Perintah baru `python run.py --drive-auth` untuk otorisasi OAuth sekali saja.
- Variabel `.env` baru: `GDRIVE_BACKUP_ENABLED` (default mati),
  `GDRIVE_CREDENTIALS_FILE`, `GDRIVE_TOKEN_FILE`, `GDRIVE_ROOT_FOLDER`.
- Panduan `PANDUAN_GDRIVE_BACKUP.md`, test `tests/test_drive_backup.py`
  (7 test, Drive di-mock).

## Fase 4 — n8n + endpoint `/api/stats`

- Endpoint baru `GET /api/stats` (butuh Bearer token): jumlah PDF/chunk dan
  model embedding per matkul + 20 keputusan verifikasi terakhir + waktu server.
  Didukung metode DB baru `get_recent_verifications()`.
- Tiga workflow siap-import di folder `n8n/`: `kuis_harian.json`,
  `auto_ingest_folder.json`, `digest_harian.json`.
- Panduan `PANDUAN_N8N.md` (instal, import, token, Telegram, LAN, troubleshooting).
- Test endpoint ditambahkan ke `tests/test_web_api.py`.

## Verifikasi akhir

- `python -m compileall -q app run.py web_run.py` → OK
- `python -m pytest -q` → **45 passed** (31 awal + 14 baru)
- `node tests/test_agent_office.js` → passed (225 rute)

## Update susulan — Rapikan kode + dokumen arsitektur (8 Okt 2026)

- Standar gaya baru `pyproject.toml` (ruff, baris 100): `ruff check` 48 → 0,
  `ruff format` 68/68 file konsisten. Perbaikan perilaku: `zip(strict=True)`
  di 3 titik (ketidakseimbangan panjang kini gagal keras, bukan sunyi),
  logging pada cleanup upload yang sebelumnya `pass` sunyi.
- Dokumen baru `ARSITEKTUR.md`: kerangka kerja rinci, peta prompt per agent,
  dan solusi anti-miss (7 lapis eksisting + 7 saran R1–R7).
- Verifikasi pasca-rapi: 45/45 pytest hijau + Agent Office lolos.

## Update susulan — Optimasi kuota template gratis (8 Okt 2026)

- `.env.gratis-9router.example`: seluruh Specialist A dipindah dari
  `kr/claude-sonnet-4.5` ke `kr/claude-haiku-4.5` (lebih murah, dipanggil paling
  sering); Manager dinaikkan dari Haiku ke `kr/claude-sonnet-4.5` (juri kuat,
  hanya 1x panggil per ronde). Specialist B tidak berubah.
- `MAX_REVISION_ROUNDS=1` di template (kasus terburuk 6 panggilan/tanya, bukan 9),
  plus komentar pengungkit hemat lain (`MAX_OUTPUT_TOKENS`, `RAG_TOP_K`).
- `SETUP_CHECKLIST.md` bagian 4 disesuaikan. Verifikasi ID ke katalog live tetap
  wajib (`python run.py --check --live`) karena daftar Kiro dapat berubah.

## Update susulan — Sprint offline: jobs, settings, OCR, /mode, ekspor (8 Okt 2026)

Paket A/B/C dari sesi tanya-jawab, semua Rp 0 (kode + Tesseract + Tailscale di sisi user):

- **Ringkasan per topik** — `manager.summarize(topic=...)` memakai jalur retrieval bila topik diisi
  (`/ringkas <topik>` bot, `topic` di `POST /api/summary`); tanpa topik tetap full-corpus.
- **Antrean job** — `POST /api/jobs` (chat/summary/quiz, FIFO 1 worker, maks 50 tersimpan),
  `GET /api/jobs[/id]`; progres tahap via `progress_callback` manager.
- **Ekspor riwayat** — `GET /api/export?subject_code=&format=md|txt` (maks 500 pesan).
- **Pengaturan runtime** — `Settings` mutable, `GET/PATCH /api/settings` (validasi-semua-dulu,
  tulis `.env` preservatif, secret dimask), `python run.py --set-password`.
- **OCR scan** — fallback Tesseract otomatis (ind+eng, maks 80 hlm); `pypdfium2`+`pytesseract`
  masuk requirements; pesan error jujur bila biner belum diinstal.
- **`/mode`** — preset Singkat/Seimbang/Mendalam (bot tombol + dropdown web).
- **Web UI** — progress bar job untuk ringkas/kuis, panel Pengaturan, tombol Ekspor,
  helper JS teruji (`tests/test_web_ui.js`).
- **n8n** — `n8n/academic_webhook.json` (Webhook → `/api/chat` → Respond).
- **Stabilitas tes** — harness JS memakai jam tetap (tes office sebelumnya gagal saat
  dibaca di dalam jendela waktu sholat karena semua worker berstatus praying).

Verifikasi: `pytest` 89 passed (termasuk 2 tes Node), `ruff check` + `ruff format` bersih.

## Cara upgrade dari versi lama

1. Backup folder project lama (terutama `.env` dan `data/`).
2. Timpa/salin versi baru, lalu salin kembali `.env` dan `data/` milikmu.
3. `python -m pip install -r requirements.txt` (ada dependensi Google baru).
4. Jalankan seperti biasa (`run.py` / `web_run.py`). Kolom DB baru dibuat
   otomatis. Aktifkan fitur baru sesuai panduan masing-masing bila perlu.
