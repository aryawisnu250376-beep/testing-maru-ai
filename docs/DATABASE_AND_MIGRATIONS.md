# DATABASE & MIGRATIONS — MARU HQ
**Dokumen Referensi: Phase 6.0 Integration Audit & Job System Architecture Blueprint**
*Strategi Penyimpanan SQLite Terisolasi & Rencana Skema Non-Destruktif*
*Klasifikasi Status Komponen: `PROPOSED`*
*Tanggal Rilis: 13 November 2026*

---

## 1. INVENTARIS DATABASE EKSISTING (ZERO DESTRUCTIVE CHANGES)

### Database Pasif Divisi Social Media: `data/episodes.db`
* **Status:** **TIDAK BOLEH DIUBAH / TIDAK DIHAPUS (IMMUTABLE)**.
* **Tabel Eksisting:**
  - `queue4`: Menyimpan antrean draf konten media sosial (`id`, `judul`, `naskah`, `status`, `gaya_referensi`).
  - `mausbot_cards`: Menyimpan perizinan ACC (`id`, `title`, `summary`, `status`, `decision`, `reason`).
  - `episodes`: Menyimpan riwayat episode video penyiaran.
  - `reference_creators`: Menyimpan profil kreator acuan formula hook.

---

## 2. USULAN DATABASE BARU HQ CORE: `data/hq_core.db`

Untuk mencegah konflik dan menjaga arsitektur *clean architecture*, seluruh antrean pekerjaan Phase 6 ditempatkan pada file database terpisah yang menggunakan **SQLite Write-Ahead Logging (WAL)**:

```sql
-- TABEL PERSISTENT JOB QUEUE
CREATE TABLE IF NOT EXISTS hq_jobs (
    task_id TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    parent_task_id TEXT,
    division TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    goal TEXT NOT NULL,
    input_payload TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,
    priority INTEGER DEFAULT 1,
    status TEXT NOT NULL,
    assigned_agent TEXT NOT NULL,
    dependencies TEXT DEFAULT '[]',
    budget_idr INTEGER DEFAULT 10000,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    lease_owner TEXT,
    lease_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    result_payload TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_hq_jobs_status_priority ON hq_jobs(status, priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_hq_jobs_correlation ON hq_jobs(correlation_id);

-- TABEL AUDIT & EVENT LOG TERPERINCI
CREATE TABLE IF NOT EXISTS hq_event_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES hq_jobs(task_id)
);

CREATE INDEX IF NOT EXISTS idx_hq_events_task_id ON hq_event_logs(task_id);
```

---

## 3. STRATEGI BACKUP & ROLLBACK OTOMATIS
1. **Pencadangan Sebelum Transaksi:** Skrip eksekusi wajib membuat salinan cadangan snapshot `data/episodes.db.bak` dan `data/hq_core.db.bak` secara teratur.
2. **Koneksi Terkunci Bersih:** Menggunakan timeout `busy_timeout = 5000` ms untuk mencegah error `database is locked` pada Windows.
3. **Rollback Strategy:** Jika migrasi tabel baru gagal, cukup hapus file `data/hq_core.db` tanpa memengaruhi fungsi web dashboard utama sedikitpun.
