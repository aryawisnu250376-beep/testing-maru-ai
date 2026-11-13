# Laporan Pengujian Kanonikal Phase 6.1.1 (Test Report)
**Tanggal**: 2026-11-02  
**Suite Pengujian**: `tests/hq/test_job_engine.py`  
**Runner**: `tests/hq/run_all.py`  
**Total Kasus**: 26  
**Lulus**: 26 (100%)  
**Gagal**: 0  
**Error**: 0  
**Durasi Eksekusi**: 12.933 detik  

---

## 1. Rincian Metrik Pengujian

### A. Idempotensi & Integritas Payload
- **Kasus 01 (`test_01_enqueue_single_job`)**: Job berhasil dibuat dengan status `PENDING`, ID kanonikal diterbitkan, dan hash payload dihitung secara deterministik.
- **Kasus 02 (`test_02_enqueue_duplicate_same_payload`)**: Enqueue ulang dengan `idempotency_key` dan payload identik mengembalikan job eksisting tanpa penambahan record.
- **Kasus 03 (`test_03_enqueue_duplicate_different_payload_conflict`)**: Enqueue ulang dengan `idempotency_key` yang sama namun payload berbeda berhasil menolak operasi dan melempar `IdempotencyConflictError`.

### B. Konkurensi & Lease Management Multi-Worker
- **Kasus 04 (`test_04_concurrent_enqueue_multithread`)**: 10 worker/thread melakukan submit job secara simultan; seluruh job tercatat tanpa terjadi `database locked`.
- **Kasus 05 (`test_05_two_workers_competing_lease`)**: Dua worker mencoba mengambil job yang sama pada mikrodetik yang sama; sistem menjamin tepat satu worker yang mendapatkan hak sewa (`RUNNING`), sementara worker kedua mendapatkan `None`.
- **Kasus 06 (`test_06_lease_renewal`)**: Thread heartbeat worker berhasil memperbarui `lease_expires_at` secara periodik sebelum kadaluarsa.
- **Kasus 07 (`test_07_lease_expiry`)**: Job yang ditinggalkan worker hingga masa sewa habis otomatis dapat di-reclaim oleh worker lain.
- **Kasus 08 (`test_08_old_fencing_token_rejected`)**: Percobaan manipulasi status job menggunakan `fencing_token` usang diblokir secara mutlak.
- **Kasus 09 (`test_09_complete_by_valid_worker`)**: Penyelesaian job oleh worker pemilik sewa yang sah berjalan sukses (`COMPLETED`).
- **Kasus 10 (`test_10_complete_by_stale_worker_rejected`)**: Upaya penyelesaian job oleh worker yang sewanya telah diambil alih ditolak dengan melempar `LeaseExpiredError`.
- **Kasus 11 (`test_11_fail_by_valid_worker`)**: Pelaporan error oleh worker aktif memicu mekanisme retry.
- **Kasus 12 (`test_12_fail_by_expired_worker_rejected`)**: Pelaporan error oleh worker kadaluarsa diblokir oleh antrean.

### C. Siklus Hidup Retry, Dead-Letter & Dependensi
- **Kasus 13 (`test_13_retry_up_to_max_attempts`)**: Job gagal otomatis dinaikkan hitungan `retry_count` dan dijadwalkan ulang ke status `PENDING`.
- **Kasus 14 (`test_14_dead_letter_transition`)**: Setelah mencapai kuota maksimal (`max_retries = 2`), job bertransisi ke status `DEAD_LETTER`.
- **Kasus 15 (`test_15_dependency_not_satisfied_skipped`)**: Job yang memiliki dependensi tertunda tidak dapat di-lease oleh worker.
- **Kasus 16 (`test_16_dependency_satisfied_success`)**: Segera setelah job induk selesai (`COMPLETED`), job turunan dapat di-lease dan diselesaikan.
- **Kasus 17 (`test_17_dependency_failed_cascades`)**: Kegagalan job induk secara otomatis menggagalkan job turunan (`FAILED`) untuk mencegah eksekusi sia-sia.

### D. Keamanan Worker, Heartbeat & Budget
- **Kasus 18 (`test_18_cancellation_during_handler`)**: Handler eksekusi mendeteksi sinyal `token.is_cancelled` saat dibatalkan dari luar.
- **Kasus 19 (`test_19_worker_loses_lease_during_handler`)**: Jika sewa dicabut atau diambil alih, `CancellationToken` worker otomatis aktif untuk memutus proses secara kooperatif.
- **Kasus 20 (`test_20_startup_recovery`)**: Saat worker melakukan bootstrap/restart, job zombie peninggalan crash sebelumnya langsung dipulihkan ke status `PENDING`.
- **Kasus 25 (`test_25_budget_duration_limit_exceeded`)**: Job yang berjalan melebihi batas durasi budget (`max_duration_seconds = 1`) dihentikan paksa dan ditandai gagal.

### E. Integritas Database & Isolasi
- **Kasus 21 (`test_21_restart_db_connection`)**: Penutupan dan pembukaan kembali koneksi database tetap mempertahankan seluruh data job dan riwayat event.
- **Kasus 22 (`test_22_wal_mode`)**: SQLite beroperasi penuh dalam mode `journal_mode = WAL`.
- **Kasus 23 (`test_23_sqlite_integrity_check`)**: `PRAGMA integrity_check` mengembalikan status `ok`.
- **Kasus 24 (`test_24_event_log_consistent`)**: Seluruh transisi status tercatat kronologis pada tabel `hq_job_events`.
- **Kasus 26 (`test_26_legacy_database_untouched`)**: Database divisi lama (`data/maru.db`) tidak tersentuh, dimodifikasi, ataupun terpengaruh oleh operasi HQ Core.

---

## 2. Kesimpulan Pengujian
Semua kriteria fungsional dan non-fungsional antrean persisten kanonikal Phase 6.1.1 terbukti **100% andal, terverifikasi, dan aman untuk konkurensi produksi**.
