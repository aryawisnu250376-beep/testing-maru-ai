# Pusat Skill MARU AI (`skills/`)

Folder ini menjadi sumber kebenaran terpusat untuk seluruh **Agent Skills (`SKILL.md`)** dan **Skill Hasil Pembelajaran (`learned/`)** pada ekosistem MARU AI.

## Struktur Direktori

- `REGISTRY.json` — Katalog otomatis seluruh skill yang terdaftar lintas divisi.
- `social-media/` — Skill operasional `01-social-media-agent` (`konten-ai`, `ringkas-modul`, `naskah-video`, `cek-mutu`, `usul-jadwal`).
- `academic/` — Skill pedagogis & disiplin sitasi `02-academic-ai` (`answer`, `citation-discipline`, `quiz`, `summary`, serta template akademik).
- `learned/` — Pola & hint yang dipelajari otomatis dari hasil kerja nyata:
  - `academic_answer_skills.json` — Hint panjang & sitasi dari jawaban berstatus `VERIFIED`/`REVISED`.
  - `social_media_winning_patterns.md` — Pola retensi video pemenang dari `learning.apply_insights()`.

## Sinkronisasi Otomatis

- Saat `MARU_GITHUB_SYNC_ENABLED=true`, pembaruan pada `learned/` diekspor dan diunggah secara otomatis (non-blocking) ke repository `aryawisnu250376-beep/testing-maru-ai`.
- Untuk menarik atau mengunggah manual:
  ```cmd
  python -m maru_github_sync sync
  ```
