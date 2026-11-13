# LAPORAN PHASE 0 — FULL CODEBASE AUDIT & ARCHITECTURE SPECIFICATION
**MARU HQ — Living Isometric 3D Corporate Headquarters & Command Center**
*Berdasarkan: MASTER PROMPT MARU AI HQ INTEGRATION & MASTER PROMPT HYBRID ISOMETRIC 3D (v1.0)*
*Tanggal Audit: 12 November 2026*
*Auditor: Principal Frontend & Three.js Systems Architect*

---

## 1. PEMETAAN SOURCE CODE AKTUAL & ARSITEKTUR SISTEM

### A. Arsitektur Backend Eksisting
* **Runtime & Framework:** Python 3 (Standard Library + Async HTTP Server), dirancang *local-first* berjalan di Windows (`cmd.exe` / `PowerShell`).
* **Modul Inti:**
  1. `src/hermes_mausbot.py`: Engine orkestrasi bot & handler slash-commands, parser intent chat, manajemen antrean tugas episode.
  2. `src/dashboard.py`: HTTP Server penyaji REST API (`/api/login`, `/api/state`, `/api/action`, `/api/preview-bootstrap`, `/video/<id>`).
  3. `src/security.py`: Autentikasi sesi *bearer-token* berbasis HMAC-SHA256 persisten (`sessionStorage`), tanpa ambient cookie auth.
  4. `src/db.py`: Konektor database lokal SQLite (`studio.sqlite3`) untuk tabel episode, logs, dan state agensi.
  5. `src/render.py`: Pipeline rendering video vertikal MP4 (1080x1920 9:16).
  6. `src/publish.py` & `src/tiktok_bridge.py`: Modul integrasi Content Posting API TikTok (Direct Post).

### B. Arsitektur Frontend Eksisting
* **File Utama:** `studio.html` (versi terpasang: `studio_bulletproof.html`, 1.859 baris).
* **Teknologi:** Vanilla JavaScript (IIFE modul tertutup, Safe DOM Proxy guards), Tailwind-like CSS Variables dark theme, responsive viewport-fit mobile/desktop.
* **Routing & Halaman Eksisting:** Single Page Application (SPA) berbasis `data-page`:
  - `overview`: Metrik global, status server, status antrean, quick preview.
  - `workflow`: Alur pipeline (Draft -> ACC -> Render -> Publish).
  - `squad` (Tim AI): Grid profil karyawan dan pembagian divisi.
  - `studio`: Pemutar video interaktif 9:16, terminal log, tombol aksi ACC/Tolak/Revisi.
* **Polling Data:** Menggunakan fungsi `poll()` yang memanggil `GET /api/state` secara berkala (default 2–3 detik) dengan header `Authorization: Bearer <token>`.

---

## 2. PEMETAAN DEPARTEMEN & 9 NAMA AGEN RESMI (MARU LEADERS)

Sesuai master prompt, arsitektur tidak boleh menggunakan agen fiktif. Seluruh 9 nama departemen dan leadernya adalah:

| No | Departemen | Leader | Role Utama | Aktivitas Standar |
|---|---|---|---|---|
| 1 | **Executive HQ** | **Bima** | Chief Executive Intelligence | Monitoring agensi, review laporan, alokasi resource |
| 2 | **Kreatif & Naskah** | **Hermes** | Creative Director & Scriptwriter | Menulis naskah TikTok, merancang hook 3 detik |
| 3 | **Brainstorming & Tren** | **Nara** | Research Ideation Specialist | Scraping tren viral, riset format visual 9:16 |
| 4 | **PR & Gerbang ACC** | **Maus** | Quality Gatekeeper & PR | Verifikasi etika, filter konten, menunggu izin ACC pemilik |
| 5 | **Research Library** | **Cendekia** | Chief Academic Researcher | Membaca modul kuliah di Google Drive, audit teori komunikasi |
| 6 | **Video Production** | **Kirana** | Visual Production Director | Timeline video editing, komposisi kinetic typography |
| 7 | **Studio Dubbing** | **Ardi** | Voice Production Specialist | Rekaman vokal anak muda (Voice-02 Pro), audio mixing |
| 8 | **IT Observability** | **Wira** | Chief Technical Operations | Monitoring server zero-downtime, audit error log |
| 9 | **TikTok Publisher** | **Ootto** | Social Media Distribution | Eksekusi API Direct Post, jadwal tayang, metrik analitik |

**Fasilitas Bersama (Shared Facilities):**
- Canteen & Pantry (tempat istirahat & kopi).
- Meeting Room (ruang rapat & presentasi).
- Lounge & Rest Area.
- Reception & Main Entrance.
- Mushola & Ruang Doa.

---

## 3. STRATEGI INTEGRASI THREE.JS (NON-DESTRUKTIF)

### Prinsip Utama:
**Tidak merusak sistem lama.** Kita tidak membuang `studio.html` atau merombak endpoint backend. 
Integrasi dilakukan dengan menyisipkan tab halaman baru: `data-page="office"` (**Virtual Office 3D**) ke dalam navigasi `studio.html`, serta menyediakan viewer standalone (`maru_hq_command_center.html`).

