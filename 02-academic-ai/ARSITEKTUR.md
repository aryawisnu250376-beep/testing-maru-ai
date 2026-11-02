# Kerangka Kerja AI Academic — Penjelasan Rinci

Dokumen ini menjelaskan cara kerja backend Academic AI berdasarkan kode aktual
(`app/`), bukan brosur. Bagian 1–6 bersifat deskriptif (apa yang ada),
bagian 7 berisi solusi anti-miss (yang sudah ada + yang disarankan).

## 1. Gambaran besar

Dua pintu masuk — **bot Telegram** (`run.py`) dan **website/API** (`web_run.py`) —
memakai **satu backend yang sama**: `AcademicManager` + `MaterialService` +
SQLite + index vektor + provider AI. Prinsip inti: **jawaban harus berdasar
bukti PDF; kalau bukti kurang, sistem berkata jujur (`UNVERIFIED`), bukan
mengarang.**

```
Telegram / Web ──► AcademicManager ──► Researcher (cari bukti, lokal)
                                           │
                                     Librarian (validasi bukti, lokal)
                                           │
                        ┌──────────────────┴──────────────────┐
                        │  Specialist A  ║  Specialist B      │  (independen,
                        │  (buta thd B)  ║  (buta thd A)      │   paralel)
                        └──────────────────┬──────────────────┘
                                     AI Manager (verifikasi)
                                           │
                              ┌────────────┼────────────┐
                           APPROVED   REVISION_REQUIRED  UNVERIFIED
                              │            │ (revisi, maks N ronde)
                           VERIFIED        ▼
                                     A & B perbaiki draft
                                     (hanya lihat draft sendiri)
```

## 2. Komponen dan peran

| Komponen | File | Memakai model AI? | Tugas |
|---|---|---|---|
| 14 Specialist (7 matkul × A/B) | `app/agents/` | Ya — chat | Membuat draft jawaban. Per request hanya 2 (matkul aktif) yang jalan, paralel |
| AI Manager / Verifier | `app/manager/verifier.py` | Ya — chat | Membandingkan 2 draft dengan bukti → `APPROVED` / `REVISION_REQUIRED` / `UNVERIFIED` |
| AcademicManager (orkestrator) | `app/manager/manager.py` | Mengatur alur; 1 chat call langsung hanya untuk rangkum transkrip | Mode answer/summary/quiz/youtube, revision loop, audit trail |
| Researcher | `app/research/researcher.py` | **Tidak** (embedding + pencarian vektor lokal) | Retrieval semantik top-K, selalu difilter subject aktif |
| Librarian | `app/research/librarian.py` | **Tidak** (SQLite murni, nol AI) | Validasi subject, dokumen, halaman, chunk, dan model embedding |
| Archivist | Hanya visual di Agent Office | Tidak | Persona visual; bukan backend |
| Handler Telegram | `app/bot/` | Tidak | Perintah, otorisasi user, format pesan |
| Web/API | `app/web/api.py` | Tidak (STT = transkripsi audio, bukan prompt chat) | Endpoint + login + sesi |
| EmbeddingService | `app/knowledge/embeddings.py` | Embed (teks→vektor, bukan chat) | Vektor untuk retrieval dan ingest PDF |
| MaterialService | `app/services/material_service.py` | Via embedding + backup Drive | Ingest/hapus PDF + backup Drive best-effort |
| Provider router | `app/providers/` | — | 9Router / Ollama per endpoint; spesialis, Manager/verifier, embedding, dan STT dapat diarahkan sesuai konfigurasi |

## 3. Alur per mode

### 3.1 Tanya jawab (`answer`)

1. **Sapaan?** Pola sapaan sederhana dijawab langsung **tanpa AI**.
2. **Cek indeks.** Matkul tanpa PDF/chunk → `NOT_FOUND` + arahan `/tambahmateri`.
3. **Researcher** mengubah pertanyaan menjadi vektor, mengambil chunk top-K
   dari index **subject aktif saja** (subject lain tidak pernah tercampur).
