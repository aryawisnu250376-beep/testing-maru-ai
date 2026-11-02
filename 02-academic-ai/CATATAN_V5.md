# CATATAN VERSI 5 — AI TEKNISI (PERBAIKAN BUG OTOMATIS)
Tanggal: 9 Oktober 2026 · Dasar paket: v4 (lihat CATATAN_V4.md)

Penambahan utama rilis ini adalah **AI Teknisi**: montir AI di dalam aplikasi yang
mencari sendiri sumber error lalu memperbaikinya — dari salah konfigurasi model
sampai bug di kode program.

---

## 1. Apa yang bisa dilakukan AI Teknisi

1. **Pemantauan terus-menerus** — membaca `data/logs/*.log`, pesan error runtime
   (traceback), dan cache `data/error_responses.json` milik Agent Office.
2. **Pemeriksaan kesehatan (health check)** — katalog model vs `.env`, endpoint
   Manager/9Router/embedding/STT, `NINE_ROUTER_TIMEOUT`, `OLLAMA_CONTEXT_LENGTH`,
   `MODEL_MANAGER`, model 7 mata kuliah (A/B/C), model embedding.
3. **Perbaikan aman otomatis (mode `safe`)** — contoh: `MODEL_MANAGER` tidak ada
   di katalog (akibat 404 saat verifikasi) → otomatis diganti model yang benar-benar
   tersedia; timeout terlalu pendek → dinaikkan ke 300 detik. Hasilnya ditulis ke
   `.env` (backup nilai lama tercatat) + jejak audit di `data/fix_journal.jsonl`.
4. **Perbaikan kode oleh AI (mode `full`)** — AI Manager menganalisis error,
   menambal kode sumber; file asli dibackup ke `data/patches/<batch>/originals/`,
   diuji otomatis dengan `pytest`, dan **langsung di-rollback bila tes gagal**.
   Tombol **Rollback Terakhir** di web mengembalikan patch terakhir secara manual.
5. **Laporan ringkas** — diagnosis, daftar masalah (kode ERROR/WARNING), daftar
   perbaikan, dan status komponen, tampil di panel web dan endpoint API.

## 2. Cara pakai

### Dari web
Login → panel **"05 AI Teknisi"** → *Pindai Sekarang (Mode Aman)* atau
*(Mode Penuh)* → baca *Hasil Inspeksi* → *Rollback Terakhir* bila perlu.

### Dari API
```
GET  /api/technician/status     # status + jejak perbaikan terakhir
POST /api/technician/scan       # {"mode": "safe"} atau {"mode": "full"}
POST /api/technician/rollback   # kembalikan patch AI terakhir
```
Semua butuh token lokal seperti endpoint lain (Bearer `LOCAL_API_TOKEN`).

### Konfigurasi baru di `.env`
```
TECHNICIAN_ENABLED=true        # aktifkan AI Teknisi
TECHNICIAN_AUTO=true           # pindai otomatis di latar belakang
TECHNICIAN_MODE=safe           # safe = konfigurasi saja; full = boleh menambal kode
TECHNICIAN_INTERVAL_MIN=30     # interval pindai otomatis (5–1440 menit)
TECHNICIAN_CODE_FIX=true       # izinkan mode penuh memperbaiki kode
```
Sudah tercantum di keempat template `.env.*.example`.

## 3. Keamanan

- Perbaikan konfigurasi hanya menyentuh kunci terkait model/timeout di `.env`.
- Perubahan kode: hanya file `app/`, `tools/`, `web_run.py`, `run.py` berakhiran
  `.py`, maksimal 5 file per batch; teks yang dicari (`find_text`) harus unik —
  bila ragu, tambalan dilewati (tidak pernah menebak posisi).
- Backup otomatis sebelum setiap tambalan; `pytest` otomatis setelahnya;
  gagal = rollback otomatis. Semua tercatat di `data/fix_journal.jsonl`.

## 4. Isi paket v5 (perubahan vs v4)

| Bagian | Perubahan |
|---|---|
| `app/technician/` (baru) | `collector` (pengumpul error dari log), `checks` (health check), `fixers` (perbaikan config aman), `coder` (diagnosis + tambal kode + rollback), `service` (orkestrator + mode otomatis) |
| `app/config.py` | 5 kunci `TECHNICIAN_*` baru |
| `app/web/api.py` | 3 endpoint `/api/technician/*` + auto-scan di latar belakang |
| `app/web/index.html` | panel **"05 AI Teknisi"** + tombol pindai/rollback + laporan |
| `tests/test_technician.py` (baru) | 10 tes: pengumpul error, health check, perbaikan config, tambal kode + auto-rollback, rollback manual, orkestrator, API web |
| Template `.env.*.example` | kunci `TECHNICIAN_*` |
| `build_manual_docx.py` | seksi 14 "AI Teknisi" + MANUAL_BOOK_PEMASANGAN.docx baru |
| Sisanya | **sama persis dengan v4** (skill GitHub, 3 agen/mata kuliah, probe_models, Manager Ollama, dll.) |

## 5. Hasil pengujian akhir

- `python -m pytest tests/ --ignore=tests/test_video.py --ignore=tests/test_agent_office.py`
  → **111 tes lulus** (101 tes lama + 10 tes AI Teknisi), tanpa kegagalan.
- Uji asap `python run.py --check` dengan template hybrid: **22 model terisi**
  (21 agen + Manager), 7 mata kuliah terdeteksi, konfigurasi lokal lengkap.
- `node --check` untuk JavaScript panel baru: valid.

## 6. Catatan

- Setelah mengganti endpoint/akun AI, tetap jalankan `python tools/probe_models.py`.
- Mode `full` memanggil model untuk mendiagnosis error — pastikan `MODEL_MANAGER`
  valid (`ollama list` untuk Manager lokal).
- Paket data `academic_ai_data_v3.zip` tidak berubah; PDF lama perlu di-upload
  ulang bila ingin memakai chunking baru (turunan teks per halaman).
