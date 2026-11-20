# PHASE 6.1.1 FILE INVENTORY & MAPPING
**MARU HQ — Repository Alignment & File Inventory**
*Repository: `aryawisnu250376-beep/testing-maru-ai`*
*Branch: `feat/phase-6-1-1-hardening`*
*Tanggal Rilis: 13 November 2026*

---

## 1. INVENTARISASI STRUKTUR UTAMA FOLDER

| Folder / Path | Deskripsi & Isi Faktual | Status Fungsional |
|---|---|---|
| `src/hq/` | Modul HQ Core: `models.py`, `database.py`, `queue.py`, `worker.py`, `__init__.py`. | `IMPLEMENTED` |
| `01-social-media-agent/` | Divisi Social Media: Web dashboard UI, skrip otomasi pipeline, 44 skill, server lokal. | `IMPLEMENTED` |
| `01-social-media-agent/src/studio.html` | **Source Kantor 3D Resmi & Dashboard MARU HQ**. | `IMPLEMENTED` |
| `02-academic-ai/` | Divisi Academic AI: Bot Telegram, Technician, Research RAG, kurikulum, dan web UI. | `IMPLEMENTED` |
| `skills/` | Koleksi 68 skill agen AI (academic, social-media, shared, learned). | `IMPLEMENTED` |
| `docs/` | 16 dokumen arsitektur, spesifikasi kontrak, registri agen, database & risiko. | `IMPLEMENTED` |
| `data/` | Direktori database lokal (`data/hq_core.db` untuk HQ Core, `data/episodes.db` untuk media). | `IMPLEMENTED` |
| `tests/hq/` | *(Akan Dibuat)* Test suite kanonikal Phase 6.1.1 untuk HQ Core Engine. | `PROPOSED` |

---

## 2. INVENTARISASI FILE KANTOR 3D & DASHBOARD
1. `01-social-media-agent/src/studio.html` (155 KB) — **Sumber Kebenaran Kantor 3D Resmi MARU HQ**.
2. `02-academic-ai/app/web/index.html` (238 KB) — Web client divisi akademik (bukan kantor 3D resmi HQ).

---

## 3. INVENTARISASI FILE KURIKULUM & KNOWLEDGE BASE
1. `maru_knowledge_base.md` — Rangkuman kurikulum 7 departemen komunikasi dari materi UTS STIAMI.
2. `maru_v2_system.py` — Definisi kode Python kurikulum DEP_01 s/d DEP_07 & rotasi jadwal siaran 7 hari.