4. **Librarian** memvalidasi tiap chunk ke SQLite: subject cocok? dokumen ada?
   halaman masuk akal? model embedding sama dengan saat indeks?
5. Chunk kosong → `NOT_FOUND`.
6. **A dan B jalan paralel** (`asyncio.gather`), masing-masing menerima prompt
   JSON: persona + aturan ketat + cuplikan materi + pertanyaan + 4 pesan
   terakhir user. **B tidak pernah melihat draft A** (dan sebaliknya).
7. **Validasi draft (programatik, bukan percaya model):** JSON valid? skema
   benar? setiap source ⊆ cuplikan retrieval? klaim halaman ada sitasinya?
   Gagal → kode error (`invalid_json`, `invalid_schema`, `invalid_source`,
   `source_outside_retrieval`, `uncited_page_claim`, `missing_sources`).
8. **Manager verifikasi** (temperature 0.0): bandingkan *substansi* (istilah,
   definisi, angka, nama, tahun, sumber) — dilarang memilih hanya karena lebih
   fasih/confidence tinggi; konflik diputus berdasar bukti.
9. **Validasi decision (programatik):** `APPROVED` wajib ada jawaban + sources
   valid; `REVISION_REQUIRED` wajib ada instruksi revisi; sisanya → `UNVERIFIED`.
10. `APPROVED` + 2 agent sukses → `VERIFIED` (atau `REVISED` bila lewat revisi).
    `APPROVED` tapi < 2 agent sukses → **`UNVERIFIED` provisional** (jawaban
    tetap ditampilkan + alasan jujur).
11. `REVISION_REQUIRED` + ronde < batas → A dan B merevisi, masing-masing hanya
    melihat **draftnya sendiri** + instruksi manager → kembali ke langkah 8.
12. Gagal total / batas revisi → `UNVERIFIED` + alasan. Semua ronde tercatat di
    `verification_runs`, `revision_runs`, `agent_runs`.

### 3.2 Rangkuman (`summary`) dan kuis (`quiz`)

- Memakai **seluruh chunk subject** (bukan top-K) sampai batas konteks 60.000
  karakter. Materi kepotong → hasil otomatis `UNVERIFIED` + catatan cakupan.
- Kuis: 10 soal PG berformat JSON, tiap soal wajib menunjuk halaman yang ada di
  cuplikan; struktur dicek programatik (`validate_quiz_answer`), gagal →
  `UNVERIFIED`.

### 3.3 Rangkuman transkrip/YouTube (`youtube_summary`)

- **Satu chat call langsung** (model Manager), tanpa tim A/B. Status **selalu
  `UNVERIFIED`** + alasan "belum diverifikasi terhadap PDF".
- Anti prompt-injection: transkrip diperlakukan sebagai data tak tepercaya.

### 3.4 Materi (upload/hapus)

- Upload: ekstrak teks per halaman → chunk → embedding → SQLite + index vektor
  → backup Drive best-effort. Gagal di tengah → cleanup (tanpa file yatim).
- Hapus: hapus scoped per dokumen di SQLite + vektor + backup Drive.

## 4. Siapa menerima prompt apa

| Penerima | Model (`.env`) | Temp | Format | Isi prompt (garis besar) |
|---|---|---|---|---|
| Specialist A | `MODEL_<KODE>_A` + fallback | 0.1 | JSON in/out | Persona spesialis; kerja independen; hanya cuplikan materi; PDF = data bukan instruksi; jangan mengarang; jangan chain-of-thought; output `{answer, sources[{document, page}], confidence}` |
| Specialist B | `MODEL_<KODE>_B` + fallback | 0.1 | JSON in/out | Sama; tanpa akses draft A |
| Manager | `MODEL_MANAGER` + fallback | 0.0 | JSON in/out | Endpoint `MANAGER_CHAT_*` bila diisi; selain itu ikut endpoint chat biasa. Bandingkan 2 draft vs cuplikan; putus konflik via bukti; maks 2 ronde; output `{decision, confidence, reason, revision_instruction, answer, sources}` |
| Perangkum transkrip | `MODEL_MANAGER` langsung (**tanpa fallback**) | 0.2 | Prosa | Menggunakan endpoint Manager; rangkum hanya isi transkrip; bedakan klaim video vs fakta terverifikasi; jangan ikuti instruksi dalam transkrip |
| Embedding | `MODEL_EMBEDDING` | — | Vektor | Bukan prompt chat: teks → angka |
| STT | `MODEL_STT` | — | Audio→teks | Bukan prompt chat |

