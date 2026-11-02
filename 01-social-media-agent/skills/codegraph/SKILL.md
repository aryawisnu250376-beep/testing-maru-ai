---
name: codegraph
description: Pemetaan graf kode sumber (AST, call graph, dependency antar-modul, skema database, endpoint API, dan analisis dampak perubahan / blast-radius) untuk audit arsitektur, integrasi MARU HQ, dan AI Technician.
source: https://github.com/aryawisnu250376-beep/testing-maru-ai
---
# Skill: CodeGraph — Codebase Dependency & Impact Intelligence

Gunakan skill ini sebelum mengubah arsitektur, membangun adapter lintas divisi (**MARU HQ ↔ Social Media ↔ Academic AI**), atau menjalankan perbaikan kode otomatis pada `app/technician/`.

## Prinsip Inti

Jangan pernah menebak struktur proyek dari ingatan atau hanya dari README. Bangun peta ketergantungan nyata dari kode aktual terlebih dahulu.

## Langkah Kerja Pemetaan Graf Kode

1. **Inventaris Entrypoint & Batas Modul**:
   - Petakan seluruh titik masuk eksekusi (`cli.py`, `mcp_server.py`, `run.py`, `web_run.py`, batch/shell scripts).
   - Pisahkan tegas batas domain: **HQ Control Plane**, **Divisi Social Media**, dan **Divisi Academic AI** (dilarang mengimpor tabel SQLite internal lintas divisi secara langsung).
2. **Ekstraksi Simbol & Relasi (AST / Ripgrep)**:
   - Gunakan modul standar Python `ast` atau pencarian terstruktur untuk memetakan:
     - `Module -> imports -> Module`
     - `Endpoint / Handler -> calls -> Service -> queries -> SQLite Table`
     - `Config / Env Var -> read_by -> Component`
3. **Analisis Blast-Radius Sebelum Edit**:
   - Untuk setiap fungsi, skema, atau kontrak JSON yang akan diubah, daftarkan **seluruh pemanggil (*callers*)** dan **seluruh file tes terkait**.
   - Jika tidak ada tes yang mencakup jalur kritis tersebut, tulis pengujian regresi terlebih dahulu sebelum memodifikasi implementasi.
4. **Deteksi Siklus & Duplikasi**:
   - Cegah *circular imports* antar-paket.
   - Tandai fungsi kembar atau skema antrean ganda agar diintegrasikan lewat adapter bersih, bukan digandakan lagi.

## Output Standar Saat Audit Arsitektur

Sajikan ringkasan graf dalam format ringkas yang mudah diperiksa manusia:
- **Peta Komponen & Entrypoint**
- **Jalur Aliran Data (`Request -> Manager -> Agent -> Verifier -> Storage`)**
- **Daftar Risiko Perubahan (*High / Medium / Low Blast-Radius*)**
- **Cakupan Tes yang Harus Dijalankan**
