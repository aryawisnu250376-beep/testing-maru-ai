# Panduan Stack AI (15 Lapis)

Ringkasan implementasi lokal di repo ini. Semua gratis/self-host, tanpa kunci API
berbayar. Lihat juga `.env.example` untuk daftar kunci lengkap.

## 1. Video Explainer (`/video`)

Alur: `preflight → research → script → narration → slides → render`.

- `app/services/video_service.py` — orkestrasi `VideoService.build_video()`.
- `app/services/tts.py` — narasi Piper dulu, fallback edge-tts (`TTS_PROVIDER=auto`).
- Job async: `POST /api/jobs {"task": "video", "topic": "..."}` → unduh di
  `GET /api/videos/{id}/download`. UI: tombol 🎬 Video di Study Desk.
- Butuh `ffmpeg` di PATH dan suara Piper (`TTS_VOICE`, default
  `id_ID-fajri-medium`) atau akses `edge-tts` untuk fallback.

## 2. TTS Lokal (Piper + edge-tts)

`pick_engine("auto")` pilih Piper bila biner `piper` ada, else edge-tts bila
`edge-tts` ada. Gagal jujur: error sebut perintah install yang kurang.

## 3. Web Research (`/web`)

`app/services/webfetch.py`: ambil HTML via Scrapling (bila terpasang) lalu
fallback httpx; tautan dari DuckDuckGo HTML (`duckduckgo_links`).
`POST /api/web {"query": "..."}` → rangkuman terverifikasi + `source_url`.
Bot: `/web <topik>`.

## 4. Docling-first PDF

`extract_pdf_pages()` coba Docling dulu, fallback pypdf → OCR.
Docling tidak wajib: bila tidak terpasang, kode lanjut diam-diam (ImportError
ditangkap). Install opsional: `pip install docling`.

## 5. Tree RAG (`RAG_MODE`)

`app/knowledge/tree_index.py` bangun pohon seksi leksikal (deteksi BAB/judul)
dan `retrieve_with_tree()` pilih seksi relevan tanpa embedding.
`RAG_MODE=vector|tree|hybrid` (runtime, bisa diubah via Settings).

## 6. Memori User (`MEMORY_ENABLED`)

`app/services/user_memory.py`: `answer(..., user_id=...)` merekam fakta
("nama saya …", "saya kelas …") ke tabel `user_facts` (maks 50/user) dan
menyuntik `[profil]` relevan ke riwayat. Bot teruskan `user_id` Telegram.

## 7. Kompresi Konteks

`app/knowledge/compress.py`: `compress_chunks()` dedupe + rapikan spasi +
batasi `MAX_CONTEXT_CHARS`; `rolling_history()` simpan pesan user pertama +
ekor; `estimate_saved()` untuk metrik hemat token di log debug.

## 8. Answer Skills (`SKILLS_LEARN_ENABLED`)

`app/manager/skills.py`: tiap jawaban VERIFIED/REVISED direkam bentuknya
(panjang, jumlah sumber) per `tugas:mapel`; jawaban berikut dapat hint gaya
yang menang ("coba ~N kata, M sumber"). Tabel `answer_skills`.

## 9. Fabric Patterns

`app/knowledge/prompts/academic/*.md`: `explain_simple`, `summarize_id`,
`quiz_maker`. `render(pola, **var)` isi variabel `{...}`.
`GET /api/patterns` daftar pola; bot `/jelaskan <topik>` pakai pola
`explain_simple` + RAG.

## 10. Bot: /video & /jelaskan & /web

`app/bot/handlers/video.py`, `discover.py`, terdaftar di `telegram_bot.py`.
`/video` kirim MP4 progresif (pesan status → file). `/jelaskan` jawab terverifikasi.
`/web` riset web + kutip URL sumber.

## 11. n8n: Trend Briefing

`n8n/trend_briefing.json` — contoh workflow impor: cron Senin 07:00 →
`POST /api/web` per topik → format → kirim Telegram. Isi
`ACADEMIC_API_TOKEN` dan `TELEGRAM_CHAT_ID` di environment n8n.

## 12. TrendRadar (terminologi skor)

Skor tren untuk briefing: **frekuensi** (kemunculan topik), **kesegaran**
(sumber < 30 hari), **nilai guna** (relevansi ke SUBJECTS aktif).
Lihat `scoring_hint` di `n8n/trend_briefing.json`.

## 13. Daytona (catatan)

Repo ini tidak memanggil Daytona API; pola yang dipakai: pekerjaan berat
(ffmpeg, TTS, Docling) jalan sebagai job async di worker — setara pola
"lempar ke sandbox, polling hasil" bila nanti dipindah ke Daytona.

## 14. AI Hub (catatan)

`GET /api/patterns` + `prompts/academic/*.md` adalah "hub pola" lokal:
satu tempat untuk template prompt yang dipakai bot, API, dan workflow.

## 15. Verifikasi

```bash
.venv/bin/python -m pytest tests/ -q   # ±115 tes
node tests/test_web_ui.js              # helper UI + tombol Video
node tests/test_agent_office.js        # regresi Agent Office
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## Kunci Environment Baru

| Kunci | Default | Arti |
|---|---|---|
| `TTS_PROVIDER` | `auto` | `auto\|piper\|edge` |
| `TTS_VOICE` | `id_ID-fajri-medium` | suara Piper / Edge |
| `VIDEO_MAX_SCENES` | `6` | maks adegan per video |
| `VIDEOS_DIR` | `data/videos` | simpan MP4 |
| `RAG_MODE` | `vector` | `vector\|tree\|hybrid` |
| `MEMORY_ENABLED` | `true` | ingat fakta user |
| `SKILLS_LEARN_ENABLED` | `true` | belajar gaya jawaban |
| `WEB_RESEARCH_ENABLED` | `false` | saklar riset web |

## Endpoint Baru

- `POST /api/jobs` task `video` (+ `topic` wajib)
- `GET /api/videos`, `GET /api/videos/{id}/download`
- `POST /api/web`, `GET /api/patterns`
