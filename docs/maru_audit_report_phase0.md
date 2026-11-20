# LAPORAN AUDIT CODEBASE & ARSITEKTUR KANTOR 3D (PHASE 0)
**MARU HQ — Living Isometric 3D Corporate Headquarters**
*Status: COMPLETED — Sesuai Mandat PART 18 (STOP after Phase 0)*

---

### 1. Hasil Audit Arsitektur Saat Ini
* **Frontend Eksisting:**
  - File utama UI sebelumnya: `studio.html` (Vanilla JS + IIFE + Tailwind/CSS Variables + Canvas).
  - Standalone Viewer: Single HTML bundle (`maru_office_hyperlive.html`, `maru_hq_preview.html`) yang mandiri, portabel, dan ramah sandboxed iframe (`sandbox="allow-scripts"`).
* **Backend Eksisting:**
  - Python HTTP Server (port `8080` / `8443`), modul `src.security` (HMAC SHA-256 session token), `src.db` (SQLite `studio.sqlite3`), `src.hermes_mausbot`, `src.render`, dan `src.publish`.
* **Identitas 9 Agen Terdaftar (MARU Leaders):**
  1. `Bima` — Direktur HQ
  2. `Hermes` — Kreatif & Copy
  3. `Nara` — Brainstorming & Visual
  4. `Maus` — PR & Gerbang ACC
  5. `Cendekia` — Teori Komunikasi
  6. `Kirana` — Video Editor
  7. `Ardi` — Studio Dubbing
  8. `Wira` — IT Observability
  9. `Ootto` — TikTok Publisher
* **Fasilitas Bersama (Shared Facilities):**
  - Canteen & Pantry, Conference Meeting Room, Lounge / Rest Area, Reception & Main Entrance, Mushola, Perpustakaan/Arsip.

---

### 2. Usulan Arsitektur Integrasi 3D (Three.js Living Diorama)
* **3D Rendering Core:** Three.js r128 (Geometry reuse, InstancedMesh untuk kursi/meja/monitor, texture atlas, low-draw-calls).
* **Dual Camera System:**
  - Mode A: Fixed Isometric Camera (Orthographic / 45° Fixed Perspective) untuk tampilan makro gedung.
  - Mode B: Free Camera (OrbitControls) dengan batas polar angle $\le \pi/2.15$ dan batas zoom aman.
* **Living NPC & Real-Time State Adapter:**
  - 9 Pemimpin Divisi + NPC Staff Pendukung di setiap meja.
  - State Enum: `IDLE`, `WORKING`, `RESEARCHING`, `REVIEWING`, `PRODUCING`, `WAITING_APPROVAL`, `ON_BREAK`, `MEETING`, `COMPLETED`, `ERROR`, `OFFLINE`.
* **Integrasi Backend MARU:**
  - Polling fallback interval 2–3 detik ke endpoint `/api/state` atau WebSocket bila tersedia.
  - Sanitasi ketat: Kredensial, prompt internal, dan token OAuth tidak pernah diekspos ke UI.

---

### 3. Penilaian Risiko & Mitigasi (Risk Assessment)
1. **Performa di Laptop Biasa / HP:**
   - *Mitigasi:* Terapkan 3 Quality Profiles (`HIGH`, `BALANCED`, `PERFORMANCE`), minimalkan shadow map size, dan gunakan low-poly procedural geometries.
2. **Kamera Tembus Dinding/Lantai:**
   - *Mitigasi:* Pasang `minDistance`, `maxDistance`, dan clamp target Y pada OrbitControls.
3. **Integritas Data (No Fake Progress):**
   - *Mitigasi:* Bedakan secara eksplisit antara animasi santai (*ambient idle*) dan pekerjaan aktif (*real task execution*).

---

### 4. Roadmap Eksekusi Selanjutnya
* **Phase 1 & 2:** UI Shell navigasi lengkap + Blueprint Lantai Cutaway Gedung 3D.
* **Phase 3 & 4:** Interior 9 Ruangan + Fasilitas Lengkap + Penempatan Meja Karyawan & Rig NPC.
* **Phase 5 & 6:** Sistem Animasi Nyata (Task Driven, Speech Bubble, Exclamation Urgent) + Dual Camera Switching.
* **Phase 7 & 8:** Integrasi State Dashboard HQ + Pengujian Performa.
