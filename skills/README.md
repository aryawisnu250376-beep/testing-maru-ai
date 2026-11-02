# Pusat Skill MARU AI (`skills/` — 68 Skill Terkurasi)

Folder ini menjadi sumber kebenaran terpusat untuk seluruh **Agent Skills (`SKILL.md`)** dan **Skill Hasil Pembelajaran (`learned/`)** pada ekosistem **MARU AI** (**MARU HQ**, **Social Media Corporation**, dan **Academic AI**).

---

## Ringkasan Katalog Skill Terpasang (68 Skill)

### 1. Divisi Social Media, Video, Motion & 3D (`skills/social-media/` — 19 Skill)
- **Pipeline Inti MARU**: `konten-ai`, `ringkas-modul`, `naskah-video`, `cek-mutu`, `usul-jadwal`
- **Video Programatik & Sinematik**: `remotion`, `hyperframes`, `video-shotcraft`, `money-printer-turbo`, `manim-video`, `ai-presenter-video`, `kanban-video-orchestrator`
- **3D, Generative Visual & Desain Brand**: `blender-mcp`, `img2threejs`, `comfyui`, `brand-guidelines`, `canvas-design`, `theme-factory`
- **Anti-Slop Naskah Konten**: `antislop-copywriting`

### 2. Divisi Academic AI & Riset Ilmiah (`skills/academic/` — 18 Skill)
- **Pedagogi & Verifikasi Inti MARU**: `answer`, `citation-discipline`, `quiz`, `summary`, `explain-simple`, `quiz-maker`, `summarize-id`, `bedah-jurnal`
- **Riset Ilmiah & NotebookLM Mandiri**: `open-notebook`, `grounded-citations`, `arxiv-research`, `research-paper-writing`, `academy-guide`
- **Olah Dokumen Kuliah & Akademik**: `pdf`, `docx`, `pptx`, `xlsx`, `doc-coauthoring`

### 3. Lintas Divisi / MARU HQ, UI/UX, Anti-Slop & Otomasi (`skills/shared/` — 31 Skill)
- **Anti-Slop & Kualitas Tulisan/Kode**: `antislop`, `antislop-ui`, `no-ai-slop`
- **UI/UX, Design System, Stitch & Penpot**: `impeccable`, `ui-ux-pro-max`, `penpot-mcp`, `diagram-design`, `frontend-design`, `web-design-guidelines`, `react-best-practices`, `stitch-generate-design`, `stitch-design-md`, `stitch-taste-design`, `stitch-loop`
- **MARU HQ, Multi-Agent, Routing & CodeGraph**: `maru-hq-governance`, `multica-ai`, `omni-route`, `codegraph`, `gitnexus-explorer`, `dynamic-workflow`, `ai-agent-observability`, `arch-design-review`
- **Otomasi, Pencarian, & Ekosistem Skill**: `find-skills`, `antigravity-skills`, `skill-creator`, `mcp-builder`, `skill-security-auditor`, `n8n-workflow-patterns`, `n8n-mcp-tools-expert`, `searxng-search`, `webapp-testing`

---

## Cara Menambah Skill Baru dari GitHub Kapan Saja

### 1. Impor 1-Klik dari URL GitHub Mana Pun
```cmd
add_skill.bat https://github.com/<owner>/<repo>/tree/main/skills/<nama-skill> shared
```
Atau via Python:
```cmd
python -m maru_github_sync add-skill <URL_GITHUB> --division <academic|social-media|shared>
```

### 2. Tambah Langsung dari Browser GitHub `testing-maru-ai`
Buat file `skills/<divisi>/<nama-skill>/SKILL.md` lewat tombol **Add file** di GitHub, lalu jalankan `sync_github.bat pull` di laptop.