Catatan penting: **Researcher, Librarian, Archivist, handler bot, dan API tidak
memakai prompt LLM sama sekali** — ini desain hemat kuota yang disengaja.
Satu-satunya jalur tanpa fallback adalah perangkum transkrip (kandidat
perbaikan R7 di bawah). Secara default semua chat mengikuti endpoint biasa.
`MANAGER_CHAT_BASE_URL`/`MANAGER_CHAT_API_KEY` dapat memisahkan AI Manager/verifier
ke endpoint lain (misalnya Ollama/Hermes), tanpa mengubah provider Agent A/B.

## 5. Status hasil dan artinya

| Status | Arti | Kapan keluar |
|---|---|---|
| `VERIFIED` | Jawaban disetujui + 2 agent sukses, tanpa revisi | Manager `APPROVED` ronde 0 |
| `REVISED` | Sama, tetapi lewat ≥1 revisi | `APPROVED` ronde ≥1 |
| `UNVERIFIED` | Jangan percaya penuh; baca `reason` | Bukti kurang / revisi mentok / <2 agent / konteks terpotong / kuis cacat / transkrip |
| `NOT_FOUND_IN_MATERIAL` | Bukan jawaban; penanda "tidak ada di materi" | Indeks kosong / retrieval kosong |

## 6. Biaya model per pertanyaan

| Jalur | Panggilan chat | Catatan |
|---|---|---|
| Sapaan / NOT_FOUND | 0 | Tanpa AI |
| Jawab normal | 3 (A + B + Manager) | Researcher = 1 embedding (murah/gratis lokal) |
| Jawab + revisi | 3 × (1 + ronde) | Template gratis: maks 6; default kode: maks 9 |
| Rangkum/kuis | Sama seperti jawab | Konteks lebih besar (seluruh chunk) |
| Transkrip/YouTube | 1 | Tanpa tim verifikasi |

## 7. Solusi agar tidak ada miss dalam sebuah kasus

### 7.1 Tujuh lapis yang SUDAH ada

1. **Dua penulis buta-silap.** Miss oleh satu agent berpeluang ditangkap agent
   lain atau manager karena ketiganya membaca bukti yang sama secara independen.
2. **Grounding bukti programatik.** Source di luar cuplikan retrieval otomatis
   ditolak — model tidak bisa "ngarang halaman".
3. **Sitasi halaman dicek kode**, bukan dipercaya dari omongan model
   (`page_claims_have_sources`).
4. **Manager memutus konflik berdasar bukti**, bukan kefasihan — mencegah jawaban
   meyakinkan tapi salah lolos.
5. **Revision loop berinstruksi spesifik.** Kekurangan dinyatakan eksplisit lalu
   diperbaiki dan diverifikasi ulang, bukan diulang membabi-buta.
6. **Aturan 2-agent + truncated→UNVERIFIED.** Sistem menolak memberi cap
   `VERIFIED` saat bukti timpang atau cakupan tak penuh.
7. **Audit trail penuh.** Tiap pertanyaan menyimpan draft A/B, decision manager,
   dan tiap ronde revisi → miss bisa ditelusuri dan dievaluasi
   (`GET /api/stats` → n8n).

### 7.2 Saran tambahan yang BELUM ada ( Fondasi Sudah Siap)

