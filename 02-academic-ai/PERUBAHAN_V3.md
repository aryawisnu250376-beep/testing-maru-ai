# Perubahan v3 — Video Explainer + Stack AI 15 Lapis

Dari `academic_ai_v2.zip` ke versi ini. Kompatibel mundur: tanpa variabel
baru dan tanpa ffmpeg, aplikasi berperilaku seperti v2 (fitur video/TTS
menolak dengan pesan install yang jelas, bukan crash).

## Baru

- **Video explainer MP4** (`/video`): alur preflight → research → script →
  narration → slides → render; job async + unduhan + tombol 🎬 di web.
- **TTS lokal**: Piper-first, fallback edge-tts, error jujur bila tak ada.
- **Riset web** (`/web`, `POST /api/web`): Scrapling→httpx, tautan DuckDuckGo.
- **PDF Docling-first**: Docling bila ada, fallback pypdf→OCR seperti dulu.
- **RAG_MODE** `vector|tree|hybrid`: tree index leksikal tanpa embedding.
- **Memori user**: fakta "nama saya …" diingat per `user_id`, disuntik
  sebagai `[profil]` pada pertanyaan berikut.
- **Kompresi konteks**: dedupe chunk + rolling history + metrik hemat token.
- **Answer skills**: gaya jawaban menang direkam, hint diinjeksikan.
- **Fabric patterns**: `explain_simple`, `summarize_id`, `quiz_maker` +
  `GET /api/patterns` + bot `/jelaskan`.
- **n8n Trend Briefing**: `n8n/trend_briefing.json` siap impor.
- **Panduan**: `PANDUAN_STACK_AI.md` (15 lapis + env + endpoint).

## Berubah

- Skema DB: tabel `videos`, `user_facts`, `answer_skills` (dibuat otomatis).
- `POST /api/jobs` terima task `video` (wajib `topic`).
- `answer()` terima `user_id`; bot teruskan id Telegram.
- Settings runtime baru: `TTS_PROVIDER`, `TTS_VOICE`, `VIDEO_MAX_SCENES`,
  `RAG_MODE`, `MEMORY_ENABLED`, `SKILLS_LEARN_ENABLED`, `WEB_RESEARCH_ENABLED`.
- `requirements.txt`: + Pillow, piper-tts, edge-tts, docling.

## Verifikasi

- `pytest`: 115 lolos — `node tests/test_web_ui.js` + `test_agent_office.js`
  lolos — `ruff check` + `ruff format --check` bersih.

Inspirasi OpenMontage (AGPL) hanya pola pipeline/preflight/decision-log —
tidak ada kode OpenMontage yang disalin.
