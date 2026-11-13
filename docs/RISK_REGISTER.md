# RISK REGISTER & MITIGATION STRATEGY — PHASE 6
**Dokumen Referensi: Phase 6.0 Integration Audit & Job System Architecture Blueprint**
*Matriks Risiko Teknis, Dampak & Tindakan Pencegahan*
*Klasifikasi Status Komponen: `PROPOSED`*
*Tanggal Rilis: 13 November 2026*

---

## 1. MATRIKS RISIKO UTAMA

| No | Kategori Risiko | Deskripsi Risiko | Dampak | Probabilitas | Rencana Mitigasi Teknis |
|---|---|---|---|---|---|
| 1 | **Database Concurrency** | Akses bersamaan ke SQLite saat antrean padat memicu error `database is locked` di Windows CMD. | Tinggi | Sedang | Aktifkan WAL Mode (`PRAGMA journal_mode=WAL`), gunakan `busy_timeout=5000` ms, dan batasi koneksi penulisan dengan mutex lokal. |
| 2 | **Stale Job / Zombie Worker** | Worker crash saat mengeksekusi job, menyebabkan job selamanya berstatus `RUNNING`. | Tinggi | Rendah | Terapkan mekanisme *lease expiration* (30 detik). Heartbeat monitor secara otomatis mereset job kedaluwarsa kembali ke status `QUEUED`. |
| 3 | **Accidental External Action** | Agen mengirim video publik ke TikTok tanpa persetujuan manual pemilik HQ. | Kritis | Rendah | Hardcoded policy check di server: bypass frontend ditolak jika flag `decision !== 'SETUJU'` di database. |
| 4 | **Budget Overrun** | Loop generasi naskah LLM yang macet menghabiskan kuota token/biaya API. | Tinggi | Rendah | Evaluasi konsumsi token per iterasi; hentikan task otomatis jika total biaya mencapai `budget.max_cost_idr`. |
| 5 | **Breaking Existing UI** | Integrasi API baru merusak fungsi polling dashboard lama `/api/state`. | Kritis | Rendah | Buat endpoint baru `/api/hq/*` terisolasi; pertahankan response schema `/api/state` 100% identik dengan versi Phase 5B. |
| 6 | **Prompt Injection** | Konten media sosial eksternal memanipulasi instruksi agen penulisan naskah. | Sedang | Sedang | Isolasi input pengguna di dalam parameter `input_payload`, filter keyword instruksi berbahaya, dan batasi output ke format JSON terstruktur. |