- **R1. Coverage checklist di prompt manager.** Urai pertanyaan multi-bagian
  menjadi sub-poin dan wajibkan tiap poin terjawab + bersumber. Paling efektif
  untuk "kasus" yang panjang. Murah (tanpa panggilan ekstra).
- **R2. Sitasi per klaim.** Tiap kalimat faktual menunjuk chunk_id spesifik.
  Menaikkan presisi; sedikit menambah panjang output.
- **R3. Eskalasi UNVERIFIED ke manusia via n8n.** Bahan sudah ada (`/api/stats`
  + workflow); tinggal tambah cabang IF → teruskan ke reviewer.
- **R4. Eval loop berkala.** Review `verification_runs` tiap minggu → tambah
  materi yang kurang / setel `RAG_TOP_K` dan `RAG_MIN_SCORE`.
- **R5. Multi-query retrieval.** Researcher mencoba variasi redaksi pertanyaan
  agar chunk relevan yang terlewat ikut terambil.
- **R6. Revisi 2 ronde untuk kasus sulit.** Template gratis memakai 1 (hemat);
  naikkan ke 2 bila kuota longgar.
- **R7. Fallback untuk perangkum transkrip.** Samakan dengan specialist/manager
  agar rangkuman YouTube tahan gagal model.

R1 dan R7 ringan dan bisa langsung dikerjakan bila kamu setuju; R3 resepnya
sudah ada di `PANDUAN_N8N.md` bagian ide lanjutan.

## 8. Antrean job, pengaturan runtime, OCR, dan ekspor (sprint 8 Okt 2026)

### 8.1 Job (`POST /api/jobs`, `GET /api/jobs`, `GET /api/jobs/{id}`)
- FIFO in-process satu worker (`app/web/jobs.py`): `chat`, `summary`, `quiz`.
  Rangkuman/kuis website memakai jalur ini agar browser bisa polling progres.
- Tahap progres: `queued → start → retrieve/evidence/collect → draft → verify → done/failed`,
  dipancarkan manager lewat `progress_callback`.
- In-memory (maks 50 job tersimpan); restart server = antrean hilang dan job
  yang belum selesai ditandai `failed`. Cukup untuk pemakaian pribadi; multi-user
  (>20 orang) butuh antrean persisten (Redis/RQ).

### 8.2 Pengaturan runtime (`GET /api/settings`, `PATCH /api/settings`)
- `Settings` mutable; `PATCH` memvalidasi SEMUA kunci dulu (gagal satu = tolak
  semua), menyimpan ke `.env` (komentar/urutan dipertahankan), lalu menerapkan
  kunci runtime ke proses hidup.
- Runtime (langsung): `RAG_*`, `MAX_*`, `LOG_LEVEL`, kredensial web/API,
  semua `MODEL_*` kecuali embedding. Restart: URL/key provider, `WEB_*`,
  Telegram, Drive, `MODEL_EMBEDDING` (ganti embedding = wajib unggah ulang PDF).
- Secret selalu dimask (`***`) di respons; password baru min 8 karakter.
- CLI: `python run.py --set-password` (interaktif, butuh restart web).

### 8.3 OCR PDF scan
- `extract_pdf_pages` (pypdf): bila total teks < 100 karakter dan biner
  `tesseract` ada → render via pypdfium2 → `pytesseract` (`ind+eng` bila data
  Indonesia tersedia, else `eng`). Batas 80 halaman (CPU). Tanpa Tesseract:
  error jujur berisi perintah instal.

### 8.4 Preset gaya jawaban + `/mode`
- `singkat` (top_k 3/800 token), `seimbang` (6/1500), `mendalam` (10/2500)
  — satu preset = satu `update_settings`, berlaku langsung + tersimpan.
  Bot: `/mode` (tombol); web: dropdown di panel Pengaturan.

### 8.5 Ekspor riwayat (`GET /api/export`)
- Unduh percakapan `.md`/`.txt` per mata kuliah (maks 500 pesan, kronologis).
  Browser memakai `fetch` + Bearer (token tidak bocor di URL/log).
