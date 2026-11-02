# testing-maru-ai — Ekosistem MARU AI (Penyimpanan Kode, Skill, & Memori)

Repository terpusat untuk **MARU AI (Hybrid Autonomous AI Corporation)** yang menyatukan source code operasional beserta penyimpanan **Skill (`skills/`)** dan **Memori (`memory/`)** dengan sinkronisasi otomatis ke GitHub.

## Struktur Repository

| Direktori / File | Fungsi |
|---|---|
| `skills/` | Katalog & definisi skill terpusat lintas divisi (`social-media/`, `academic/`, `learned/`, `REGISTRY.json`) |
| `memory/` | Penyimpanan memori & state ringan ber-scope (`social-media/`, `academic/`, `hq/`, `index.json`) |
| `maru_github_sync/` | Modul Python Auto-Sync ke GitHub REST API (tanpa dependency eksternal tambahan) |
| `01-social-media-agent/` | Divisi Social Media Corporation (9Router, Hermes, Ootto, Studio, Learning Loop) |
| `02-academic-ai/` | Divisi Academic AI v5 (Manager/Verifier, 7 Mata Kuliah, Telegram, Web, RAG) |
| `sync_github.bat` / `.ps1` | Skrip 1-klik Windows CMD & PowerShell untuk tarik/simpan skill & memori |
| `.env.github.example` | Template konfigurasi token GitHub lokal (aman, tidak pernah di-commit) |

## Cara Mengaktifkan Auto-Sync di Laptop (Windows / VS Code)

1. Salin `.env.github.example` menjadi `.env` di root folder proyek:
   ```cmd
   copy .env.github.example .env
   ```
2. Isi variabel berikut di `.env`:
   ```env
   MARU_GITHUB_SYNC_ENABLED=true
   MARU_GITHUB_REPO=aryawisnu250376-beep/testing-maru-ai
   MARU_GITHUB_BRANCH=main
   MARU_GITHUB_TOKEN=github_pat_xxxx
   ```
3. Uji koneksi & sinkronisasi dari CMD / Terminal VS Code:
   ```cmd
   python -m maru_github_sync status
   sync_github.bat sync
   ```

## Alur Auto-Sync Otomatis Saat Aplikasi Berjalan

- **Academic AI (`02-academic-ai`)**:
  - Setiap kali pengguna menyampaikan fakta baru (`app/services/user_memory.py`), fakta disimpan ke SQLite lokal lalu diekspor & di-push otomatis ke `memory/academic/user_facts.json`.
  - Setiap kali jawaban lulus verifikasi `VERIFIED`/`REVISED` (`app/manager/skills.py`), pola skill pemenang diekspor & di-push otomatis ke `skills/learned/academic_answer_skills.json`.
- **Social Media Agent (`01-social-media-agent`)**:
  - Setiap kali `learning.apply_insights()` memperbarui pola retensi pemenang, hasilnya diekspor & di-push otomatis ke `skills/learned/social_media_winning_patterns.md`.
- **Aman & Non-Blocking**: Bila internet mati atau token kosong, aplikasi tetap berjalan normal secara lokal tanpa error.

## Aturan Keamanan

- Tidak ada file `.env` asli, token, password, biner database (`.db`/`.sqlite`), atau PDF materi berukuran besar yang diunggah ke repository ini.
- Gunakan **Fine-Grained Personal Access Token** yang dibatasi khusus pada repository `testing-maru-ai` dengan izin **Contents: Read and write**.
