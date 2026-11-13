# CODEBASE MAP — MARU HQ INTEGRATION AUDIT
**Dokumen Referensi: Phase 6.0 Integration Audit & Job System Architecture Blueprint**
*Klasifikasi Status Komponen: `VERIFIED` | `PARTIAL` | `NOT AVAILABLE` | `PROPOSED`*
*Tanggal Rilis: 13 November 2026*

---

## 1. STRUKTUR UTAMA FOLDER & FILE PROYEK

```
MARU HQ Repository Root/
├── studio_bulletproof.html             [VERIFIED] UI Dashboard Utama, Autentikasi, Kanban & Three.js 3D HQ
├── studio_bulletproof.html.bak-phase*   [VERIFIED] Arsip Rollback Cadangan Fase 1 s/d Fase 5B
├── maru_v2_system.py                   [VERIFIED] Spesifikasi 7 Departemen Edukasi & Rotasi Konten 7 Hari
├── maru_knowledge_base.md              [VERIFIED] Basis Pengetahuan Kurikulum Akademik Ilmu Komunikasi
├── maru_fullbody.png                   [VERIFIED] Aset Karakter Pixel Art Fullbody Resmi MARU HQ
├── maru_app_icon_1024.png              [VERIFIED] Aset Ikon Aplikasi Resmi 1024x1024 Pixel Art
├── maru_voice_young_pro.mp3            [VERIFIED] Sample Audio Dubbing Karakter Muda Resmi
├── maru_office_phase4_render.png       [VERIFIED] Render Referensi Visual Arsitektur Kantor 3D
├── docs/                               [PROPOSED] Folder Dokumentasi Arsitektur & Kontrak Integrasi
└── uploads/                            [PARTIAL]  Penyimpanan Aset Unggahan Video / Gambar
```

---

## 2. INVENTARISASI KOMPONEN DETAIL & STATUS STATUSNYA

| Kategori | File / Entitas | Status | Keterangan & Fungsionalitas Aktual |
|---|---|---|---|
| **Entrypoint UI** | `studio_bulletproof.html` | `VERIFIED` | Single-page application dashboard aktif (HTML5 + Vanilla JS IIFE + Tailwind/CSS Variables + Three.js r128). |
| **Backend Server** | Local Python Server (`/api/state`, `/api/action`) | `PARTIAL` | Endpoint terdefinisi di UI (`/api/state`, `/api/action`, `/api/login`), menangani draf, kartu MausBot, dan polling status. |
| **Database** | SQLite (`episodes.db` / `data/episodes.db`) | `PARTIAL` | Skema tabel `queue4`, `mausbot_cards`, `episodes`, `employees` diakses via adapter Python lokal. |
| **Visualizer 3D** | `window.MaruOffice3D` | `VERIFIED` | Engine Three.js isometrik 1 lantai terpadu, 14 ruangan, 27 karakter (9 Pemimpin + 18 NPC Dekoratif). |
| **Knowledge Base** | `maru_knowledge_base.md` | `VERIFIED` | 7 departemen kurikulum komunikasi hasil ekstraksi UTS STIAMI terverifikasi lengkap. |
| **Rotasi Konten** | `maru_v2_system.py` | `VERIFIED` | Spesifikasi kurikulum DEP_01 s/d DEP_07 dan jadwal siaran 7 hari. |
| **Job Queue Engine** | Persistent HQ Task Planner | `PROPOSED` | Belum ada engine antrean tugas berbasis tabel SQLite terpusat dengan lease/lock (Sasaran Phase 6). |
| **Telegram Bot** | Bot Interaksi Hermes/Maus | `NOT AVAILABLE` | Belum ditemukan file bot Telegram aktif mandiri di repository root; integrasi saat ini via web dashboard. |
| **Vector Store / RAG** | Vector DB / Chunker PDF | `NOT AVAILABLE` | Materi saat ini berformat Markdown terstruktur; belum menggunakan embeddings/vector store. |
| **TikTok Direct Post** | Content Posting API flow | `PARTIAL` | Skrip pengujian alur otorisasi dan endpoint Sandbox tersedia (`test_direct_post_mock.py`, dll). |

---

## 3. PEMISAHAN LOGIS DUA DIVISI UTAMA

### A. Divisi 1: Social Media Corporation
* **Fokus:** Perancangan konten TikTok vertikal 9:16, hook 3 detik, review etika penyiaran, persetujuan ACC Maus, dan distribusi rilis.
* **Database Pasif:** Tabel `queue4`, `mausbot_cards`, `episodes`.
* **Agen Terkait:** Bima, Hermes, Nara, Maus, Kirana, Ardi, Ootto.

### B. Divisi 2: Academic AI
* **Fokus:** Kurikulum 7 departemen ilmu komunikasi (Pancasila, Adab, Bahasa Inggris, PR, Pengantar Komunikasi, Komunikasi Antarpribadi, Jurnalistik).
* **Knowledge Source:** `maru_knowledge_base.md` & `maru_v2_system.py`.
* **Agen Terkait:** Cendekia (Chief Academic Researcher), Bima (Pengesah).
