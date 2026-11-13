# PANDUAN VERIFIKASI INDEPENDEN — MARU HQ PHASE 6.1.1
**Untuk**: Pemilik MARU HQ  
**Tanggal**: 2026-11-02  
**Repositori**: `testing-maru-ai`  
**Branch**: `feat/phase-6-1-1-hardening` (Commit: `2787a91`)

---

## 1. Link Unduhan Paket ZIP (Google Drive)

Sesuai permintaan pemilik, paket ZIP repositori lengkap telah di-generate langsung dari workspace lokal dan diunggah ke Google Drive dengan status akses publik (siapa saja yang memiliki tautan dapat mengunduh):

- **Tautan Utama (`maru_v3_update.zip`)**:  
  👉 **`https://drive.google.com/file/d/1HJmnisNYNg0KSMQpTx6MbIqlYji9zzes/view?usp=drivesdk`**  
  *(Ukuran: 2.55 MB, 461 berkas)*

- **Tautan Salinan Resmi (`hasil tugas 1.zip`)**:  
  👉 **`https://drive.google.com/file/d/14OV7_wRrTEXe8B88YKemoEmtQ7BS-pYI/view?usp=drivesdk`**  
  *(Ukuran: 2.55 MB, nama sesuai instruksi standing constraint)*

---

## 2. Cara Ekstraksi & Menjalankan Verifikasi Independen (Windows PowerShell)

Pemilik dapat melakukan audit dan verifikasi 26 test suite secara independen di laptop/PC lokal dengan langkah sederhana berikut:

```powershell
# 1. Ekstrak file zip ke folder kerja lokal
Expand-Archive -Path "$HOME\Downloads\maru_v3_update.zip" -DestinationPath "$HOME\maru_audit" -Force
cd "$HOME\maru_audit"

# 2. Jalankan test suite kanonikal Phase 6.1.1 (Single Command)
python -m tests.hq.run_all

# --- blok selesai ---
```

**Hasil yang Diharapkan**:
```text
======================================================================
MARU HQ — PHASE 6.1.1 CANONICAL TEST SUITE (26 ACCEPTANCE CHECKS)
======================================================================
... (seluruh 26 test berstatus ok) ...
Ran 26 tests in ~12s
RESULT: PASS (100% SUCCESS)
```

---

## 3. Pembuktian Tiga Kriteria Utama Pemilik

### A. Implementasi Benar-Benar Sesuai Laporan
- Modul antrean kanonikal `src/hq/` telah dilengkapi pertahanan konkurensi:
  - `src/hq/models.py`: Custom exceptions (`IdempotencyConflictError`, `BudgetExceededError`, `DependencyNotSatisfiedError`, dll) dan `payload_hash`.
  - `src/hq/database.py`: Tabel `hq_canonical_jobs` memiliki kolom `payload_hash` dan indeks komposit untuk lookup cepat. SQLite WAL mode aktif.
  - `src/hq/queue.py`: Penolakan tegas idempotency collision jika payload berbeda; dependency satisfaction gating; fencing token increment.
  - `src/hq/worker.py`: Heartbeat non-blocking (`stop_heartbeat.wait()`), pengoperan `CancellationToken`, startup recovery job orphan, dan budget duration limit.

### B. Tidak Ada Regresi pada Codebase Lama
- **Isolasi Database**: DDL dan DML HQ Core 100% dialokasikan ke `data/hq_core.db`. File database divisi lama `data/maru.db` tidak pernah dibuka, dimodifikasi, atau diubah skemanya (terbukti lolos di `test_26_legacy_database_untouched`).
- **Pipeline Eksisting Utuh**: Pengujian pipeline social media agent eksisting (`tests/test_pipeline.py`) dijalankan dan lulus 100% (`16 passed in 0.8s`).
- **Kantor 3D Three.js Asli Terjaga**: File kantor 3D Three.js kanonikal berukuran 155 KB di `01-social-media-agent/src/studio.html` (SHA256: `6c3ee4133bb8...`) tetap utuh tanpa modifikasi destruktif.

### C. Fondasi Siap Digunakan untuk HQ Intelligence Berikutnya
- Rantai pekerjaan multi-agent kini dapat dihubungkan via dependensi (`dependencies=[job_id_1, job_id_2]`).
- Eksekusi agent dapat dibatalkan sewaktu-waktu secara kooperatif (`token.is_cancelled`).
- Worker aman dari race-condition split-brain dan zombie job peninggalan crash.
