# INTEGRATION PLAN — PHASE 6 IMPLEMENTATION ROADMAP
**Dokumen Referensi: Phase 6.0 Integration Audit & Job System Architecture Blueprint**
*Rencana Bertahap: Zero Breaking Change & Windows/CMD Compatible*
*Klasifikasi Status Komponen: `PROPOSED`*
*Tanggal Rilis: 13 November 2026*

---

## 1. TAHAPAN IMPLEMENTASI (PHASED ROLLOUT)

Implementasi Phase 6 dibagi menjadi sub-fase terkontrol untuk menjamin stabilitas sistem:

```
[ Phase 6.0: Audit & Blueprint ] (Selesai - Tidak Mengubah Kode)
             │
             ▼
[ Phase 6.1: HQ Job Core & SQLite Engine ] (Tabel jobs & event_log non-destruktif)
             │
             ▼
[ Phase 6.2: Division Adapters ] (Adapter Social Media & Academic AI)
             │
             ▼
[ Phase 6.3: Orchestrator & Task Planner ] (Dekomposisi tugas & dependency resolver)
             │
             ▼
[ Phase 6.4: UI Bridge & Three.js Activity Sync ] (Sinkronisasi status visual real-time)
             │
             ▼
[ Phase 6.5: End-to-End Verification & Owner Sign-off ]
```

---

## 2. DETAIL SUB-FASE

### Phase 6.1 — HQ Job Core & Persistent Queue
* **Tujuan:** Membuat tabel baru `hq_jobs` dan `hq_event_logs` di database SQLite terpisah (`data/hq_core.db`) tanpa menyentuh tabel eksisting `episodes.db`.
* **Komponen:**
  - `src/hq/queue.py` (Metode `enqueue`, `acquire_lease`, `complete_job`, `fail_job`).
  - Mekanisme atomic SQLite transaction (`BEGIN IMMEDIATE`) untuk mencegah *race condition*.

### Phase 6.2 — Division Adapters
* **Tujuan:** Membangun antarmuka komunikasi bersih ke dua divisi utama:
  - `SocialMediaAdapter`: Menghubungkan job engine ke `hermes_create_draft`, `mausbot_card_decision`, `queue4_decision`, `ootto_schedule`.
  - `AcademicAIAdapter`: Menghubungkan job engine ke kurikulum 7 departemen di `maru_knowledge_base.md` & `maru_v2_system.py`.

### Phase 6.3 — Orchestrator & Task Planner
* **Tujuan:** Membangun logika pendelegasian tugas Bima $\to$ Agen spesialis dengan alokasi budget dan pemenuhan kriteria penerimaan.

### Phase 6.4 — Dashboard UI Bridge & Three.js Sync
* **Tujuan:** Menyajikan telemetri job aktif ke panel `studio_bulletproof.html` dan menggerakkan visualizer 3D Three.js hanya saat job benar-benar berjalan di worker.

---

## 3. STRATEGI TESTING & ACCEPTANCE CRITERIA
1. **Backward Compatibility:** Seluruh 5 pengujian regresi lama (`test_regression_phase1.py` s/d `test_regression_phase5b.py`) wajib lulus 100% tanpa modifikasi.
2. **Local Windows Readiness:** Seluruh modul dapat dijalankan via perintah standar `python -m src.hq.server` di CMD / PowerShell tanpa Docker/WSL.
3. **Idempotency Test:** Memasukkan task yang sama 2x tidak menghasilkan duplikasi job di database.
