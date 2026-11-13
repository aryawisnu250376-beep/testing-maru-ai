# PHASE 6.1 DATABASE SPECIFICATION & ISOLATION REPORT
**MARU HQ — Multi-Agent Integration & Real Job Execution Control Plane**
*Status: TERISOLASI 100% DI data/hq_core.db*
*Tanggal Rilis: 13 November 2026*

---

## 1. PRE-FLIGHT VERIFIKASI DATABASE EKSISTING
Sebelum implementasi Phase 6.1, audit menyeluruh membuktikan:
* File database operasional media sosial yang tercatat pada konfigurasi adalah `data/episodes.db`.
* Istilah `studio.sqlite3` tidak ditemukan sebagai berkas fisik mandiri di repositori saat ini.
* Seluruh operasi Phase 6.1 **sama sekali tidak mengakses atau memodifikasi tabel lama** (`queue4`, `mausbot_cards`, `episodes`).

---

## 2. SKEMA DATABASE TERISOLASI: data/hq_core.db
Database baru dibuat di `data/hq_core.db` dengan pragmas:
```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
```

### A. Tabel `hq_jobs`
```sql
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
    budget_payload TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    lease_owner TEXT,
    lease_expires_at REAL,
    fencing_token INTEGER DEFAULT 0,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    result_payload TEXT,
    error_message TEXT
);
```

### B. Tabel `hq_event_logs`
```sql
CREATE TABLE IF NOT EXISTS hq_event_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    fencing_token INTEGER DEFAULT 0,
    previous_state TEXT,
    new_state TEXT,
    details TEXT,
    timestamp REAL NOT NULL,
    FOREIGN KEY(task_id) REFERENCES hq_jobs(task_id)
);
```
