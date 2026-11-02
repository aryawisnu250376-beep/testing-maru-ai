# Pusat Skill MARU AI (`skills/`)

Folder ini menjadi sumber kebenaran terpusat untuk seluruh **Agent Skills (`SKILL.md`)** dan **Skill Hasil Pembelajaran (`learned/`)** pada ekosistem MARU AI.

## Struktur Direktori

- `REGISTRY.json` — Katalog otomatis seluruh skill yang terdaftar lintas divisi.
- `social-media/` — Skill operasional `01-social-media-agent` (`konten-ai`, `ringkas-modul`, `naskah-video`, `cek-mutu`, `usul-jadwal`, + skill tambahan).
- `academic/` — Skill pedagogis & disiplin sitasi `02-academic-ai` (`answer`, `citation-discipline`, `quiz`, `summary`, + skill tambahan).
- `shared/` — Skill lintas divisi yang otomatis didistribusikan ke **Social Media** dan **Academic AI**.
- `learned/` — Pola & hint yang dipelajari otomatis dari hasil kerja nyata:
  - `academic_answer_skills.json` — Hint panjang & sitasi dari jawaban berstatus `VERIFIED`/`REVISED`.
  - `social_media_winning_patterns.md` — Pola retensi video pemenang dari `learning.apply_insights()`.

---

## 2 Cara Menambahkan Skill Baru dari GitHub

### Cara 1: Impor Otomatis dari Repository GitHub Orang Lain / Open-Source (1 Perintah)
Misalnya Anda menemukan skill open-source di GitHub (seperti `anthropics/skills` atau koleksi `SKILL.md` lainnya). Cukup jalankan di CMD / Terminal VS Code:

```cmd
add_skill.bat https://github.com/anthropics/skills/tree/main/skills/pdf academic
```
Atau menggunakan Python langsung:
```cmd
python -m maru_github_sync add-skill https://github.com/anthropics/skills/tree/main/skills/docx --division shared
```
Otomatis mengunduh `SKILL.md`, memasangnya ke `skills/<divisi>/<nama>/SKILL.md`, menyebarkannya ke aplikasi divisi lokal, memperbarui `skills/REGISTRY.json`, dan langsung mengunggahnya ke `testing-maru-ai`!

### Cara 2: Buat / Upload Langsung di Web GitHub `testing-maru-ai`
1. Buka `https://github.com/aryawisnu250376-beep/testing-maru-ai`.
2. Klik **Add file** → **Create new file**.
3. Ketik path: `skills/academic/cek-jurnal/SKILL.md` (atau `skills/social-media/<nama>/SKILL.md` / `skills/shared/<nama>/SKILL.md`).
4. Isi instruksi dengan format standar:
   ```markdown
   ---
   name: cek-jurnal
   description: Verifikasi metodologi dan sitasi jurnal ilmiah.
   task_mode: answer, summary
   ---
   # Skill: Cek Jurnal Ilmiah
   1. Periksa tahun terbit, metode penelitian, dan kesimpulan utama.
   2. Tandai bila klaim tidak didukung data sampel di dalam PDF.
   ```
5. Klik **Commit changes**, lalu di laptop jalankan `sync_github.bat pull`. Skill langsung aktif dipakai agent tanpa perlu mengubah kode Python!
