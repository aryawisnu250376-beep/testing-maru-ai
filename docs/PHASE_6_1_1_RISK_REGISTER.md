# Register Risiko & Mitigasi Phase 6.1.1 (Risk Register)
**Status**: AKTIF & TERKONTROL  
**Tanggal**: 2026-11-02  

---

| ID Risiko | Deskripsi Risiko | Tingkat Dampak | Probabilitas | Status Penanganan | Strategi Mitigasi / Implementasi Aktual |
|---|---|---|---|---|---|
| **RSK-01** | Konflik Idempotensi / Race Condition Duplikasi Job | TINGGI | SEDANG | **TERATASI (100%)** | Diterapkan penghitungan `payload_hash` SHA-256 kanonikal. Jika `idempotency_key` sama dengan payload berbeda, sistem menolak transaksi dengan `IdempotencyConflictError`. Jika payload sama, job eksisting dikembalikan. Diuji di Kasus 02 & 03. |
| **RSK-02** | Stale Worker / Split-Brain Modifikasi Job Kadaluarsa | TINGGI | SEDANG | **TERATASI (100%)** | Diterapkan fencing token monotonik yang bertambah di setiap renewal dan akuisisi sewa. Worker kadaluarsa yang mencoba `complete_job` atau `fail_job` langsung ditolak dengan `LeaseExpiredError`. Diuji di Kasus 08, 10, & 12. |
| **RSK-03** | Race Condition Multi-Worker pada SQLite Database | SEDANG | TINGGI | **TERATASI (100%)** | Diaktifkan SQLite WAL Mode (`PRAGMA journal_mode=WAL`), `PRAGMA busy_timeout=5000`, dan transaksi `BEGIN IMMEDIATE` pada level antrean untuk mencegah lock contention. Diuji di Kasus 04, 05, & 22. |
| **RSK-04** | Job Zombie / Orphan Akibat Worker Crash Mendadak | SEDANG | SEDANG | **TERATASI (100%)** | Mekanisme `startup_recovery()` pada worker mengidentifikasi job yang berstatus `RUNNING` dengan `lease_expires_at` yang telah kadaluarsa saat worker pertama kali booting, lalu mengembalikannya ke `PENDING` atau `DEAD_LETTER`. Diuji di Kasus 20. |
| **RSK-05** | Eksekusi Job Terperangkap dalam Infinite Loop / Over-budget | TINGGI | RENDAH | **TERATASI (100%)** | Diterapkan `JobBudget(max_duration_seconds=...)`. Handler worker dipantau oleh timer presisi; bila melampaui batas, job diputus dan ditandai gagal. Diuji di Kasus 25. |
| **RSK-06** | Eksekusi Anak Job Sebelum Induk Selesai atau Gagal Terabaikan | TINGGI | SEDANG | **TERATASI (100%)** | Evaluasi dependensi bertingkat pada `acquire_lease()`. Job ditahan (`PENDING`) hingga seluruh dependensi `COMPLETED`. Jika salah satu dependensi berstatus `FAILED`/`DEAD_LETTER`, cascading failure membatalkan seluruh rantai hilir. Diuji di Kasus 15, 16, & 17. |
| **RSK-07** | Perusakan atau Perubahan Destruktif pada Database Warisan (`data/maru.db`) | KRITIS | RENDAH | **TERATASI (100%)** | Isolasi total DDL dan DML HQ Core pada file terpisah `data/hq_core.db`. Tidak ada kode HQ Core yang menulis atau mengubah skema `data/maru.db`. Diuji di Kasus 26. |
| **RSK-08** | Inkonsistensi Visual Kantor 3D Akibat Berkas Duplikat | SEDANG | SEDANG | **TERATASI (100%)** | Dilakukan audit SHA256; berkas `01-social-media-agent/src/studio.html` ditetapkan sebagai Satu-Satunya Sumber Resmi (Single Source of Truth). Seluruh integrasi visual mengacu ke berkas ini. |