### Skema Lapisan Arsitektur (UI Layer Separation):
```
┌────────────────────────────────────────────────────────────────────────┐
│                        TOP COMMAND HEADER                              │
│   [Logo MARU]  [Waktu Real-time]  [Kamera: ISO / FREE]  [Status Server]│
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│                      THREE.JS 3D VIEWPORT LAYER                        │
│   - Floor Cutaway: 9 Ruangan Departemen + Fasilitas Bersama            │
│   - Furniture Detil: Meja, Monitor Canvas, Rak Buku, Server, Mic       │
│   - Living NPCs: 9 Agen + Staf Pendukung (Animasi mengetik/baca)       │
│   - Ambient Life: Mobil jalan raya, karakter jalan antar-ruangan       │
│                                                                        │
│   [Overlay: Room Tags] [Overlay: Speech Bubbles] [Urgent ! Indicators] │
├────────────────────────────────────────────────────────────────────────┤
│                      BOTTOM CONTROL & ACC PANEL                        │
│   [Informasi Draf Konten Aktif]  ───▶  [Tombol ACC Pemilik / Status]  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. KEBUTUHAN ASET 3D & STRATEGI PERFORMA (60 FPS TARGET)

### A. Kebutuhan Aset 3D
Sesuai aturan *local-first*, kita tidak mengandalkan file eksternal `.gltf` raksasa dari CDN yang rentan gagal unduh atau lambat di HP. Seluruh aset dibangun menggunakan **Procedural Geometric Diorama** dengan Three.js:
- **Arsitektur:** Lantai bertekstur, pembatas partisi kaca transparan (*MeshPhysicalMaterial* dengan transmission), kusen baja minimalis.
- **Perabotan:** Meja modern minimalis, kursi ergonomis, stand mic rekaman kondensor + pop filter, rak server IT dengan indikator LED, 3 rak buku perpustakaan kayu, sofa lounge, meja rapat.
- **Karakter:** Model humanoid estilistik proporsional dengan jas divisi, kepala, rambut/topi unik, dasi, dan sendi tangan yang beranimasi saat mengetik/berjalan.

### B. Strategi Optimasi Performa
1. **Geometry & Material Reuse:** Mesh furnitur yang berulang (meja, kursi, komputer) menggunakan *geometry instance* yang sama untuk menekan Draw Calls (< 60 draw calls).
2. **Dynamic Canvas Texture untuk Layar Monitor:** Menggunakan 1 canvas kecil (128x64) yang di-update ringan untuk merender grafik bergerak di layar komputer tanpa membebani GPU.
3. **Shadow Map Capping:** Shadow map dibatasi pada 2048x2048 dengan bias halus untuk mencegah lag di laptop/HP.
4. **Frustum & Distance Culling:** Objek di luar jarak pandang kamera otomatis dilewati oleh renderer.
5. **Quality Profiles:**
   - `HIGH`: Bayangan soft, partisi kaca fisik, efek cahaya studio lengkap.
   - `PERFORMANCE`: Bayangan dimatikan, partisi kaca standar, refresh canvas lebih rendah (untuk HP low-end).

---

## 5. PENILAIAN RISIKO & MITIGASI (RISK ASSESSMENT)

| Risiko | Dampak | Strategi Mitigasi |
|---|---|---|
| **Memory Leak pada Polling State** | Browser melambat setelah berjalan berjam-jam | Gunakan variabel penampung tunggal, hindari alokasi objek Three.js baru di setiap siklus render `animate()`. |
| **Kamera Melompat / Tembus Lantai** | Pengalaman pengguna rusak | Kunci batas sudut kemiringan kamera (`maxPolarAngle = Math.PI / 2.15`), atur batas zoom minimum dan maksimum. |
| **Integritas Data (Palsu/Fake Progress)** | Melanggar Master Prompt Part 15 | Status animasi terikat ketat ke status backend (`WORKING`, `IDLE`, `WAITING_APPROVAL`). Jika tidak ada tugas aktif, karyawan berada di mode *ambient idle*. |
| **Kredensial Bocor ke Tampilan 3D** | Pelanggaran keamanan | Token, password, dan secret API disanitasi ketat; speech bubble hanya menampilkan ringkasan judul tugas edukasi. |

---

## 6. RENCANA IMPLEMENTASI BERTAHAP (ROADMAP)

* **Phase 1: UI Shell & Navigasi Terpadu**
  - Mengintegrasikan navigasi kontrol atas, pemilih mode kamera (`ISO` vs `FREE`), dan panel inspeksi pop-up.
* **Phase 2: Struktur Bangunan 3D Cutaway**
  - Merender denah lengkap 9 ruangan departemen + fasilitas kantin, lounge, meeting room, lobby, trotoar, dan jalan raya.
* **Phase 3: Detail Interior & Furnitur Spesifik**
  - Memasang furnitur khas: Perpustakaan Cendekia, Studio Dubbing Ardi, Server IT Wira, Meja Eksekutif Bima.
* **Phase 4: Populasi Karakter & Workstation Mapping**
  - Menempatkan 9 Leader resmi + NPC Staf pada koordinat meja kerja masing-masing.
* **Phase 5: Living System & Integrasi Tugas Nyata**
  - Menyambungkan event task ke animasi mengetik, balon ucapan, tanda seru `!`, dan gerakan Ardi ke studio saat di-ACC.
* **Phase 6: Pengujian Interaksi & Verifikasi Bebas Error**
  - Uji sentuhan gestur HP, responsivitas layar, dan sanitasi data.

---

**STATUS AUDIT PHASE 0: SELESAI.**
*Sesuai aturan Master Prompt Part 18: "STOP after Phase 0. Do not modify existing source code before reporting the audit."*

Mohon tinjau laporan audit di atas, Bre. Jika sudah sesuai dengan visi lu, berikan persetujuan untuk kita mulai eksekusi Phase 1!
