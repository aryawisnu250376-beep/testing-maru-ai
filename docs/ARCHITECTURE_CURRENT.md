# CURRENT ARCHITECTURE — MARU HQ
**Dokumen Referensi: Phase 6.0 Integration Audit & Job System Architecture Blueprint**
*Klasifikasi Status Komponen: `VERIFIED` | `PARTIAL` | `NOT AVAILABLE` | `PROPOSED`*
*Tanggal Rilis: 13 November 2026*

---

## 1. ARSITEKTUR EKSISTING SAAT INI (PHASE 1 S/D 5B)

Sistem saat ini beroperasi dengan model **Dashboard-Centric Asynchronous Polling**, di mana UI web bertindak sebagai frontend pengendali dan backend Python menyediakan endpoint REST sederhana:

```
[ Browser / User ]
       │
       ▼
[ studio_bulletproof.html ] ◄── (sessionStorage Auth Token)
       │
       ├──► GET  /api/state   (Polling berkala status antrean, kartu ACC, episode)
       ├──► POST /api/action  (Aksi draf hermes, keputusan kartu Maus, jadwal Ootto)
       └──► Three.js Render Loop (60 FPS Living Diorama, Pill Tags & Inspector)
```

---

## 2. DETAIL ELEMEN ARSITEKTUR AKTUAL

### A. Frontend Layer (`studio_bulletproof.html`)
1. **Single Page Application IIFE:** Terisolasi dalam `(function() { ... })()`, mencegah polusi global namespace.
2. **Halaman Terisolasi (`.page-view`):**
   - `#page-overview` (KPI, Grafik Penonton, Ringkasan Status).
   - `#page-workflow` (Kartu ACC MausBot, Kanban Antrean `queue4`).
   - `#page-squad` (Daftar Karyawan AI MARU Corporation).
   - `#page-studio` (Studio Video 9:16, Creator Watchlist, Chat Assistant).
   - `#page-office` (Three.js 3D Living Isometric Command Center).
3. **Office 3D Engine (`window.MaruOffice3D`):**
   - Three.js r128 WebGLRenderer, OrbitControls isometrik, pencahayaan directional + ambient.
   - 14 ruangan terpartisi kaca tembus pandang, 27 karakter (9 Leader + 18 Dekoratif).
   - Raycasting selection hierarchy untuk seleksi karyawan & ruangan.

### B. Backend Layer (`/api/state` & `/api/action`)
1. **Endpoint `/api/state`:** Mengembalikan snapshot JSON berisi `totals`, `episodes`, `mausbot_cards`, `queue4`, `reference_creators`, `watchlist`, `skills_catalog`.
2. **Endpoint `/api/action`:** Menangani dispatch aksi pengguna:
   - `hermes_create_draft`: Menambahkan draf baru ke `queue4`.
   - `mausbot_card_decision`: Menyetujui atau menolak draf di Gerbang Maus.
   - `queue4_decision`: Memindahkan status antrean Kanban (`SETUJU` / `REVISI`).
   - `ootto_schedule`: Menetapkan timestamp jadwal tayang.

---

## 3. KELEMAHAN ARSITEKTUR EKSISTING
* **Ketiadaan Job Queue Terpadu:** Pekerjaan saat ini beroperasi secara *fire-and-forget* sinkronis; jika proses pembuatan video atau audio memakan waktu > 30 detik, browser akan mengalami timeout.
* **Tidak Ada State Persistence untuk Multi-Step Workflow:** Belum ada mekanisme pencatatan tahapan antar-agen (misal: Hermes selesai $\to$ Cendekia memverifikasi $\to$ Maus mereview $\to$ Kirana merender).
* **Status Berbasis Snapshot Database:** Status di UI mengandalkan kondisi data statis di tabel, belum memiliki event log perubahan status yang dapat diaudit secara runut.
